"""Tablas cargadas por el usuario: detección, unión y bases NBA inmutables."""
from copy import deepcopy
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import time
import unicodedata
from uuid import uuid4
from zipfile import ZipFile, BadZipFile

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import Field

if __package__:
    from . import servicio as svc
    from .esquemas import Modelo, Pedido, diccionario
else:
    import servicio as svc
    from esquemas import Modelo, Pedido, diccionario
from modelo.optimizacion.problema import condition_columns

router = APIRouter(prefix="/api/datos", tags=["Datos adaptables"])
CHUNK = 1024 * 1024
MAX_BYTES = 32 * CHUNK
MAX_ROWS = 100_000
MAX_COLUMNS = 200
KEY_NAMES = {"id_cliente", "cliente_id", "customer_id", "id_customer", "documento", "cedula", "identificacion", "id"}


def storage_id(value):
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Identificador de datos inválido")
    return value


def slug(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:120]


def decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def profile(frame):
    columns = []
    for name in frame.columns:
        values = frame[name]
        present = values[values != ""]
        numbers = present.map(decimal)
        numeric = name not in KEY_NAMES and name not in svc.TEXT_COLUMNS and len(present) > 0 and numbers.notna().all()
        probability = bool(numeric and len(present) == len(values) and numbers.map(lambda n: 0 <= n <= 1).all())
        columns.append({"nombre": name, "tipo": "numero" if numeric else "texto",
                        "vacios": int((values == "").sum()), "unicos": int(values.nunique()),
                        "clave": bool(len(present) == len(values) and values.is_unique),
                        "score": probability})
    return columns


def clean_table(header, rows):
    names = [slug(value) for value in header]
    if not names or len(names) > MAX_COLUMNS or any(not name for name in names):
        raise ValueError(f"Cada tabla debe tener encabezados no vacíos y hasta {MAX_COLUMNS} columnas")
    if len(set(names)) != len(names):
        raise ValueError("Hay encabezados duplicados después de normalizar sus nombres")
    records = []
    for index, row in enumerate(rows):
        if index >= MAX_ROWS:
            raise ValueError(f"Cada tabla admite hasta {MAX_ROWS:,} filas")
        if len(row) > len(names) and any(value not in (None, "") for value in row[len(names):]):
            raise ValueError(f"La fila {index + 2} tiene más valores que encabezados")
        values = ["" if value is None else str(int(value) if isinstance(value, bool) else value).strip() for value in row[:len(names)]]
        values += [""] * (len(names) - len(values))
        if any(values):
            records.append(values)
    if not records:
        raise ValueError("La tabla no contiene filas de datos")
    return pd.DataFrame(records, columns=names)


def parse_file(raw, filename):
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 128 * CHUNK:
                    raise ValueError("El Excel descomprimido es demasiado grande")
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        except (BadZipFile, KeyError) as error:
            raise ValueError("No se pudo leer el archivo Excel") from error
        try:
            if len(book.worksheets) > 10:
                raise ValueError("Carga un Excel con hasta diez hojas")
            tables = []
            for sheet in book.worksheets:
                rows = sheet.iter_rows(values_only=True)
                header = next(rows, None)
                if header is not None and any(value is not None for value in header):
                    tables.append((sheet.title, clean_table(header, rows)))
            if not tables:
                raise ValueError("El Excel no contiene tablas con encabezados")
            return tables
        finally:
            book.close()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    if suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError as error:
            raise ValueError("El JSON no es válido") from error
        tables = {Path(filename).stem: data} if isinstance(data, list) else data
        if not isinstance(tables, dict) or not 1 <= len(tables) <= 10:
            raise ValueError("Usa una lista de registros o un objeto con hasta diez tablas")
        result = []
        for name, records in tables.items():
            if not isinstance(records, list) or not records or not all(isinstance(row, dict) for row in records):
                raise ValueError(f"La tabla {name} debe ser una lista de registros")
            header = list(dict.fromkeys(key for row in records for key in row))
            if any(isinstance(value, (dict, list)) for row in records for value in row.values()):
                raise ValueError("Las celdas JSON deben ser valores simples; usa tablas separadas para relaciones")
            result.append((str(name), clean_table(header, ([row.get(key) for key in header] for row in records))))
        return result
    if suffix not in (".csv", ".tsv"):
        raise ValueError("Formatos admitidos: CSV, TSV, XLSX y JSON")
    try:
        delimiter = "\t" if suffix == ".tsv" else csv.Sniffer().sniff(text[:65536], delimiters=",;\t").delimiter
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        frame = clean_table(next(reader, []), reader)
    except csv.Error as error:
        raise ValueError("No se pudo identificar la tabla CSV; revisa separadores y comillas") from error
    if delimiter == ";":
        for name in frame:
            if name in KEY_NAMES or name in svc.TEXT_COLUMNS:
                continue
            values = frame[name].str.replace(",", ".", regex=False)
            present = values[values != ""]
            if len(present) and present.map(decimal).notna().all():
                frame[name] = values
    return [(Path(filename).stem, frame)]


def save_table(frame, name, source):
    key = uuid4().hex
    raw = frame.to_csv(index=False).encode()
    metadata = {"id": key, "nombre": name[:160], "archivo": source[:160], "filas": len(frame),
                "columnas": profile(frame), "datos_sha256": hashlib.sha256(raw).hexdigest()}
    svc.STORE.write(f"tablas/{key}/datos.csv.gz", gzip.compress(raw), "application/gzip")
    svc.STORE.write_json(f"tablas/{key}/manifest.json", metadata)
    return metadata


def load_table(key):
    key = storage_id(key)
    metadata = svc.STORE.json(f"tablas/{key}/manifest.json")
    raw = svc.STORE.read(f"tablas/{key}/datos.csv.gz")
    if metadata is None or raw is None:
        raise FileNotFoundError("La tabla ya no está disponible; vuelve a cargarla")
    return metadata, pd.read_csv(io.BytesIO(raw), compression="gzip", dtype=str, keep_default_na=False)


class Archivo(Modelo):
    nombre: str = Field(min_length=1, max_length=160)
    bytes: int = Field(gt=0, le=MAX_BYTES)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/archivos")
def start_upload(p: Archivo):
    if Path(p.nombre).suffix.lower() not in (".csv", ".tsv", ".xlsx", ".json"):
        raise ValueError("Selecciona un CSV, TSV, Excel XLSX o JSON")
    key = uuid4().hex
    svc.STORE.write_json(f"cargas/{key}/manifest.json", {**p.model_dump(), "creado": time.time()})
    return {"id": key, "tamano_parte": CHUNK}


def upload_metadata(key):
    metadata = svc.STORE.json(f"cargas/{storage_id(key)}/manifest.json")
    if metadata is None or time.time() - metadata["creado"] > 3600:
        raise ValueError("La carga expiró; selecciona el archivo de nuevo")
    return metadata


@router.put("/archivos/{key}/partes/{part}")
async def upload_part(key: str, part: int, request: Request):
    metadata = await run_in_threadpool(upload_metadata, key)
    offset = part * CHUNK
    if part < 0 or offset >= metadata["bytes"]:
        raise ValueError("Parte de archivo inválida")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > CHUNK:
            raise ValueError("La parte supera el tamaño permitido")
    if len(body) != min(CHUNK, metadata["bytes"] - offset):
        raise ValueError("La parte del archivo está incompleta")
    await run_in_threadpool(svc.STORE.write, f"cargas/{key}/{part}.bin", bytes(body))
    return {"recibida": part}


@router.post("/archivos/{key}/analizar")
def analyze_upload(key: str):
    metadata = upload_metadata(key)
    ready = svc.STORE.json(f"cargas/{key}/resultado.json")
    if ready:
        return ready
    parts = []
    for part in range((metadata["bytes"] + CHUNK - 1) // CHUNK):
        value = svc.STORE.read(f"cargas/{key}/{part}.bin")
        if value is None:
            raise ValueError("Faltan partes del archivo; vuelve a cargarlo")
        parts.append(value)
    raw = b"".join(parts)
    if len(raw) != metadata["bytes"] or hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("El archivo recibido no coincide con el original")
    result = {"tablas": [save_table(frame, name, metadata["nombre"]) for name, frame in parse_file(raw, metadata["nombre"])]}
    svc.STORE.write_json(f"cargas/{key}/resultado.json", result)
    # La tabla normalizada ya es persistente; liberar las partes temporales.
    for part in range(len(parts)):
        svc.STORE.delete(f"cargas/{key}/{part}.bin")
    return result


class Union(Modelo):
    tabla: str = Field(pattern=r"^[a-f0-9]{32}$")
    izquierda: str = Field(min_length=1, max_length=120)
    derecha: str = Field(min_length=1, max_length=120)


class Preparar(Modelo):
    principal: str = Field(pattern=r"^[a-f0-9]{32}$")
    id_columna: str = Field(min_length=1, max_length=120)
    uniones: list[Union] = Field(default_factory=list, max_length=9)


def propose_config(frame):
    columns = set(frame.columns)
    scores = {column["nombre"] for column in profile(frame) if column["score"]}
    channel_scores = {name.removeprefix("score_canal_"): name for name in frame if name.startswith("score_canal_") and name in scores}
    products = [name for name in frame if name.startswith("score_") and not name.startswith("score_canal_") and name in scores]
    warnings = []
    channels = list(channel_scores)[:20]
    campaigns = []
    for index, column in enumerate(products[:20]):
        existing = next((deepcopy(c) for c in svc.RETO["campanas"] if c["columna_score"] == column), None)
        campaigns.append(existing or {"id": f"C-DATOS-{index + 1}", "nombre": column.removeprefix("score_").replace("_", " ").capitalize(),
                                     "producto": column.removeprefix("score_").upper()[:64], "objetivo": "Oferta de la base cargada",
                                     "columna_score": column, "valor_negocio": 1, "canales_permitidos": channels,
                                     "vigencia_inicio": "2000-01-01", "vigencia_fin": "2099-12-31", "activa": True})
    for campaign in campaigns:
        campaign["canales_permitidos"] = [channel for channel in campaign["canales_permitidos"] if channel in channels]
    campaign_ids = {campaign["id"] for campaign in campaigns}
    rules, missing = [], []
    for rule in svc.RETO["reglas"]:
        scope = rule["alcance"]
        available = condition_columns(rule["condicion"]) <= columns
        applies = scope["nivel"] == "global" or (scope["nivel"] == "campana" and set(scope["valores"]) <= campaign_ids) or (scope["nivel"] == "canal" and set(scope["valores"]) <= set(channels))
        if available and applies:
            rules.append(deepcopy(rule))
        elif not available:
            missing.append(rule["nombre"])
    if missing:
        warnings.append("Reglas del reto sin datos suficientes: " + "; ".join(missing) + ". Revisa las reglas de esta base antes de ejecutar.")
    week = "contactos_semana_actual" if "contactos_semana_actual" in columns else ""
    if not week:
        warnings.append("Selecciona la columna de contactos semanales. Este límite necesita datos; no se asumen ceros.")
    if not channels or not campaigns:
        warnings.append("Asigna al menos una columna de probabilidad de producto y una de canal. Sus valores deben estar entre 0 y 1.")
    params = deepcopy(svc.RETO["parametros"])
    params["priorizacion"]["jerarquia"] = [campaign["id"] for campaign in campaigns]
    params["canal"]["columnas_score"] = {channel: channel_scores[channel] for channel in channels}
    params["canal"]["orden_preferencia"] = channels
    params["canal"]["capacidad_por_corrida"] = {channel: min(len(frame), svc.RETO["parametros"]["canal"]["capacidad_por_corrida"].get(channel, 0)) for channel in channels}
    params["politica_contacto"]["max_productos_por_canal"] = {channel: svc.RETO["parametros"]["politica_contacto"]["max_productos_por_canal"].get(channel, 1) for channel in channels}
    params["politica_contacto"]["columna_contactos_semana"] = week
    if any(channel not in svc.RETO["parametros"]["canal"]["capacidad_por_corrida"] for channel in channels):
        warnings.append("Los canales nuevos empiezan con cupo cero. Define su capacidad antes de asignar contactos.")
    return {"campanas": campaigns, "reglas": rules, "parametros": params}, warnings


@router.post("/preparar")
def prepare(p: Preparar):
    principal, frame = load_table(p.principal)
    if p.id_columna not in frame or frame[p.id_columna].eq("").any() or not frame[p.id_columna].is_unique:
        raise ValueError("La columna de cliente debe existir y tener un identificador único no vacío por fila")
    sources = [principal]
    seen = {p.principal}
    for join in p.uniones:
        if join.tabla in seen:
            raise ValueError("Una tabla no puede incorporarse dos veces")
        seen.add(join.tabla)
        metadata, right = load_table(join.tabla)
        if join.izquierda not in frame or join.derecha not in right:
            raise ValueError("La columna de unión no existe")
        if not right[join.derecha].is_unique or right[join.derecha].eq("").any():
            raise ValueError(f"{metadata['nombre']}: la clave de unión tiene duplicados o vacíos. Agrega los eventos por cliente antes de unir.")
        overlap = (set(right.columns) - {join.derecha}) & set(frame.columns)
        for column in overlap:
            right = right.rename(columns={column: f"{slug(metadata['nombre'])[:30]}_{column}"[:120]})
        key_column = f"__union_{len(sources)}"
        right = right.rename(columns={join.derecha: key_column})
        if len(set(right.columns)) != len(right.columns) or ((set(right.columns) - {key_column}) & set(frame.columns)):
            raise ValueError("Los nombres de columnas se repiten al unir tablas")
        if frame[join.izquierda].eq("").any() or not frame[join.izquierda].isin(right[key_column]).all():
            raise ValueError(f"{metadata['nombre']}: faltan coincidencias para algunos clientes. Completa la tabla antes de unir.")
        frame = frame.merge(right, how="left", left_on=join.izquierda, right_on=key_column, validate="many_to_one", sort=False).drop(columns=[key_column])
        if len(frame.columns) > MAX_COLUMNS:
            raise ValueError(f"La base unida admite hasta {MAX_COLUMNS} columnas")
        sources.append(metadata)
    if p.id_columna != "id_cliente":
        if "id_cliente" in frame:
            raise ValueError("La base ya tiene id_cliente; selecciónala como identificador")
        frame = frame.rename(columns={p.id_columna: "id_cliente"})
    key = uuid4().hex
    raw = frame.to_csv(index=False).encode()
    config, warnings = propose_config(frame)
    metadata = {"id": key, "nombre": principal["nombre"], "clientes": len(frame), "columnas": profile(frame),
                "fuentes": [{"id": item["id"], "nombre": item["nombre"], "filas": item["filas"]} for item in sources],
                "datos_sha256": hashlib.sha256(raw).hexdigest(), "config": config, "avisos": warnings}
    svc.STORE.write(f"bases/{key}/datos.csv.gz", gzip.compress(raw), "application/gzip")
    svc.STORE.write_json(f"bases/{key}/manifest.json", metadata)
    return metadata


def load_base(key):
    key = storage_id(key)
    metadata = svc.STORE.json(f"bases/{key}/manifest.json")
    raw = svc.STORE.read(f"bases/{key}/datos.csv.gz")
    if metadata is None or raw is None:
        raise FileNotFoundError("La base no está disponible; vuelve a prepararla")
    return metadata, pd.read_csv(io.BytesIO(raw), compression="gzip", dtype=str, keep_default_na=False)


@router.get("/bases/{key}")
def get_base(key: str):
    metadata, _ = load_base(key)
    return metadata


@router.post("/bases/{key}/simular")
def simulate(key: str, p: Pedido):
    metadata, frame = load_base(key)
    config = diccionario(p.config)
    return svc.public(svc.simulate(config, p.fecha.isoformat(), data=frame, data_hash=metadata["datos_sha256"],
                                   dataset={"id": metadata["id"], "nombre": metadata["nombre"], "fuentes": metadata["fuentes"]}))

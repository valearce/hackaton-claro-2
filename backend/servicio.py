"""Orquestación del motor único, caché acotada y artefactos persistentes."""
from collections import OrderedDict
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

import numpy as np
import pandas as pd

from modelo.nba import Engine, load_config, validate_grid
from modelo.optimizacion.problema import NUMBER_COLUMNS, TEXT_COLUMNS, canonical_hash
if __package__:
    from .almacen import Almacen
    from .esquemas import Configuracion, diccionario
else:
    from almacen import Almacen
    from esquemas import Configuracion, diccionario

SERVICE = Path(__file__).resolve().parent
ROOT = SERVICE if (SERVICE / "modelo").is_dir() else SERVICE.parent
DATA_PATH = ROOT / "datos/clientes.csv"
DATA = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
DATA_HASH = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
RETO = diccionario(Configuracion.model_validate(load_config(ROOT / "modelo/config")))
REFERENCE = json.loads((SERVICE / "referencia.json").read_text(encoding="utf-8"))["referencia"]
REVISION = hashlib.sha256(b"".join((ROOT / name).read_bytes().replace(b"\r\n", b"\n") for name in (
    "modelo/nba/motor.py", "modelo/optimizacion/problema.py", "modelo/optimizacion/solvers.py", "modelo/optimizacion/certificado.py"))).hexdigest()
STORE = Almacen(SERVICE.parent)
LOCK = threading.Lock()
CACHE_LOCK = threading.RLock()
CACHE = OrderedDict()
CACHE_SIZE, CACHE_TTL = 3, 900
GRID_CACHE = OrderedDict()
NOMBRES = {"R01":"Sin mora", "R02":"Terminales: calificación permitida", "R03":"Equipo de 18 meses o más",
    "R04":"Hogar solo si no lo tiene", "R05":"Disponibilidad OTT", "R06":"Sin repetir oferta del mes",
    "R07":"Límite de quejas", "R08":"Score mínimo de producto", "R09":"Autorización del canal",
    "R10":"Límite de llamadas", "R11":"Score mínimo de canal", "R12":"Canales permitidos",
    "R13":"Un canal por cliente", "R14":"Productos por contacto", "R15":"Límite semanal", "R16":"Cupos por canal"}


def now():
    return datetime.now(timezone.utc).isoformat()


def column_types():
    result = {}
    for name in DATA.columns:
        numeric = name in NUMBER_COLUMNS or name.startswith("score_")
        if not numeric and name not in TEXT_COLUMNS:
            try:
                pd.to_numeric(DATA[name], errors="raise")
                numeric = True
            except (ValueError, TypeError):
                pass
        result[name] = "numero" if numeric else "texto"
    return result


TYPES = column_types()


def check_conditions(config):
    def check(condition, depth=0):
        if depth > 4:
            raise ValueError("Las condiciones permiten hasta cuatro niveles")
        for key in ("todas", "alguna"):
            if key in condition:
                for child in condition[key]: check(child, depth+1)
                return
        column = condition["atributo"]
        if column not in TYPES:
            raise ValueError(f"La columna {column} no existe en la base")
        values = condition["valor"] if isinstance(condition["valor"], list) else [condition["valor"]]
        if TYPES[column] == "numero":
            for value in values:
                try: float(value)
                except (ValueError, TypeError): raise ValueError(f"La columna {column} necesita valores numéricos")
        elif condition["operador"] in ("<", "<=", ">", ">=") or any(not isinstance(x, str) for x in values):
            raise ValueError(f"La columna {column} es de texto: usa igualdad, listas o contiene")
    for rule in config["reglas"]:
        if rule["activa"]: check(rule["condicion"])
    for column in [c["columna_score"] for c in config["campanas"]] + list(config["parametros"]["canal"]["columnas_score"].values()):
        if column not in TYPES or TYPES[column] != "numero":
            raise ValueError(f"La columna de score {column} debe existir y ser numérica")


def cached(key):
    with CACHE_LOCK:
        record = CACHE.get(key)
        if record and record[0] > time.monotonic():
            CACHE.move_to_end(key)
            return record[1]
        CACHE.pop(key, None)
    return None


def remember(key, record):
    with CACHE_LOCK:
        CACHE[key] = (time.monotonic()+CACHE_TTL, record)
        CACHE.move_to_end(key)
        while len(CACHE) > CACHE_SIZE: CACHE.popitem(last=False)
    return record


def load_run(key):
    record = cached(key) or STORE.json(f"corridas/{key}/manifest.json")
    if record is None: raise FileNotFoundError("La simulación no existe")
    return remember(key, record)


def summary(grid, config, date, info, seconds):
    own = validate_grid(DATA, grid, config, date)
    original = own if config == RETO else validate_grid(DATA, grid, RETO, date)
    if own["violaciones"]:
        raise ValueError("La parrilla incumple su configuración; no se guarda")
    counts = pd.concat([grid.campana_1, grid.campana_2]); counts = counts[counts != ""].value_counts().to_dict()
    return {"valor_esperado": float(info["certificado"]["valor_esperado_exacto"]),
        "clientes": own["clientes_con_accion"], "total_clientes": len(DATA), "productos": own["productos_asignados"],
        "jerarquia": own["indicador_jerarquia"], "violaciones": own["violaciones"], "violaciones_reto": original["violaciones"],
        "exceso_cupos_reto": original["exceso_cupos"],
        "controles_reto": [{"control": k, "nombre": NOMBRES.get(k,k), "violaciones": v} for k,v in original["controles"].items()],
        "canales": [{"canal": c,"cupo": v,"uso": own["uso_canales"][c]} for c,v in config["parametros"]["canal"]["capacidad_por_corrida"].items()],
        "campanas": [{"id": c["id"],"ofertas": int(counts.get(c["id"],0))} for c in config["campanas"]],
        "segundos_motor": info["segundos"], "segundos": round(seconds,3),
        "certificado": info["certificado"], "objetivo": info["objetivo"]}


def simulate(config, date):
    check_conditions(config)
    key = canonical_hash({"config":config,"fecha":date,"datos":DATA_HASH,"motor":REVISION})[:32]
    record = cached(key) or STORE.json(f"corridas/{key}/manifest.json")
    if record: return remember(key,record)
    if not LOCK.acquire(timeout=30): raise TimeoutError("Hay otra simulación en curso; vuelve a intentarlo")
    try:
        record = cached(key) or STORE.json(f"corridas/{key}/manifest.json")
        if record: return remember(key,record)
        started=time.perf_counter()
        engine=Engine(DATA,config,date,DATA_HASH)
        grid,info=engine.optimize()
        result=summary(grid,config,date,info,time.perf_counter()-started)
        csv=gzip.compress(grid.to_csv(index=False).encode(),mtime=0)
        proof=gzip.compress(json.dumps(engine.certificate,separators=(",", ":")).encode(),mtime=0)
        STORE.write(f"corridas/{key}/parrilla.csv.gz",csv,"application/gzip")
        STORE.write(f"corridas/{key}/certificado.json.gz",proof,"application/gzip")
        result["segundos"]=round(time.perf_counter()-started,3)
        record={"id":key,"creado":now(),"fecha":date,"config":config,"datos_sha256":DATA_HASH,"motor_sha256":REVISION,
                "commit":os.environ.get("VERCEL_GIT_COMMIT_SHA"),"metodos":{"optimo":result},"referencia":REFERENCE}
        STORE.write_json(f"corridas/{key}/manifest.json",record)
        return remember(key,record)
    finally:
        LOCK.release()


def public(record):
    return {key: value for key,value in record.items() if key != "config"}


def grid_for(key):
    load_run(key)
    with CACHE_LOCK:
        current=GRID_CACHE.get(key)
        if current and current[0] > time.monotonic(): return current[1]
    raw=STORE.read(f"corridas/{key}/parrilla.csv.gz")
    if raw is None: raise FileNotFoundError("La parrilla no está disponible")
    grid=pd.read_csv(io.BytesIO(raw),compression="gzip",dtype=str,keep_default_na=False)
    with CACHE_LOCK:
        GRID_CACHE.clear();GRID_CACHE[key]=(time.monotonic()+120,grid)
    return grid


def save_version(config,date,name):
    record=simulate(config,date)
    key=datetime.now(timezone.utc).strftime("v%Y%m%dT%H%M%S")+"-"+uuid4().hex[:12]
    version={"version":key,"nombre":name,"creado":now(),"fecha":date,"config":config,"corrida":record["id"],
             "datos_sha256":DATA_HASH,"motor_sha256":REVISION,"resultado":record["metodos"]["optimo"]}
    STORE.write_json(f"versiones/{key}.json",version)
    return version


def versions():
    paths=sorted(STORE.keys("versiones/"),reverse=True)[:50]
    return [item for path in paths if (item:=STORE.json(path)) is not None]


def version(key):
    item=STORE.json(f"versiones/{key}.json")
    if item is None: raise FileNotFoundError("La versión no existe")
    return item


def active():
    pointer=STORE.json("activa.json")
    return version(pointer["version"]) if pointer else None


# ---- Plus: desglose por cluster (los clusters salen de modelo.experimentos.exportar_app) ----
CLUSTERS_PATH = SERVICE / "datos/clusters.csv" if (SERVICE / "datos/clusters.csv").is_file() else ROOT / "datos/clusters.csv"
_CLUSTERS = {}


def cluster_codes():
    if "c" not in _CLUSTERS:
        if not CLUSTERS_PATH.is_file():
            raise FileNotFoundError("No hay clusters: falta datos/clusters.csv (python -m modelo.experimentos.exportar_app --web .)")
        table = pd.read_csv(CLUSTERS_PATH, dtype=str, keep_default_na=False).set_index("id_cliente").reindex(DATA.id_cliente)
        if table.cluster.eq("").any() or table.cluster.isna().any():
            raise ValueError("datos/clusters.csv no cubre todos los clientes")
        names = sorted(table.cluster.unique())
        _CLUSTERS["c"] = (names, pd.Categorical(table.cluster.to_numpy(), categories=names).codes)
    return _CLUSTERS["c"]


def score(column):
    if column not in _CLUSTERS:
        _CLUSTERS[column] = DATA[column].astype(float).to_numpy()
    return _CLUSTERS[column]


def by_cluster(key):
    """Qué hizo la corrida en cada cluster: valor esperado (score producto x score canal x valor), clientes, ofertas y canales."""
    record = load_run(key)
    cached_result = record.get("clusters")
    if cached_result:
        return cached_result
    config = record["config"]
    names, code = cluster_codes()
    n = len(names)
    grid = grid_for(key).set_index("id_cliente").reindex(DATA.id_cliente)
    channels = list(config["parametros"]["canal"]["capacidad_por_corrida"])
    channel_index = grid.canal.map({c: i for i, c in enumerate(channels)}).fillna(-1).to_numpy(int)
    channel_scores = np.column_stack([score(config["parametros"]["canal"]["columnas_score"][c]) for c in channels])
    assigned = (grid.estado == "asignado").to_numpy()
    rows = np.arange(len(grid))
    value = np.zeros(len(grid))
    offers = {}
    for campaign in config["campanas"]:
        picked = ((grid.campana_1 == campaign["id"]) | (grid.campana_2 == campaign["id"])).to_numpy() & assigned & (channel_index >= 0)
        offers[campaign["id"]] = np.bincount(code, weights=picked.astype(float), minlength=n)
        value[picked] += score(campaign["columna_score"])[picked] * channel_scores[rows[picked], channel_index[picked]] * campaign["valor_negocio"]
    per_value = np.bincount(code, weights=value, minlength=n)
    acting = np.bincount(code, weights=assigned.astype(float), minlength=n)
    size = np.bincount(code, minlength=n)
    used = {c: np.bincount(code, weights=(grid.canal == c).to_numpy().astype(float), minlength=n) for c in channels}
    result = {"clusters": [{"id": names[i], "clientes": int(size[i]), "con_accion": int(acting[i]), "valor": float(per_value[i]),
                            "ofertas": {k: int(v[i]) for k, v in offers.items()}, "canales": {k: int(v[i]) for k, v in used.items()}}
                           for i in range(n)],
              "total": {"valor": float(per_value.sum()), "con_accion": int(acting.sum())}}
    return result

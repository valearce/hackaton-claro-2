"""Conserva los CSV oficiales y crea una configuración inicial editable."""
from pathlib import Path, PurePosixPath
import csv
import io
import json
import re
import zipfile
from .rutas import KIT_OFICIAL

MODEL = Path(__file__).resolve().parent


def scalar(value):
    if "|" in value:
        return value.split("|")
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def main():
    original = MODEL / "kit_original"
    config = MODEL / "config"
    original.mkdir(exist_ok=True)
    config.mkdir(exist_ok=True)
    with zipfile.ZipFile(KIT_OFICIAL) as archive:
        for item in archive.infolist():
            if item.filename.endswith(".csv"):
                target = original / PurePosixPath(item.filename).name
                if not target.exists():
                    target.write_bytes(archive.read(item))

    def rows(name):
        return list(csv.DictReader(io.StringIO((original / name).read_text(encoding="utf-8-sig"))))

    campaigns = rows("config_campanas.csv")
    for campaign in campaigns:
        campaign["valor_negocio"] = float(campaign["valor_negocio"])
        campaign["canales_permitidos"] = campaign["canales_permitidos"].split("|")
        campaign["activa"] = campaign["activa"] == "1"
    controls = {"R08": "R09", "R09": "R09", "R10": "R09", "R11": "R10"}
    rules = []
    for row in rows("config_reglas.csv"):
        rules.append({
            "id": row["id"], "control": controls.get(row["id"], row["id"]),
            "nombre": row["nombre"], "tipo": row["tipo"],
            "alcance": {"nivel": row["alcance_nivel"], "valores": row["alcance_valores"].split("|") if row["alcance_valores"] else []},
            "condicion": {"atributo": row["atributo"], "operador": row["operador"], "valor": scalar(row["valor"])},
            "accion": row["accion"], "activa": row["activa"] == "1",
        })
    parameters = {}
    for row in rows("config_parametros.csv"):
        location = parameters
        parts = row["parametro"].split(".")
        for part in parts[:-1]:
            location = location.setdefault(part, {})
        location[parts[-1]] = scalar(row["valor"])
    parameters["canal"]["columnas_score"] = {
        channel: f"score_canal_{channel}" for channel in parameters["canal"]["capacidad_por_corrida"]
    }
    parameters["optimizacion"] = {"backend": "flujo_ortools", "objetivo": "valor_esperado"}
    parameters["priorizacion"]["modos_disponibles"] = ["ponderado", "jerarquia_estricta"]
    profiles = {
        "semilla": 42, "fraccion_train": 0.7, "fraccion_validacion": 0.15,
        "numericas": ["edad", "antiguedad_meses", "plan_datos_gb", "consumo_datos_pct", "arpu_movil", "arpu_hogar", "edad_equipo_meses"],
        "binarias": ["tiene_hogar", "tiene_netflix", "tiene_amazon_prime", "tiene_win", "usa_redes_sociales", "usa_banca_digital", "compras_digitales"],
        "categoricas": ["tipo_linea", "gama_equipo"],
        "log1p": ["arpu_movil", "arpu_hogar"], "plan_ilimitado": {"columna": "plan_datos_gb", "valor": 999},
        "capas": [32, 16], "dimension_latente": 5, "epocas": 50, "paciencia": 7,
        "batch_size": 1024, "learning_rate": 0.001, "weight_decay": 0.0001,
        "hilos_cpu": 4, "segmentos": 5, "muestra_silhouette": 2000,
    }
    for name, content in [("campanas.json", campaigns), ("reglas.json", rules), ("parametros.json", parameters), ("perfiles.json", profiles)]:
        target = config / name
        if target.exists():
            raise FileExistsError(f"No se sobrescribe una configuración existente: {target}")
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Configuración inicial creada a partir del kit oficial.")


if __name__ == "__main__":
    main()

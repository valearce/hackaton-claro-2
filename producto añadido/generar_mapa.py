"""Build a single HTML with official block geometry and aggregated CSV data.

Core generation uses the standard library; first network-layer download needs
Pillow. Run with --actualizar to refresh official geometry.
No customer is assigned an invented address or block.
"""

import argparse
import base64
import concurrent.futures
import csv
import gzip
import hashlib
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICE = "https://sinu.sdp.gov.co/serverp/rest/services/ESTRATO/Estratificacion/FeatureServer/2"
CACHE = ROOT / ".cache" / "manzanas.json.gz"


def request(params):
    url = SERVICE + "/query?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BogotaEstratos/1.0"})
            with urllib.request.urlopen(req, timeout=45) as response:
                result = json.load(response)
            if result.get("error"):
                raise ValueError(str(result["error"]))
            return result
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def download_geometry():
    expected_ids = request({"where": "1=1", "returnIdsOnly": "true", "f": "json"})["objectIds"]
    # Short paginated URLs avoid the public IIS service's query-string limit.
    batches = list(range(0, len(expected_ids), 1000))

    def batch(offset):
        result = request({
            "where": "1=1", "resultOffset": str(offset), "resultRecordCount": "1000",
            "orderByFields": "OBJECTID ASC",
            "outFields": "OBJECTID,CODIGO_MANZANA,ESTRATO,NORMATIVA,FECHA_ACTO",
            "returnGeometry": "true", "outSR": "4326", "geometryPrecision": "6",
            "maxAllowableOffset": "0.000005", "f": "geojson",
        })
        features = result.get("features", [])
        if len(features) != min(1000, len(expected_ids) - offset):
            raise ValueError("La respuesta del servicio no contiene la pagina completa.")
        return features

    features = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for index, chunk in enumerate(pool.map(batch, batches), 1):
            features.extend(chunk)
            if index % 15 == 0 or index == len(batches):
                print(f"Geometria oficial: {len(features):,}/{len(expected_ids):,}", flush=True)
    features.sort(key=lambda f: int(f["properties"]["OBJECTID"]))
    actual_ids = [int(f["properties"]["OBJECTID"]) for f in features]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids):
        raise ValueError("La capa cambio durante la descarga o no se descargaron todas las manzanas; vuelve a ejecutarlo.")
    for feature in features:
        props = feature["properties"]
        feature["id"] = int(props["OBJECTID"])
        value = str(props.get("ESTRATO", "")).strip()
        props["estrato"] = int(value) if value in {"1", "2", "3", "4", "5", "6"} else 0
        props["manzana"] = str(props.get("CODIGO_MANZANA") or "Sin codigo")
    snapshot = {
        "downloadedAt": datetime.now(timezone.utc).isoformat(),
        "source": SERVICE,
        "geojson": {"type": "FeatureCollection", "features": features},
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(CACHE, "wt", encoding="utf-8") as stream:
        json.dump(snapshot, stream, ensure_ascii=False, separators=(",", ":"))
    return snapshot


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).strip().casefold()


def aggregate_csv(path):
    buckets = {str(i): {"clientes": 0, "sin_hogar": 0, "arpu_total": 0, "consumo_total": 0.0} for i in range(1, 7)}
    total = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id_cliente", "region", "estrato", "tiene_hogar", "arpu_movil", "consumo_datos_pct"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Columnas ausentes: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            total += 1
            if normalize(row["region"]) != "bogota":
                continue
            bucket = buckets[row["estrato"]]
            bucket["clientes"] += 1
            bucket["sin_hogar"] += int(row["tiene_hogar"]) == 0
            bucket["arpu_total"] += int(row["arpu_movil"])
            bucket["consumo_total"] += float(row["consumo_datos_pct"])
    for bucket in buckets.values():
        bucket["consumo_total"] = round(bucket["consumo_total"], 4)
    return {
        "file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "total": total, "bogota": sum(b["clientes"] for b in buckets.values()), "byStratum": buckets,
        "scope": "Clientes sinteticos de Bogota, agregados por estrato; sin localizacion individual.",
    }


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actualizar", action="store_true", help="Volver a descargar las manzanas oficiales")
    parser.add_argument("--actualizar-red", action="store_true", help="Actualizar recortes publicos de cobertura Claro y sitios CRC")
    parser.add_argument("--csv", type=Path, default=ROOT.parent / "clientes 1.csv")
    args = parser.parse_args()
    if args.actualizar or not CACHE.exists():
        snapshot = download_geometry()
    else:
        with gzip.open(CACHE, "rt", encoding="utf-8") as stream:
            snapshot = json.load(stream)
    features = snapshot["geojson"]["features"]
    if len({f["id"] for f in features}) != len(features):
        raise ValueError("Hay identificadores geograficos duplicados.")
    clients = aggregate_csv(args.csv.resolve())
    from capas_red import load_layers
    network = load_layers(refresh=args.actualizar_red)
    metadata = {
        "downloadedAt": snapshot["downloadedAt"], "source": SERVICE,
        "blocks": len(features), "blocksByStratum": dict(Counter(str(f["properties"]["estrato"]) for f in features)),
        "csv": clients,
    }
    raw = safe_json(snapshot["geojson"]).encode("utf-8")
    encoded = base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")
    style = json.loads((ROOT / "estilo-base.json").read_text(encoding="utf-8-sig"))
    template = (ROOT / "mapa.template.html").read_text(encoding="utf-8")
    logo = "data:image/jpeg;base64," + base64.b64encode((ROOT / "Claro_Logo.jpg").read_bytes()).decode("ascii")
    html = template.replace("__META_JSON__", safe_json(metadata)).replace("__STYLE_JSON__", safe_json(style)).replace("__GEO_GZIP_BASE64__", encoded).replace("__CLARO_LOGO_DATA_URL__", logo).replace("__NETWORK_JSON__", safe_json(network))
    output = ROOT / "mapa-estratos-bogota.html"
    output.write_text(html, encoding="utf-8")
    print(json.dumps({"html": str(output), "bytes": output.stat().st_size, "manzanas": len(features), "csv_total": clients["total"], "csv_bogota": clients["bogota"], "clientes_por_estrato": {k: b["clientes"] for k, b in clients["byStratum"].items()}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()


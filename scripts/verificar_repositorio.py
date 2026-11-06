"""Comprueba fuentes reubicadas, evaluaciones y enlaces Markdown locales."""
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    checked = 0
    for manifest_path in (ROOT / "datos/manifest.json", ROOT / "docs/reto/manifest.json"):
        for item in read_json(manifest_path)["archivos"]:
            path = (ROOT / item["ruta"]).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f"Fuente ausente o fuera del repositorio: {item['ruta']}")
            if path.stat().st_size != item["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"Cambió una fuente original: {item['ruta']}")
            checked += 1
    dataset = read_json(ROOT / "datos/manifest.json")
    with (ROOT / "datos/clientes.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        columns = len(next(reader))
        rows = sum(1 for _ in reader)
    if (rows, columns) != (dataset["filas"], dataset["columnas"]):
        raise ValueError("Dimensiones del CSV diferentes al manifiesto")
    for task in ("nba", "perfiles", "comparacion"):
        metrics = read_json(ROOT / "modelo/evaluacion" / f"{task}.json")
        if metrics["datos_sha256"] != dataset["archivos"][0]["sha256"]:
            raise ValueError(f"Evaluación {task}: huella del CSV diferente")
        if task == "nba":
            config = {key: read_json(ROOT / "modelo/config" / f"{key}.json") for key in ("campanas", "reglas", "parametros")}
        else:
            config = read_json(ROOT / "modelo/config" / f"{task}.json")
        if metrics["configuracion"] != config:
            raise ValueError(f"Evaluación {task}: configuración distinta de la evaluada")
    markdown = [ROOT / "README.md", ROOT / "CONTRIBUTING.md"]
    for folder in ("datos", "docs", "modelo", "mapa", "investigacion", "recursos", "herramientas"):
        markdown.extend(path for path in (ROOT / folder).rglob("*.md")
                        if "referencias-qnexus" not in path.parts and "resultados" not in path.parts)
    links = 0
    optional = ROOT / "investigacion/estudios"
    for path in markdown:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8-sig")):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            relative = unquote(target.split("#", 1)[0].strip("<>"))
            destination = (path.parent / relative).resolve()
            if destination.is_relative_to(optional):
                continue  # Copias locales; el catálogo ofrece las fuentes públicas.
            if not destination.is_relative_to(ROOT) or not destination.exists():
                raise ValueError(f"Enlace roto en {path.relative_to(ROOT)}: {target}")
            links += 1
    print(f"OK: {checked} fuentes originales, CSV {rows} x {columns}, 3 evaluaciones y {links} enlaces locales.")


if __name__ == "__main__":
    main()

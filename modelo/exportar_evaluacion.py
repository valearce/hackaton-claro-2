"""Copia solo métricas y gráfico verificables a la evaluación versionada."""
import hashlib
import json
from pathlib import Path
import shutil

from .ejecutar import write_json
from .nba import load_config
from .rutas import DATOS


def main():
    model = Path(__file__).resolve().parent
    fingerprint = hashlib.sha256(DATOS.read_bytes()).hexdigest()
    output = model / "evaluacion"
    reports = {}
    for task in ("nba", "perfiles", "comparacion"):
        report = json.loads((model / "resultados" / task / "metricas.json").read_text(encoding="utf-8"))
        if report.get("datos_sha256") != fingerprint:
            raise ValueError(f"{task}: los resultados no corresponden a los datos actuales")
        if task == "nba":
            if report["configuracion"] != load_config():
                raise ValueError("NBA: configuración distinta de la evaluada")
        else:
            configuration = json.loads((model / "config" / f"{task}.json").read_text(encoding="utf-8-sig"))
            if report["configuracion"] != configuration:
                raise ValueError(f"{task}: configuración distinta de la evaluada")
        reports[task] = report
    optimizer = model / "resultados/optimizador/metricas.json"
    if optimizer.exists():
        report = json.loads(optimizer.read_text(encoding="utf-8"))
        if report.get("datos_sha256") != fingerprint or report.get("configuracion") != load_config():
            raise ValueError("Optimizador: datos o configuración distintos de los evaluados")
        current_code = {
            path.relative_to(model.parent).as_posix(): hashlib.sha256(
                path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for path in sorted(model.rglob("*.py")) if "resultados" not in path.parts
        }
        if report.get("normalizacion_codigo") != "LF" or report.get("codigo_sha256") != current_code:
            raise ValueError("Optimizador: el código cambió después del benchmark")
        results = report.get("resultados", {})
        if not results or any(
            not item.get("optimo_exacto") or item.get("brecha_exacta") != "0" or item.get("violaciones") != 0
            for item in results.values()
        ):
            raise ValueError("Optimizador: falta optimalidad exacta o hay violaciones")
        reports["optimizador"] = report
    output.mkdir(parents=True, exist_ok=True)
    for task, report in reports.items():
        write_json(output / f"{task}.json", report)
    for name in ("comparacion.csv", "comparacion_metodos.png"):
        shutil.copyfile(model / "resultados/comparacion" / name, output / name)
    print(f"Evaluación exportada a {output}")


if __name__ == "__main__":
    main()

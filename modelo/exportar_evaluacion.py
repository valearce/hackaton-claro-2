"""Copia solo métricas y gráfico verificables a la evaluación versionada."""
import hashlib
import json
from pathlib import Path
import shutil

from .ejecutar import ROOT, write_json
from .nba import load_config


def main():
    model = Path(__file__).resolve().parent
    fingerprint = hashlib.sha256((ROOT / "clientes 1.csv").read_bytes()).hexdigest()
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
    output.mkdir(parents=True, exist_ok=True)
    for task, report in reports.items():
        write_json(output / f"{task}.json", report)
    for name in ("comparacion.csv", "comparacion_metodos.png"):
        shutil.copyfile(model / "resultados/comparacion" / name, output / name)
    print(f"Evaluación exportada a {output}")


if __name__ == "__main__":
    main()

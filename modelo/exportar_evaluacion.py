"""Exporta las métricas vigentes del motor NBA y los perfiles guardados."""
import hashlib
import json
from pathlib import Path

from .ejecutar import write_json
from .nba import load_config
from .rutas import DATOS


def main():
    model = Path(__file__).resolve().parent
    fingerprint = hashlib.sha256(DATOS.read_bytes()).hexdigest()
    output = model / "evaluacion"
    reports = {}
    for task in ("nba", "perfiles"):
        source = model / "resultados" / task / "metricas.json"
        if task == "perfiles" and not source.exists():
            continue
        report = json.loads(source.read_text(encoding="utf-8"))
        if report.get("datos_sha256") != fingerprint:
            raise ValueError(f"{task}: los resultados no corresponden a los datos actuales")
        if task == "nba":
            if report["configuracion"] != load_config():
                raise ValueError("NBA: configuración distinta de la evaluada")
            proof = report["optimo"]["ejecucion"]["certificado"]
            if report.get("backend") != "flujo_ortools" or not proof["optimo_exacto"] or proof["brecha_exacta"] != "0" or report["optimo"]["violaciones"]:
                raise ValueError("NBA: se exige flujo certificado sin violaciones")
            current_code = {
                path.relative_to(model.parent).as_posix(): hashlib.sha256(
                    path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                for path in sorted(model.rglob("*.py")) if "resultados" not in path.parts
            }
            if report.get("codigo_sha256") != current_code:
                raise ValueError("NBA: el código cambió después de ejecutar el motor")
        else:
            configuration = json.loads((model / "config" / f"{task}.json").read_text(encoding="utf-8-sig"))
            if report["configuracion"] != configuration:
                raise ValueError(f"{task}: configuración distinta de la evaluada")
        reports[task] = report
    output.mkdir(parents=True, exist_ok=True)
    for task, report in reports.items():
        write_json(output / f"{task}.json", report)
    print(f"Evaluación exportada a {output}")


if __name__ == "__main__":
    main()

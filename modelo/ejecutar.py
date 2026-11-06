"""Ejecución reproducible del motor y de los perfiles exploratorios."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy
import sys

from .nba import CONFIG, Engine, load_config, validate_grid
from .optimizacion.certificado import save_certificate
from .rutas import DATOS, MODELO, RAIZ as ROOT



def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_nba(data, config, directory, day, datos_sha256=None):
    directory.mkdir(parents=True, exist_ok=True)
    print(f"NBA: flujo OR-Tools para {len(data):,} clientes", flush=True)
    engine = Engine(data, config, day, datos_sha256)
    grid, solver = engine.optimize()
    audit = validate_grid(data, grid, config, day)
    if audit["violaciones"]:
        write_json(directory / "errores_optimo.json", audit)
        raise RuntimeError(f"Hay {audit['violaciones']} violaciones; no se exporta la parrilla")
    grid.to_csv(directory / "parrilla_optimo.csv", index=False, encoding="utf-8")
    save_certificate(directory / "certificado.json.gz", engine.certificate)
    optimum = float(solver["certificado"]["valor_esperado_exacto"])
    reports = {
        "backend": "flujo_ortools", "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "optimo": {**audit, "valor_esperado_exacto": solver["certificado"]["valor_esperado_exacto"], "ejecucion": solver},
        "comparacion": {"referencia_publicada_pdf": 10241.5, "diferencia_valor": optimum - 10241.5,
                        "mejora_relativa": optimum / 10241.5 - 1},
        "fecha_evaluacion": day, "datos_sha256": engine.problem.data_hash, "configuracion": config,
        "normalizacion_codigo": "LF",
        "codigo_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for path in sorted(MODELO.rglob("*.py")) if "resultados" not in path.parts},
    }
    write_json(directory / "metricas.json", reports)
    print(json.dumps({"backend": "flujo_ortools", "valor_exacto": solver["certificado"]["valor_esperado_exacto"],
                      "brecha_exacta": solver["certificado"]["brecha_exacta"],
                      "violaciones": audit["violaciones"], "clientes": audit["clientes_con_accion"],
                      "resolver_seg": solver["resolver_seg"], "segundos_motor": solver["segundos"]}), flush=True)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--salida", type=Path, default=Path(__file__).parent / "resultados")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--tarea", choices=("nba", "perfiles", "todo"), default="nba")
    parser.add_argument("--dispositivo", choices=("cpu", "cuda"), help="Dispositivo del autoencoder; por defecto NBA_DEVICE o cpu")
    parser.add_argument("--directo", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.name == "nt":
        if args.directo:
            parser.error("Ejecuta el motor con su Python WSL; OR-Tools local es Linux")
        from .entorno.kernel import run_in_kernel
        raise SystemExit(run_in_kernel("modelo.ejecutar", sys.argv[1:]))
    data = pd.read_csv(args.datos, dtype=str, keep_default_na=False)
    args.salida.mkdir(parents=True, exist_ok=True)
    manifest = {"datos": str(args.datos.resolve()), "sha256_datos": hashlib.sha256(args.datos.read_bytes()).hexdigest(),
                "filas": len(data), "columnas": len(data.columns), "python": platform.python_version(),
                "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__}
    if args.tarea in ("nba", "todo"):
        run_nba(data, load_config(args.config), args.salida / "nba", args.fecha, manifest["sha256_datos"])
    if args.tarea in ("perfiles", "todo"):
        from .perfiles import run_profiles
        profile_config = json.loads((args.config / "perfiles.json").read_text(encoding="utf-8-sig"))
        run_profiles(data, profile_config, args.salida / "perfiles", manifest["sha256_datos"], args.dispositivo)
    write_json(args.salida / "ejecucion.json", manifest)


if __name__ == "__main__":
    main()

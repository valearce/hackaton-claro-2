"""Ejecución reproducible del motor y de los perfiles exploratorios."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy

from .nba import CONFIG, Engine, OUTPUT_COLUMNS, load_config, validate_grid
from .rutas import DATOS, RAIZ as ROOT



def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_nba(data, config, directory, day, datos_sha256=None):
    directory.mkdir(parents=True, exist_ok=True)
    engine = Engine(data, config, day)
    reports = {}
    for name, calculate in (("baseline", engine.baseline), ("optimo", engine.optimize)):
        print(f"NBA: calculando {name} para {len(data):,} clientes", flush=True)
        grid, solver = calculate()
        audit = validate_grid(data, grid, config, day)
        if audit["violaciones"]:
            write_json(directory / f"errores_{name}.json", audit)
            raise RuntimeError(f"{name}: hay {audit['violaciones']} violaciones; no se exporta parrilla")
        grid.to_csv(directory / f"parrilla_{name}.csv", index=False, encoding="utf-8")
        reports[name] = {**audit, "ejecucion": solver}
        if name == "baseline":
            expected = pd.read_csv(Path(__file__).parent / "kit_original/casos_ejemplo_parrilla_esperada.csv", keep_default_na=False)
            fields = OUTPUT_COLUMNS[:-1]
            actual = grid.set_index("id_cliente")
            matches = []
            for row in expected.to_dict("records"):
                present = row["id_cliente"] in actual.index
                match = present and all(actual.loc[row["id_cliente"], c] == row[c] for c in fields[1:])
                matches.append({"id_cliente": row["id_cliente"], "coincide": bool(match),
                                "esperado": {c: row[c] for c in fields[1:]},
                                "obtenido": {c: actual.loc[row["id_cliente"], c] for c in fields[1:]} if present else None})
            reports[name]["casos_kit_en_corrida_completa"] = matches
        print(json.dumps({"metodo": name, "valor": audit["valor_esperado"], "violaciones": audit["violaciones"],
                          "clientes": audit["clientes_con_accion"], "segundos": solver["segundos"]}), flush=True)
    baseline, optimum = reports["baseline"]["valor_esperado"], reports["optimo"]["valor_esperado"]
    reports["comparacion"] = {"diferencia_valor": optimum - baseline,
                              "mejora_relativa": (optimum / baseline - 1) if baseline else None,
                              "referencia_publicada_pdf": 10241.5,
                              "nota_referencia": "La referencia publicada es 10241.5 y 70443 productos. Nuestra baseline usa desempates deterministas por ID y debe compararse con sus cifras efectivamente calculadas; no se afirma reproducción exacta de la cifra publicada."}
    reports["fecha_evaluacion"] = day
    reports["datos_sha256"] = datos_sha256
    reports["configuracion"] = config
    write_json(directory / "metricas.json", reports)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--salida", type=Path, default=Path(__file__).parent / "resultados")
    parser.add_argument("--fecha", default=date.today().isoformat())
    parser.add_argument("--tarea", choices=("nba", "perfiles", "todo"), default="todo")
    args = parser.parse_args()
    data = pd.read_csv(args.datos, keep_default_na=False)
    args.salida.mkdir(parents=True, exist_ok=True)
    manifest = {"datos": str(args.datos.resolve()), "sha256_datos": hashlib.sha256(args.datos.read_bytes()).hexdigest(),
                "filas": len(data), "columnas": len(data.columns), "python": platform.python_version(),
                "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__}
    if args.tarea in ("nba", "todo"):
        run_nba(data, load_config(args.config), args.salida / "nba", args.fecha, manifest["sha256_datos"])
    if args.tarea in ("perfiles", "todo"):
        from .perfiles import run_profiles
        profile_config = json.loads((args.config / "perfiles.json").read_text(encoding="utf-8-sig"))
        run_profiles(data, profile_config, args.salida / "perfiles", manifest["sha256_datos"])
    write_json(args.salida / "ejecucion.json", manifest)


if __name__ == "__main__":
    main()

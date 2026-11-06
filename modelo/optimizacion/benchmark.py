"""Compara LP y flujo sobre el mismo modelo exacto en procesos WSL separados."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from .certificado import create_certificate, read_certificate, save_certificate, verify_certificate
from .problema import ExactProblem, decimal_string
from ..nba import CONFIG, Engine, load_config, validate_grid
from ..rutas import DATOS, MODELO
from .solvers import solve_lp, solve_flow

MODEL = MODELO
ROOT = MODEL.parent


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def worker(args):
    from threadpoolctl import threadpool_limits
    started = time.perf_counter()
    problem = ExactProblem.load(args.problema)
    load_seconds = time.perf_counter() - started
    with threadpool_limits(limits=args.hilos):
        grid, solver = solve_lp(problem, threads=args.hilos) if args.worker == "lp" else solve_flow(problem)
    stamp = time.perf_counter()
    certificate, proof = create_certificate(problem, grid)
    certificate_seconds = time.perf_counter() - stamp
    args.salida.mkdir(parents=True, exist_ok=True)
    grid.to_csv(args.salida / "parrilla.csv", index=False)
    save_certificate(args.salida / "certificado.json.gz", certificate)
    report = {"backend": args.worker, "python": sys.executable, "solver": solver, "certificado": proof,
              "cargar_problema_seg": load_seconds, "certificar_seg": certificate_seconds,
              "rss_pico_bytes": peak_rss(), "metodo_memoria": "VmHWM en /proc/self/status del proceso ejecutado",
              "proceso_seg": time.perf_counter() - started}
    write_json(args.salida / "ejecucion.json", report)
    print(json.dumps({"backend": args.worker, "valor": proof["valor_exacto"], "brecha": proof["brecha_exacta"],
                      "resolver_seg": solver["resolver_seg"], "rss_mib": report["rss_pico_bytes"] / 1024 ** 2}), flush=True)


def peak_rss():
    # ru_maxrss puede conservar el pico previo a exec del coordinador cuando
    # subprocess usa fork. VmHWM pertenece al espacio de memoria tras exec.
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("No está disponible el contador VmHWM de Linux")


def run_benchmark(args):
    from ..entorno.pruebas import check_environment, read_config
    started = time.perf_counter()
    environment_config = read_config()
    environment = check_environment(environment_config)
    args.salida.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    stamp = time.perf_counter()
    problem = ExactProblem.from_csv(args.datos, config, args.fecha)
    preparation_seconds = time.perf_counter() - stamp
    print(f"Modelo exacto: {problem.n} clientes; escala {problem.scale}; {problem.packages_examined} paquetes factibles", flush=True)
    # Contraste de todas las máscaras y máximos locales con la implementación
    # anterior. Ningún solver nuevo recibe sus paquetes como verdad de referencia.
    data = pd.read_csv(args.datos, keep_default_na=False)
    legacy = Engine(data, config, args.fecha)
    for h, allowed in enumerate(legacy.feasible):
        if not np.array_equal(allowed, problem.allowed[:, h]):
            raise RuntimeError("Las reglas independientes no coinciden con las máscaras del motor anterior")
    legacy_values = np.column_stack([bundle.expected for bundle in legacy.bundles("valor_esperado")])
    if not np.array_equal(np.rint(legacy_values * problem.scale).astype(np.int64), problem.weights):
        raise RuntimeError("La selección local anterior omite un paquete de mayor valor exacto")
    del legacy, legacy_values
    model_path = args.salida / "problema-exacto.npz"
    problem.save(model_path)
    write_json(args.salida / "configuracion.json", config)
    runs = {key: [] for key in ("lp", "flujo") if args.backend in ("ambos", key)}
    audits = {}
    objectives = set()
    for repeat in range(args.repeticiones):
        order = list(runs) if repeat % 2 == 0 else list(reversed(runs))
        for backend in order:
            destination = args.salida / f"{backend}-{repeat + 1}"
            print(f"Repetición {repeat + 1}/{args.repeticiones}: {backend}, proceso nuevo", flush=True)
            command = [sys.executable, "-u", "-m", "modelo.benchmark_optimizador", "--worker", backend,
                       "--problema", str(model_path), "--salida", str(destination), "--hilos", str(args.hilos)]
            env = {**os.environ, "OMP_NUM_THREADS": str(args.hilos), "OPENBLAS_NUM_THREADS": str(args.hilos),
                   "MKL_NUM_THREADS": str(args.hilos), "PYTHONUNBUFFERED": "1"}
            completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if completed.returncode:
                raise RuntimeError(f"Falló {backend}: {completed.stdout}\n{completed.stderr}")
            print(completed.stdout.strip(), flush=True)
            report = json.loads((destination / "ejecucion.json").read_text(encoding="utf-8"))
            grid = pd.read_csv(destination / "parrilla.csv", dtype=str, keep_default_na=False)
            # Se comprueban nuevamente los artefactos leídos de disco con el
            # problema reconstruido del CSV original, no con el caché del hijo.
            verified = verify_certificate(problem, grid, read_certificate(destination / "certificado.json.gz"))
            if not verified["optimo_exacto"]:
                raise RuntimeError("No se publica un resultado con brecha exacta no nula")
            objectives.add(verified["valor_numerador"])
            runs[backend].append(report)
            if backend not in audits:
                audit = validate_grid(data, grid, config, args.fecha)
                if audit["violaciones"]:
                    raise RuntimeError(f"El auditor anterior detectó violaciones: {audit}")
                audits[backend] = audit
            if repeat > 0:
                # Conservar las mediciones de todas las repeticiones y una
                # parrilla/certificado por backend; no duplicar 100000 filas.
                (destination / "parrilla.csv").unlink()
                (destination / "certificado.json.gz").unlink()
    if len(objectives) != 1:
        raise RuntimeError("Los backends/repeticiones no alcanzaron el mismo óptimo exacto")
    summary = {}
    for backend, measurements in runs.items():
        summary[backend] = {
            "valor_exacto": measurements[0]["certificado"]["valor_exacto"],
            "optimo_exacto": True, "brecha_exacta": "0", "violaciones": audits[backend]["violaciones"],
            "repeticiones": len(measurements),
            "resolver_mediana_seg": statistics.median(r["solver"]["resolver_seg"] for r in measurements),
            "backend_mediana_seg": statistics.median(r["solver"]["total_backend_seg"] for r in measurements),
            "certificar_mediana_seg": statistics.median(r["certificar_seg"] for r in measurements),
            "rss_pico_mediana_mib": statistics.median(r["rss_pico_bytes"] / 1024 ** 2 for r in measurements),
            "clientes_con_accion": audits[backend]["clientes_con_accion"],
            "productos_asignados": audits[backend]["productos_asignados"],
            "indicador_jerarquia": audits[backend]["indicador_jerarquia"],
            "certificado": measurements[0]["certificado"], "mediciones": measurements}
        summary[backend]["estimacion_preparar_resolver_certificar_seg"] = preparation_seconds + summary[backend]["backend_mediana_seg"] + summary[backend]["certificar_mediana_seg"]
    report = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "fecha_evaluacion": args.fecha,
              "datos_sha256": problem.data_hash, "config_sha256": problem.config_hash, "configuracion": config,
              "entorno": environment, "filas": problem.n, "escala_entera": problem.scale,
              "preparar_modelo_independiente_seg": preparation_seconds,
              "rss_pico_coordinador_mib": peak_rss() / 1024 ** 2,
              "normalizacion_codigo": "LF",
              "codigo_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                  for p in sorted(MODEL.rglob("*.py")) if "resultados" not in p.parts},
              "contraste_mascaras_y_paquetes_motor_anterior": True, "resultados": summary,
              "comparacion": {}, "segundos_experimento": time.perf_counter() - started,
              "limites": ["Certificado entero verificado por Python, no por Lean.",
                          "El RSS pico incluye carga del problema, solver, parrilla y certificado del proceso hijo.",
                          "Los tiempos de resolver excluyen la preparación común; también se reporta una estimación que la incluye.",
                          "La preparación exacta independiente se comparte; no se afirma aceleración completa mirando solo el solver.",
                          "La comparación admite valor_esperado en modo ponderado, un canal y hasta dos productos."],
              "retencion": "Se conserva la primera parrilla y certificado por backend y las mediciones de todas las repeticiones. El problema intermedio se elimina al terminar."}
    if {"lp", "flujo"} <= set(summary):
        report["comparacion"] = {
            "diferencia_valor_exacto": "0",
            "aceleracion_resolver_lp_sobre_flujo": summary["lp"]["resolver_mediana_seg"] / summary["flujo"]["resolver_mediana_seg"],
            "aceleracion_backend_lp_sobre_flujo": summary["lp"]["backend_mediana_seg"] / summary["flujo"]["backend_mediana_seg"],
            "aceleracion_con_preparacion_y_certificado": summary["lp"]["estimacion_preparar_resolver_certificar_seg"] / summary["flujo"]["estimacion_preparar_resolver_certificar_seg"]}
    write_json(args.salida / "metricas.json", report)
    model_path.unlink()
    print(json.dumps({"resultados": {k: {name: value[name] for name in ("valor_exacto", "resolver_mediana_seg", "backend_mediana_seg", "rss_pico_mediana_mib")}
                                    for k, value in summary.items()}, "comparacion": report["comparacion"]}, ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--fecha", default="2026-11-05")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--backend", choices=("ambos", "lp", "flujo"), default="ambos")
    parser.add_argument("--salida", type=Path, default=MODEL / "resultados/optimizador")
    parser.add_argument("--directo", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", choices=("lp", "flujo"), help=argparse.SUPPRESS)
    parser.add_argument("--problema", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--hilos", type=int, default=4, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeticiones < 1 or args.hilos < 1:
        parser.error("Repeticiones e hilos deben ser positivos")
    if os.name == "nt" and not args.directo:
        from ..entorno.pruebas import kernel_command, read_config
        command, kernel_env, _ = kernel_command(read_config()["kernel_jupyter"], module="modelo.benchmark_optimizador", arguments=sys.argv[1:])
        completed = subprocess.run(command, cwd=ROOT, env={**os.environ, **kernel_env}, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        encoding = "utf-16-le" if b"\0" in completed.stdout[:100] else "utf-8"
        print(completed.stdout.decode(encoding, errors="replace"), end="", flush=True)
        raise SystemExit(completed.returncode)
    if os.name == "nt":
        parser.error("El benchmark se ejecuta dentro del entorno WSL estándar")
    if args.worker:
        worker(args)
    else:
        run_benchmark(args)


if __name__ == "__main__":
    main()

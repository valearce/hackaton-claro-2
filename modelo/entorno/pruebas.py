"""Pruebas del modelo en el entorno GPU del kernel Jupyter registrado.

Windows: python -m modelo.probar
El lanzador usa el intérprete del kernel WSL y nunca abre una terminal.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import time
from ..rutas import MODELO

MODEL = MODELO
ROOT = MODEL.parent


def read_config():
    return json.loads((MODEL / "config/entorno-pruebas.json").read_text(encoding="utf-8-sig"))


def kernel_command(kernel_name, only_environment=False, module="modelo.probar", arguments=()):
    """Resuelve el kernel del usuario; no fija su nombre de usuario ni su ruta home."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA no está definido; ejecuta desde Windows o usa --directo dentro del entorno GPU")
    kernel_path = Path(appdata) / "jupyter/kernels" / kernel_name / "kernel.json"
    if not kernel_path.is_file():
        raise FileNotFoundError(f"Kernel no registrado: {kernel_name}. Consulta python -m jupyter kernelspec list")
    specification = json.loads(kernel_path.read_text(encoding="utf-8-sig"))
    argv = specification["argv"]
    if Path(argv[0]).name.lower() not in ("wsl", "wsl.exe") or "-e" not in argv:
        raise RuntimeError("El kernel seleccionado debe declarar un lanzador WSL mediante -e")
    position = argv.index("-e")
    launcher = PurePosixPath(argv[position + 1])
    if not launcher.is_absolute() or launcher.name != "kernel_wsl.sh":
        raise RuntimeError("Lanzador de kernel no reconocido: se esperaba una ruta absoluta a kernel_wsl.sh")
    python = str(launcher.with_name("python"))
    command = [*argv[:position], "--cd", str(ROOT), "-e", python, "-u", "-m", module, "--directo", *arguments]
    if only_environment:
        command.append("--solo-entorno")
    return command, specification.get("env", {}), kernel_path


def check_environment(config):
    """Valida el runtime y ejecuta operaciones CUDA; enumerar una GPU no basta."""
    os.environ["NBA_DEVICE"] = config["dispositivo"]
    os.environ["NBA_REQUIRE_CUDA"] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = config["cublas_workspace_config"]
    os.environ.setdefault("CUDA_CACHE_MAXSIZE", "4294967296")
    os.environ["MPLBACKEND"] = "Agg"
    import torch
    from .dispositivo import select_device

    if ".".join(map(str, sys.version_info[:2])) != config["python"]:
        raise RuntimeError(f"Python distinto del fijado: {platform.python_version()}")
    packages = {name: version(name) for name in config["paquetes"]}
    mismatches = {name: {"actual": packages[name], "esperado": expected}
                  for name, expected in config["paquetes"].items() if packages[name] != expected}
    if mismatches:
        raise RuntimeError(f"Versiones distintas del entorno estandarizado: {json.dumps(mismatches)}")
    if torch.__version__ != config["torch_runtime"] or torch.version.cuda != config["cuda_runtime"]:
        raise RuntimeError(f"Runtime PyTorch/CUDA distinto del fijado: {torch.__version__} / {torch.version.cuda}")
    device = select_device("cuda")
    torch.manual_seed(config["semilla"])
    torch.set_num_threads(config["hilos_cpu"])
    torch.use_deterministic_algorithms(True)
    tensor = torch.arange(64, dtype=torch.float32, device=device).reshape(8, 8).requires_grad_()
    loss = (tensor @ tensor.T).mean()
    loss.backward()
    torch.cuda.synchronize()
    if not torch.isfinite(loss) or tensor.grad is None or not torch.isfinite(tensor.grad).all():
        raise RuntimeError("Falló la comprobación numérica CUDA")
    flow_version = None
    if config.get("ortools_version"):
        from ..optimizacion.solvers import load_flow_module, ORTOOLS_VERSION
        flow = load_flow_module().SimpleMinCostFlow()
        flow.add_arc_with_capacity_and_unit_cost(0, 1, 1, -7)
        flow.set_node_supply(0, 1)
        flow.set_node_supply(1, -1)
        if ORTOOLS_VERSION != config["ortools_version"] or flow.solve() != flow.OPTIMAL or flow.optimal_cost() != -7:
            raise RuntimeError("Falló la verificación del módulo local de flujo")
        flow_version = ORTOOLS_VERSION
    return {"python": platform.python_version(), "ejecutable": sys.executable,
            "plataforma": platform.platform(), "paquetes": packages,
            "torch_runtime": torch.__version__, "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0), "capacidad_computo": list(torch.cuda.get_device_capability(0)),
            "arquitecturas_pytorch": torch.cuda.get_arch_list(), "autograd_cuda": True,
            "semilla": config["semilla"], "hilos_cpu": torch.get_num_threads(),
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"], "ortools_graph_local": flow_version,
            "protobuf_instalado": version("protobuf")}


def direct_run(only_environment):
    config = read_config()
    started = time.perf_counter()
    report_dir = MODEL / "resultados/pruebas-gpu"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "kernel": config["kernel_jupyter"],
              "estado": "error", "configuracion": config,
              "normalizacion_codigo": "LF",
              "codigo_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                for path in sorted(MODEL.rglob("*.py")) if "resultados" not in path.parts},
              "datos_sha256": hashlib.sha256((ROOT / "datos/clientes.csv").read_bytes()).hexdigest()}
    try:
        report["entorno"] = check_environment(config)
        print(json.dumps(report["entorno"], ensure_ascii=False, indent=2), flush=True)
        if only_environment:
            report["estado"] = "entorno_verificado"
        else:
            import unittest
            import io
            from threadpoolctl import threadpool_limits
            stream = io.StringIO()
            with threadpool_limits(limits=config["hilos_cpu"]):
                suite = unittest.defaultTestLoader.discover(str(MODEL / "tests"), top_level_dir=str(ROOT))
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            log = stream.getvalue()
            (report_dir / "pruebas.log").write_text(log, encoding="utf-8")
            print(log, flush=True)
            report.update(estado="aprobado" if result.wasSuccessful() and not result.skipped else "fallo",
                          pruebas=result.testsRun, fallos=len(result.failures), errores=len(result.errors),
                          omitidas=len(result.skipped))
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], file=sys.stderr, flush=True)
    finally:
        report["segundos"] = time.perf_counter() - started
        name = "entorno.json" if only_environment else "metricas.json"
        (report_dir / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["estado"] in ("aprobado", "entorno_verificado") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo-entorno", action="store_true", help="Verifica versiones y ejecuta autograd en CUDA sin la suite")
    parser.add_argument("--directo", action="store_true", help="Ejecutar dentro del Python GPU de WSL")
    args = parser.parse_args()
    if os.name == "nt" and not args.directo:
        kernel = read_config()["kernel_jupyter"]
        command, kernel_env, source = kernel_command(kernel, args.solo_entorno)
        print(f"Kernel: {kernel}; configuración: {source}", flush=True)
        completed = subprocess.run(command, cwd=ROOT, env={**os.environ, **kernel_env, "PYTHONUNBUFFERED": "1"},
                                   creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, check=False)
        encoding = "utf-16-le" if b"\0" in completed.stdout[:100] else "utf-8"
        print(completed.stdout.decode(encoding, errors="replace"), end="", flush=True)
        return completed.returncode
    if os.name == "nt":
        raise RuntimeError("--directo requiere el intérprete Linux del kernel GPU")
    return direct_run(args.solo_entorno)


if __name__ == "__main__":
    raise SystemExit(main())

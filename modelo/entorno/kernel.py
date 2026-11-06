"""Acceso al Python WSL del kernel Jupyter, sin abrir terminales."""
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess

from ..rutas import MODELO, RAIZ


def run_in_kernel(module, arguments):
    config = json.loads((MODELO / "config/entorno.json").read_text(encoding="utf-8-sig"))
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA no está definido; ejecuta desde el Python WSL configurado")
    kernel_path = Path(appdata) / "jupyter/kernels" / config["kernel_jupyter"] / "kernel.json"
    specification = json.loads(kernel_path.read_text(encoding="utf-8-sig"))
    argv = specification["argv"]
    if Path(argv[0]).name.lower() not in ("wsl", "wsl.exe") or "-e" not in argv:
        raise RuntimeError("El kernel debe declarar un lanzador WSL mediante -e")
    position = argv.index("-e")
    launcher = PurePosixPath(argv[position + 1])
    if not launcher.is_absolute() or launcher.name != "kernel_wsl.sh":
        raise RuntimeError("Se esperaba una ruta absoluta a kernel_wsl.sh")
    arguments = list(arguments)
    path_flags = {"--datos", "--config", "--salida"}
    for index, argument in enumerate(arguments):
        flag, separator, value = argument.partition("=")
        if flag not in path_flags:
            continue
        value_index = index if separator else index + 1
        value = value if separator else arguments[value_index]
        if PureWindowsPath(value).is_absolute():
            converted = subprocess.run([*argv[:position], "-e", "wslpath", "-u", value],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            value = converted.stdout.decode("utf-8").strip()
            arguments[value_index] = f"{flag}={value}" if separator else value
    threads = str(config["hilos_cpu"])
    command = [*argv[:position], "--cd", str(RAIZ), "-e", "env", f"OMP_NUM_THREADS={threads}",
               f"OPENBLAS_NUM_THREADS={threads}", f"MKL_NUM_THREADS={threads}",
               str(launcher.with_name("python")), "-u", "-B", "-m", module, "--directo", *arguments]
    env = {**os.environ, **specification.get("env", {}), "OMP_NUM_THREADS": threads,
           "OPENBLAS_NUM_THREADS": threads, "MKL_NUM_THREADS": threads,
           "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(command, cwd=RAIZ, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    encoding = "utf-16-le" if b"\0" in completed.stdout[:100] else "utf-8"
    print(completed.stdout.decode(encoding, errors="replace"), end="", flush=True)
    return completed.returncode

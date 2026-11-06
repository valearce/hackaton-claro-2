"""Incluye el motor compartido y el CSV en el servicio Python de Vercel."""
from pathlib import Path
import shutil

service = Path(__file__).resolve().parent
root = service.parent
for folder in ("nba", "optimizacion", "config"):
    for source in (root / "modelo" / folder).rglob("*"):
        if source.is_file() and "__pycache__" not in source.parts:
            target = service / "modelo" / source.relative_to(root / "modelo")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
for name in ("__init__.py", "rutas.py"):
    target = service / "modelo" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "modelo" / name, target)
(service / "datos").mkdir(exist_ok=True)
shutil.copyfile(root / "datos/clientes.csv", service / "datos/clientes.csv")
print("Motor compartido y datos preparados para el servicio NBA.")

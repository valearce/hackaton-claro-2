"""Ubicaciones compartidas, independientes del directorio de ejecución."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos" / "clientes.csv"
KIT_OFICIAL = RAIZ / "docs" / "reto" / "kit-oficial.zip"

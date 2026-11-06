"""Entrada estable: python -m modelo.probar."""
from .entorno.pruebas import main, check_environment, kernel_command, read_config

if __name__ == "__main__":
    raise SystemExit(main())

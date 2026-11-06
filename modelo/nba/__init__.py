"""API del motor NBA configurable."""
from .motor import CONFIG, OUTPUT_COLUMNS, Engine, load_config, validate_grid

__all__ = ["CONFIG", "OUTPUT_COLUMNS", "Engine", "load_config", "validate_grid"]

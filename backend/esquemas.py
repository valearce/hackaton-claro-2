"""Contrato de configuración de negocio y validación de las solicitudes."""
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Condicion(Modelo):
    atributo: str | None = None
    operador: Literal["==", "!=", "<", "<=", ">", ">=", "en", "no_en", "contiene"] | None = None
    valor: Any = None
    todas: list["Condicion"] | None = Field(default=None, min_length=1, max_length=20)
    alguna: list["Condicion"] | None = Field(default=None, min_length=1, max_length=20)

    @model_validator(mode="after")
    def forma(self):
        if sum((self.todas is not None, self.alguna is not None, self.atributo is not None)) != 1:
            raise ValueError("Define una condición simple, todas o alguna")
        if self.atributo is not None and (not self.operador or self.valor is None):
            raise ValueError("La condición necesita columna, operador y valor")
        if self.operador in ("en", "no_en") and (not isinstance(self.valor, list) or not self.valor):
            raise ValueError("El operador de lista necesita al menos un valor")
        return self


class Alcance(Modelo):
    nivel: Literal["global", "campana", "producto", "objetivo", "canal"]
    valores: list[str] = Field(default_factory=list, max_length=50)


class Regla(Modelo):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    control: str = Field(min_length=1, max_length=64)
    nombre: str = Field(min_length=1, max_length=200)
    tipo: Literal["elegibilidad", "canal"]
    alcance: Alcance
    condicion: Condicion
    accion: Literal["excluir"] = "excluir"
    activa: bool


class Campana(Modelo):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    nombre: str = Field(min_length=1, max_length=200)
    producto: str = Field(min_length=1, max_length=64)
    objetivo: str = Field(min_length=1, max_length=120)
    columna_score: str = Field(min_length=1, max_length=120)
    valor_negocio: float = Field(ge=0, le=1)
    canales_permitidos: list[str] = Field(max_length=20)
    vigencia_inicio: date
    vigencia_fin: date
    activa: bool

    @model_validator(mode="after")
    def vigencia(self):
        if self.vigencia_fin < self.vigencia_inicio:
            raise ValueError("La vigencia final debe ser posterior a la inicial")
        return self


class Pesos(Modelo):
    score_producto: float = Field(ge=0, le=1)
    valor_negocio: float = Field(ge=0, le=1)
    jerarquia: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def suma(self):
        if sum(Decimal(str(x)) for x in (self.score_producto, self.valor_negocio, self.jerarquia)) != 1:
            raise ValueError("Los pesos deben sumar 1")
        if any(Decimal(str(x)).as_tuple().exponent < -3 for x in (self.score_producto, self.valor_negocio, self.jerarquia)):
            raise ValueError("Usa como máximo tres decimales en los pesos")
        return self


class Priorizacion(Modelo):
    modo: Literal["ponderado", "jerarquia_estricta"]
    modos_disponibles: list[str] = Field(default_factory=lambda: ["ponderado", "jerarquia_estricta"])
    jerarquia: list[str] = Field(min_length=1, max_length=20)
    pesos: Pesos
    umbral_score_producto: float = Field(ge=0, le=1)
    desempate: list[str] = Field(default_factory=lambda: ["score_producto", "valor_negocio"])


class Canal(Modelo):
    criterio: str = "score_canal"
    criterios_disponibles: list[str] = Field(default_factory=lambda: ["score_canal"])
    orden_preferencia: list[str]
    umbral_score_canal: float = Field(ge=0, le=1)
    capacidad_por_corrida: dict[str, int] = Field(min_length=1, max_length=20)
    columnas_score: dict[str, str]


class Politica(Modelo):
    canales_por_cliente: Literal[1] = 1
    max_contactos_semana: int = Field(ge=0, le=100)
    max_productos_por_canal: dict[str, int]
    columna_contactos_semana: str = "contactos_semana_actual"


class Optimizacion(Modelo):
    backend: Literal["flujo_ortools"] = "flujo_ortools"
    objetivo: Literal["valor_esperado", "prioridad"] = "valor_esperado"


class Parametros(Modelo):
    priorizacion: Priorizacion
    canal: Canal
    politica_contacto: Politica
    optimizacion: Optimizacion


class Configuracion(Modelo):
    campanas: list[Campana] = Field(min_length=1, max_length=20)
    reglas: list[Regla] = Field(max_length=100)
    parametros: Parametros

    @model_validator(mode="after")
    def referencias(self):
        ids = [c.id for c in self.campanas]
        channels = self.parametros.canal.capacidad_por_corrida
        if len(set(ids)) != len(ids) or len({r.id for r in self.reglas}) != len(self.reglas):
            raise ValueError("Las campañas y reglas necesitan identificadores únicos")
        hierarchy = self.parametros.priorizacion.jerarquia
        if len(set(hierarchy)) != len(hierarchy) or set(hierarchy) - set(ids):
            raise ValueError("La jerarquía contiene campañas desconocidas o repetidas")
        if any(type(value) is not int or not 0 <= value <= 1_000_000 for value in channels.values()):
            raise ValueError("Los cupos deben ser enteros entre 0 y 1.000.000")
        limits = self.parametros.politica_contacto.max_productos_por_canal
        if set(channels) != set(limits) or any(type(x) is not int or not 0 <= x <= 2 for x in limits.values()):
            raise ValueError("Cada canal debe tener un máximo entre cero y dos productos")
        if set(channels) != set(self.parametros.canal.columnas_score):
            raise ValueError("Cada canal debe tener una columna de score")
        if any(set(c.canales_permitidos) - set(channels) for c in self.campanas):
            raise ValueError("Una campaña utiliza un canal no configurado")
        for rule in self.reglas:
            if rule.tipo == "elegibilidad" and rule.alcance.nivel == "canal":
                raise ValueError("Una exclusión de producto no puede tener alcance canal")
        return self


class Pedido(Modelo):
    config: Configuracion
    fecha: date = date(2026, 11, 5)


class Guardar(Pedido):
    nombre: str = Field(default="Nueva versión", min_length=1, max_length=100)


def diccionario(config: Configuracion):
    return config.model_dump(mode="json", exclude_none=True)

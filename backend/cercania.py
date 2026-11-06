"""Simulación geométrica de antenas, vallas y reglas de campaña."""
from datetime import date, timedelta, timezone
from math import atan2, ceil, cos, radians, sin, sqrt
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


router = APIRouter(prefix="/api/cercania", tags=["Cercanía"])
RADIO_TIERRA_M = 6_371_000.0
HORA_BOGOTA = timezone(timedelta(hours=-5))
Identificador = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Canal = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_-]*$")]


class ModeloCercania(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class ZonaCercania(ModeloCercania):
    id: Identificador
    nombre: str = Field(min_length=1, max_length=160)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radio_m: float = Field(gt=0, le=100_000)
    activo: bool


class ClienteCercania(ModeloCercania):
    id: Literal["DEMO-001"] = "DEMO-001"
    consentimiento: bool
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CampanaCercania(ModeloCercania):
    id: Identificador
    nombre: str = Field(min_length=1, max_length=160)
    canales_permitidos: list[Canal] = Field(max_length=20)
    activa: bool
    vigencia_inicio: date
    vigencia_fin: date

    @model_validator(mode="after")
    def coherencia(self):
        if self.vigencia_fin < self.vigencia_inicio:
            raise ValueError("La vigencia final debe ser posterior o igual a la inicial")
        if len(set(self.canales_permitidos)) != len(self.canales_permitidos):
            raise ValueError("Los canales permitidos no pueden repetirse")
        return self


class PedidoCercania(ModeloCercania):
    modo: Literal["mapa_demo"] = "mapa_demo"
    cliente: ClienteCercania
    antenas: list[ZonaCercania] = Field(max_length=100)
    vallas: list[ZonaCercania] = Field(max_length=100)
    campana: CampanaCercania
    canal: Canal
    momento: AwareDatetime
    cooldown_segundos: int = Field(default=300, ge=0, le=86_400, strict=True)
    ultimo_evento: AwareDatetime | None = None

    @model_validator(mode="after")
    def coherencia(self):
        ids = [zona.id for zona in self.antenas + self.vallas]
        if len(set(ids)) != len(ids):
            raise ValueError("Las antenas y vallas necesitan identificadores únicos")
        if self.ultimo_evento is not None and self.ultimo_evento > self.momento:
            raise ValueError("El último evento no puede ser posterior al momento de evaluación")
        return self


def distancia_haversine_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Distancia aproximada en metros sobre una esfera; sin servicios externos."""
    a_lat, b_lat = radians(lat_a), radians(lat_b)
    lat_delta = b_lat - a_lat
    lon_delta = radians(lon_b - lon_a)
    hav = sin(lat_delta / 2) ** 2 + cos(a_lat) * cos(b_lat) * sin(lon_delta / 2) ** 2
    hav = min(1.0, max(0.0, hav))
    return 2 * RADIO_TIERRA_M * atan2(sqrt(hav), sqrt(1 - hav))


def evaluar(pedido: PedidoCercania) -> dict:
    """Evalúa una solicitud completa con posiciones simuladas, sin persistencia."""
    controles = []
    distancias = []
    zonas_cercanas = []

    def control(codigo: str, cumple: bool, detalle_ok: str, detalle_no: str):
        controles.append({"codigo": codigo, "cumple": bool(cumple), "detalle": detalle_ok if cumple else detalle_no})

    # El validador del pedido exige ambas coordenadas en este modo.
    assert pedido.cliente.lat is not None and pedido.cliente.lon is not None
    for tipo, zonas in (("antena", pedido.antenas), ("valla", pedido.vallas)):
        for zona in zonas:
            metros = distancia_haversine_m(pedido.cliente.lat, pedido.cliente.lon, zona.lat, zona.lon)
            distancias.append({**zona.model_dump(), "tipo": tipo, "distancia_m": round(metros, 3), "dentro_radio": metros <= zona.radio_m})
    zonas_cercanas = [zona for zona in distancias if zona["activo"] and zona["dentro_radio"]]
    for tipo in ("antena", "valla"):
        control(f"radio_{tipo}", any(zona["tipo"] == tipo for zona in zonas_cercanas),
                f"La posición ficticia está dentro del radio de una {tipo} activa.",
                f"La posición ficticia está fuera del radio de todas las {tipo}s activas.")
    advertencia = "Prueba geométrica con puntos ficticios. El radio calculado no acredita recepción de señal ni exposición a una valla."

    fecha_local = pedido.momento.astimezone(HORA_BOGOTA).date()
    vigente = pedido.campana.vigencia_inicio <= fecha_local <= pedido.campana.vigencia_fin
    transcurrido = (pedido.momento - pedido.ultimo_evento).total_seconds() if pedido.ultimo_evento else None
    restante = max(0, pedido.cooldown_segundos - transcurrido) if transcurrido is not None else 0
    control("campana_activa", pedido.campana.activa, "La campaña está activa.", "La campaña está pausada.")
    control("campana_vigente", vigente, f"La campaña está vigente el {fecha_local.isoformat()} (hora de Bogotá).",
            f"La campaña no está vigente el {fecha_local.isoformat()} (hora de Bogotá).")
    control("consentimiento", pedido.cliente.consentimiento, "Se confirmó el opt-in para esta prueba.", "Falta confirmar el consentimiento opt-in para esta prueba.")
    control("canal_permitido", pedido.canal in pedido.campana.canales_permitidos,
            f"La campaña permite el canal {pedido.canal}.", f"La campaña no permite el canal {pedido.canal}.")
    control("cooldown", restante == 0, "El intervalo entre eventos permite una nueva oportunidad.",
            f"Espera {ceil(restante)} segundos antes de evaluar otra oportunidad para esta prueba.")
    elegible = all(item["cumple"] for item in controles)
    motivos = [item["detalle"] for item in controles if not item["cumple"]]
    if elegible:
        motivos = ["Se cumplen las condiciones de proximidad, campaña, autorización y frecuencia de esta prueba."]
    return {"demo": True, "modo": pedido.modo, "elegible": elegible,
        "decision": "oportunidad_demo" if elegible else "sin_oportunidad", "evaluado_en": pedido.momento.isoformat(),
        "fecha_campana_bogota": fecha_local.isoformat(), "motivos": motivos, "controles": controles,
        "distancias": distancias, "zonas_cercanas": zonas_cercanas, "unidad_distancia": "m" if pedido.modo == "mapa_demo" else None,
        "cooldown_restante_segundos": ceil(restante),
        "accion": {"campana_id": pedido.campana.id, "campana_nombre": pedido.campana.nombre, "canal": pedido.canal,
                   "tipo": "vista_previa_local", "texto": f"DEMO: oportunidad de {pedido.campana.nombre} por {pedido.canal}."} if elegible else None,
        "advertencia": advertencia + " La oportunidad es una vista previa local; no envía mensajes ni atribuye una compra a la valla."}


@router.get("/config")
def configuracion_cercania():
    """Sectores y recorrido ficticios y reproducibles."""
    return {"demo": True, "modo_recomendado": "mapa_demo", "unidad_distancia": "m",
        "antenas": [
            {"id": "ANT-DEMO-01", "nombre": "Antena simulada Chapinero", "lat": 4.6510, "lon": -74.0640, "radio_m": 180, "activo": True},
            {"id": "ANT-DEMO-02", "nombre": "Antena simulada Norte", "lat": 4.6792, "lon": -74.0467, "radio_m": 220, "activo": True},
            {"id": "ANT-DEMO-03", "nombre": "Antena simulada Centro", "lat": 4.6045, "lon": -74.0730, "radio_m": 160, "activo": True}],
        "vallas": [
            {"id": "VAL-DEMO-01", "nombre": "Valla simulada Chapinero", "lat": 4.65075, "lon": -74.0642, "radio_m": 100, "activo": True},
            {"id": "VAL-DEMO-02", "nombre": "Valla simulada Norte", "lat": 4.6793, "lon": -74.0465, "radio_m": 90, "activo": True},
            {"id": "VAL-DEMO-03", "nombre": "Valla simulada Centro", "lat": 4.6043, "lon": -74.0731, "radio_m": 80, "activo": False}],
        "campanas": [
            {"id": "C-PROX-DEMO-01", "nombre": "Hogar por cercanía (ficticia)", "canales_permitidos": ["sms", "whatsapp", "push"], "activa": True, "vigencia_inicio": "2026-01-01", "vigencia_fin": "2026-12-31"},
            {"id": "C-PROX-DEMO-02", "nombre": "Renovación en punto físico (ficticia)", "canales_permitidos": ["sms", "correo"], "activa": True, "vigencia_inicio": "2026-11-01", "vigencia_fin": "2026-12-31"},
            {"id": "C-PROX-DEMO-03", "nombre": "Experiencia OTT (ficticia)", "canales_permitidos": ["push", "whatsapp"], "activa": False, "vigencia_inicio": "2026-11-01", "vigencia_fin": "2026-12-31"}],
        "cliente_demo": {"id": "DEMO-001", "lat": 4.64597, "lon": -74.06903, "consentimiento": False},
        "politica": {"cooldown_segundos": 300, "canales": ["sms", "whatsapp", "correo", "push"]},
        "momento_demo": "2026-11-05T15:00:00-05:00",
        "aviso": "Antenas, vallas, campañas y cliente son de demostración. La cercanía se calcula con posiciones simuladas y radios configurables."}

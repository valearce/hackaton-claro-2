"""Propuestas de mensaje por campaña, adaptadas al sector.

Cada campaña tiene varias propuestas (ángulos: ahorro, novedad, familia, entretenimiento). El texto se
adapta con un gancho que sale de los rasgos que de verdad distinguen al sector. Una campaña nueva sin
plantillas propias usa la plantilla genérica de `config.json`: no hace falta tocar código."""
from .sectores import UMBRAL_EFECTO

LIMITE_SMS = 160


def _mayuscula(texto):
    texto = texto.strip()
    return texto[:1].upper() + texto[1:]


def gancho(config, z_sector):
    """Frase de apertura según el rasgo más marcado del sector; vacía si ninguno supera el umbral."""
    if not z_sector:
        return ""
    for rasgo, valor in sorted(z_sector.items(), key=lambda kv: -abs(kv[1])):
        if abs(valor) < UMBRAL_EFECTO:
            break
        frase = config["ganchos"].get(f"{rasgo}{'+' if valor > 0 else '-'}")
        if frase:
            return frase
    return ""


def redactar(config, campana, variante, z_sector=None, canal=None):
    """Texto de la propuesta `variante` para `campana` (dict con id y nombre), adaptado al sector y al canal."""
    plantilla = config["plantillas"].get(campana["id"], {}).get(variante)
    ap = gancho(config, z_sector)
    if plantilla is None:
        g = config["genericas"]
        texto = g["plantilla"].format(gancho=ap, campana=campana["nombre"], beneficio=g["beneficios"][variante])
    else:
        texto = plantilla.format(gancho=ap)
    texto = _mayuscula(texto.replace("  ", " "))
    if canal == "sms" and len(texto) > LIMITE_SMS:
        texto = texto[: LIMITE_SMS - 1].rstrip(" ,;") + "…"
    return texto


def nombres_variantes(config):
    return {clave: datos["nombre"] for clave, datos in config["variantes"].items()}


def catalogo(config, campanas):
    """Todas las propuestas disponibles: una fila por campaña y variante."""
    return [{"campana": c["id"], "variante": v, "nombre": n} for c in campanas for v, n in nombres_variantes(config).items()]

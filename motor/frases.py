"""Frases para quien ejecuta el contacto (asesor o equipo de campanas), en espanol natural.

Una frase por cliente: que ofrecer, por que canal y por que este cliente y no otro.
Varias plantillas por caso; la eleccion es determinista (depende del id) para que
la misma corrida produzca siempre las mismas frases.
"""
import zlib

import numpy as np

PRODUCTO = {"VCH": "Hogar", "TER": "la renovación de su equipo", "OTT": "el upgrade de streaming"}
CANAL = {"asesor": "una llamada de asesor", "whatsapp": "WhatsApp", "correo": "correo", "sms": "SMS", "app": "la app Mi Claro"}


def _elige(opciones, clave):
    return opciones[zlib.crc32(clave.encode()) % len(opciones)]


def _que(prods):
    nombres = [PRODUCTO.get(p, p) for p in prods]
    return nombres[0] if len(nombres) == 1 else f"{nombres[0]} y {nombres[1]}"


def _gancho(o, i, prods):
    """Un dato del cliente que justifica la oferta, en lenguaje de negocio."""
    df = o.df.iloc[i]
    p = prods[0]
    if p == "TER" and "edad_equipo_meses" in df:
        return f"su equipo ya tiene {int(df.edad_equipo_meses)} meses"
    if p == "VCH":
        return "todavía no tiene Hogar con Claro"
    if p == "OTT" and "cantidad_ott" in df:
        n = int(df.cantidad_ott)
        return "no tiene ninguna plataforma de streaming" if n == 0 else f"tiene {n} de las 3 plataformas"
    return ""


def frase(o, i, k, combo, sombra):
    """o: Orquestador ya corrido en modo optimo; i: fila del cliente; k: canal; combo: campanas."""
    ch = o.canales[k]
    prods = [o._prods[j] for j in combo]
    que, gancho, cid = _que(prods), _gancho(o, i, prods), o.df.id_cliente.iat[i]
    v = o._v[i, k]
    alt = [(o._v[i, q], o.canales[q]) for q in range(len(o.canales)) if q != k and np.isfinite(o._u[i, q])]
    mejor_alt = max(alt) if alt else None

    if ch == "asesor":
        if mejor_alt is None:
            return _elige([
                f"Llámalo para ofrecerle {que}: {gancho} y el asesor es el único canal que tenemos con él.",
                f"Ofrécele {que} por teléfono; {gancho} y no autorizó canales digitales.",
            ], cid)
        r = round(100 * mejor_alt[0] / v) if v > 0 else 0
        return _elige([
            f"Llámalo para ofrecerle {que}: {gancho}. Por {CANAL[mejor_alt[1]]} la oferta rendiría {r}% de lo que rinde tu llamada.",
            f"Este cliente vale la llamada: {gancho}, y por {CANAL[mejor_alt[1]]} solo lograríamos {r}% del resultado. Ofrécele {que}.",
            f"Ofrécele {que}; {gancho}. Es de los clientes que más pierden si no los llama un asesor.",
        ], cid)

    base = _elige([
        f"Envíale por {CANAL[ch]} {que}: {gancho}.",
        f"Por {CANAL[ch]}, ofrécele {que}; {gancho}.",
        f"{CANAL[ch][0].upper() + CANAL[ch][1:]} con {que}: {gancho}.",
    ], cid)
    if mejor_alt and mejor_alt[1] == "asesor" and mejor_alt[0] > v:
        base += " Una llamada rendiría algo más, pero ese cupo genera más valor en otro cliente."
    elif mejor_alt and mejor_alt[0] > v:
        base += f" {CANAL[mejor_alt[1]]} rendiría un poco más, pero ese cupo ya está tomado por clientes de mayor valor."
    elif len(prods) == 2:
        base += " Van las dos ofertas en el mismo mensaje, que cuenta como un solo contacto."
    return base


def frase_sin_accion(o, i):
    if o.bloq_semana[i]:
        return "No contactar esta semana: ya recibió el máximo de contactos permitido."
    if not o.elig[i].any():
        return "No contactar: no califica para ninguna campaña activa."
    if not (o.canal_ok[i][None, :] & o.permite[o.elig[i]]).any():
        return "No contactar: no tiene un canal autorizado para las campañas a las que califica."
    return "No contactar en esta corrida: los cupos de sus canales generan más valor con otros clientes."

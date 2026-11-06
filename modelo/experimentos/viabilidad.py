"""Viabilidad de cada campaña por sector, con las restricciones lógicas a la vista.

Sale del propio motor NBA (no de supuestos): para cada sector x campaña cuenta cuántos clientes hay, cuántos
sobreviven a cada regla, cuántos tienen un canal habilitado y cuánto valor esperado les asigna la parrilla.
Una celda sin clientes elegibles queda *bloqueada* y se nombra la regla responsable. También permite
probar una restricción de negocio nueva (p. ej. «no ofrecer streaming a estrato 1») volviendo a correr el motor."""
from copy import deepcopy

import numpy as np

from ..nba import Engine, applies, condition_mask

OPERADORES = {"==": "es", "!=": "no es", "<": "es menor que", "<=": "es como máximo", ">": "es mayor que",
              ">=": "es al menos", "en": "está entre", "no_en": "no está entre", "contiene": "incluye"}


def texto_condicion(cond):
    """La condición de una regla en palabras: 'estrato es 1', 'calificacion_riesgo está entre C, P'."""
    if "todas" in cond:
        return " y ".join(texto_condicion(c) for c in cond["todas"])
    if "alguna" in cond:
        return " o ".join(texto_condicion(c) for c in cond["alguna"])
    valor = cond["valor"]
    valor = ", ".join(map(str, valor)) if isinstance(valor, list) else valor
    return f"{cond['atributo']} {OPERADORES.get(cond['operador'], cond['operador'])} {valor}"


def texto_alcance(alcance, campanas):
    nombres = {c["id"]: c["nombre"] for c in campanas}
    if alcance["nivel"] == "global":
        return "Todas las campañas"
    valores = [nombres.get(v, v) if alcance["nivel"] == "campana" else v for v in alcance["valores"]]
    return {"campana": "Campaña", "producto": "Producto", "objetivo": "Objetivo", "canal": "Canal"}[alcance["nivel"]] + ": " + ", ".join(valores)


def valor_de_parrilla(engine, parrilla):
    """Valor esperado total (score producto x score canal x valor) de una parrilla sobre todos los clientes."""
    g = parrilla.set_index("id_cliente").reindex(engine.ids)
    ids = [c["id"] for c in engine.campaigns]
    total = 0.0
    for col in ("campana_1", "campana_2"):
        filas = np.flatnonzero((g["estado"] == "asignado").to_numpy() & (g[col].fillna("") != "").to_numpy())
        j = np.array([ids.index(x) for x in g[col].to_numpy()[filas]], dtype=int)
        k = np.array([engine.channels.index(x) for x in g["canal"].to_numpy()[filas]], dtype=int)
        total += float((engine.product_scores[filas, j] * engine.channel_scores[filas, k] * engine.values[j]).sum())
    return total


def reglas_vigentes(engine, idx):
    """Cada regla activa con cuántos clientes de la región bloquea, por campaña o canal."""
    datos = engine.data.iloc[idx]
    salida = []
    for regla in engine.rules:
        bloqueados = {}
        if regla["tipo"] == "elegibilidad":
            for camp in engine.campaigns:
                if applies(regla, camp):
                    bloqueados[camp["id"]] = int(condition_mask(datos, regla["condicion"], camp).sum())
        else:
            for canal in engine.channels:
                if applies(regla, None, canal):
                    bloqueados[canal] = int(condition_mask(datos, regla["condicion"], None).sum())
        salida.append({"id": regla["id"], "nombre": regla["nombre"], "tipo": regla["tipo"],
                       "alcance": texto_alcance(regla["alcance"], engine.campaigns), "condicion": texto_condicion(regla["condicion"]),
                       "bloqueados": bloqueados})
    return salida


def celdas(engine, idx, sector_de, tabla, contactos):
    """Una fila por sector x campaña: elegibles, viables, contactos asignados, valor y embudo de reglas."""
    campanas, n_c, n_s = engine.campaigns, len(engine.campaigns), len(tabla)
    umbral = engine.params["priorizacion"]["umbral_score_producto"]
    celda = contactos["sector"] * n_c + contactos["campana"]
    contactos_n = np.bincount(celda, minlength=n_s * n_c)
    valor = np.bincount(celda, weights=contactos["p0"] * contactos["vn"], minlength=n_s * n_c)
    p0 = np.bincount(celda, weights=contactos["p0"], minlength=n_s * n_c)
    sector_de = np.asarray(sector_de)
    salida = []
    for j, camp in enumerate(campanas):
        viable = np.any([engine.feasible[h][idx, j] for h in range(engine.k)], axis=0)
        bloques = list(engine.product_blocks[j])
        if not engine.active[j]:
            bloques.insert(0, (np.ones(engine.n, bool), "Campaña inactiva o fuera de vigencia"))
        for s, fila in enumerate(tabla.itertuples()):
            miembros = np.flatnonzero(sector_de == s)
            filas = idx[miembros]
            resto = np.ones(len(filas), bool)
            pasos = []
            for mascara, nombre in bloques:
                # `eliminados` es secuencial (cada cliente se cuenta en la primera regla que lo toca, en el orden del motor);
                # `solo` es lo que esa regla elimina por sí sola: con él se nombra la regla responsable de un bloqueo
                quita = mascara[filas] & resto
                resto &= ~mascara[filas]
                if mascara[filas].any():
                    nombre = f"Score de producto menor a {umbral}" if nombre.startswith("Score de producto") else nombre
                    pasos.append({"nombre": nombre, "eliminados": int(quita.sum()), "solo": int(mascara[filas].sum())})
            elegibles = int(resto.sum())
            viables = int((resto & viable[miembros]).sum())
            if elegibles - viables:
                pasos.append({"nombre": "Sin canal habilitado o con tope semanal", "eliminados": elegibles - viables,
                              "solo": elegibles - viables})
            i = s * n_c + j
            n = int(len(filas))
            bloqueada = bool(n and viables == 0)
            # ante un empate se nombra la regla de negocio y no el umbral de score
            responsable = max(pasos, key=lambda p: (p["solo"], not p["nombre"].startswith("Score de producto"))) if pasos else None
            tambien = [p["nombre"] for p in pasos if responsable and p is not responsable and p["solo"] >= responsable["solo"] * 0.999]
            salida.append({
                "sector": fila.sector, "campana": camp["id"], "clientes": n, "elegibles": elegibles, "viables": viables,
                "contactos": int(contactos_n[i]), "valor": round(float(valor[i]), 4),
                "valor_por_cliente": round(float(valor[i] / n), 5) if n else 0.0,
                "conversion_pct": round(float(100 * p0[i] / contactos_n[i]), 3) if contactos_n[i] else 0.0,
                "bloqueada": bloqueada, "bloqueo": responsable["nombre"] if bloqueada and responsable else None,
                "bloqueo_pct": round(100 * responsable["solo"] / n, 1) if bloqueada and responsable else None,
                "bloqueo_tambien": tambien if bloqueada else [], "pasos": pasos})
    return salida


def por_estrato(celdas_lista, tabla):
    """Suma por estrato y campaña: es lo que se pinta sobre el mapa (los clientes no tienen manzana)."""
    estrato = dict(zip(tabla["sector"], tabla["estrato"]))
    acum = {}
    for c in celdas_lista:
        a = acum.setdefault((int(estrato[c["sector"]]), c["campana"]),
                            {"clientes": 0, "elegibles": 0, "viables": 0, "contactos": 0, "valor": 0.0, "p0": 0.0})
        for k in ("clientes", "elegibles", "viables", "contactos", "valor"):
            a[k] += c[k]
        a["p0"] += c["conversion_pct"] * c["contactos"] / 100
    salida = []
    for (e, camp), a in sorted(acum.items()):
        salida.append({"estrato": e, "campana": camp, "clientes": a["clientes"], "elegibles": a["elegibles"], "viables": a["viables"],
                       "contactos": a["contactos"], "valor": round(a["valor"], 4),
                       "valor_por_cliente": round(a["valor"] / a["clientes"], 5) if a["clientes"] else 0.0,
                       "conversion_pct": round(100 * a["p0"] / a["contactos"], 3) if a["contactos"] else 0.0})
    return salida


def escenario(engine, parrilla, idx, sector_de, tabla, contactos, id_, nombre, regla=None):
    lista = celdas(engine, idx, sector_de, tabla, contactos)
    return {"id": id_, "nombre": nombre,
            "regla": None if regla is None else {"id": regla["id"], "nombre": regla["nombre"],
                                                 "alcance": texto_alcance(regla["alcance"], engine.campaigns),
                                                 "condicion": texto_condicion(regla["condicion"])},
            "valor_total": round(valor_de_parrilla(engine, parrilla), 2),
            "valor_region": round(float((contactos["p0"] * contactos["vn"]).sum()), 2),
            "celdas": lista, "estratos": por_estrato(lista, tabla), "reglas": reglas_vigentes(engine, idx)}


def con_regla(config_nba, regla):
    nueva = deepcopy(config_nba)
    nueva["reglas"].append(regla)
    return nueva


def correr_escenario(datos, config_nba, regla, fecha):
    """Vuelve a correr el motor NBA con una regla adicional; devuelve (motor, parrilla, config)."""
    cfg = con_regla(config_nba, regla)
    motor = Engine(datos, cfg, fecha)
    parrilla, _ = motor.optimize()
    return motor, parrilla, cfg

"""Validador generico: revisa una parrilla contra CUALQUIER configuracion.

Independiente del motor: evalua cliente por cliente con Python puro (sin pandas
vectorizado ni las funciones de nba.py), para que un error del motor no se
auto-apruebe. Sirve para las pruebas de robustez con configuraciones al azar.
"""
import operator

import pandas as pd

OPS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def _n(x):
    try:
        f = float(x)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return x


def _cond(fila_cli, r, producto):
    x = fila_cli[r["atributo"]]
    v = producto if r["valor"] == "$producto" else r["valor"]
    op = r["operador"]
    if op in OPS:
        try:
            return bool(OPS[op](x, _n(v)))
        except TypeError:
            return False
    lista = [s for s in str(v).split("|") if s]
    if op == "en":
        return str(x) in lista
    if op == "no_en":
        return str(x) not in lista
    items = [] if pd.isna(x) else str(x).split("|")
    if op == "contiene":
        return str(v) in items
    if op == "no_contiene":
        return str(v) not in items
    if op == "entre":
        lo, hi = (_n(s) for s in lista)
        return lo <= x <= hi
    raise ValueError(op)


def _excluye(fila_cli, filas, producto=None):
    c = all(_cond(fila_cli, r, producto) for r in filas)
    return c if filas[0]["accion"] == "excluir" else not c


def validar_generico(parrilla, clientes, cfg):
    P = cfg.params
    camp = {r["id"]: r for r in cfg.campanas.to_dict("records")}
    reglas = {}
    for r in cfg.reglas.to_dict("records"):
        if str(r["activa"]) == "1":
            reglas.setdefault(r["id"], []).append(r)
    up, uc = float(P["priorizacion.umbral_score_producto"]), float(P["canal.umbral_score_canal"])
    tope_sem = int(P["politica_contacto.max_contactos_semana"])
    canales = [k.split(".")[-1] for k in P if k.startswith("canal.capacidad_por_corrida.")]
    cli = clientes.set_index("id_cliente").to_dict("index")
    viol = {"elegibilidad": 0, "canal": 0, "umbral_producto": 0, "umbral_canal": 0, "canal_permitido": 0,
            "campana_inactiva": 0, "productos_por_contacto": 0, "tope_semanal": 0, "un_canal": 0, "cupo": 0}
    uso = {c: 0 for c in canales}
    for f in parrilla[parrilla.estado == "asignado"].to_dict("records"):
        c, ch = cli[f["id_cliente"]], f["canal"]
        uso[ch] = uso.get(ch, 0) + 1
        prods = [p for p in (f["campana_1"], f["campana_2"]) if isinstance(p, str) and p]
        for pid in prods:
            k = camp[pid]
            viol["campana_inactiva"] += int(k["activa"] != 1)
            viol["umbral_producto"] += int(c[k["columna_score"]] < up)
            viol["canal_permitido"] += int(ch not in k["canales_permitidos"].split("|"))
            for filas in reglas.values():
                r0 = filas[0]
                if r0["tipo"] != "elegibilidad":
                    continue
                aplica = (r0["alcance_nivel"] == "global"
                          or (r0["alcance_nivel"] == "campana" and pid in str(r0["alcance_valores"]).split("|"))
                          or (r0["alcance_nivel"] == "grupo" and (k["producto"] in str(r0["alcance_valores"]).split("|")
                                                                  or k["objetivo"] in str(r0["alcance_valores"]).split("|"))))
                viol["elegibilidad"] += int(aplica and _excluye(c, filas, k["producto"]))
        for filas in reglas.values():
            r0 = filas[0]
            if r0["tipo"] == "canal" and (r0["alcance_nivel"] == "global" or ch in str(r0["alcance_valores"]).split("|")):
                viol["canal"] += int(_excluye(c, filas))
        viol["umbral_canal"] += int(c[f"score_canal_{ch}"] < uc)
        viol["productos_por_contacto"] += int(len(prods) > int(P[f"politica_contacto.max_productos_por_canal.{ch}"]))
        viol["tope_semanal"] += int(c["contactos_semana_actual"] + 1 > tope_sem)
    viol["un_canal"] = int(parrilla.id_cliente.duplicated().sum())
    viol["cupo"] = sum(max(0, uso.get(ch, 0) - int(P[f"canal.capacidad_por_corrida.{ch}"])) for ch in canales)
    viol["total"] = sum(viol.values())
    return viol

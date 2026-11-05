"""Validador independiente de las 16 restricciones (R01-R16 del documento del reto).

Escrito aparte del motor a proposito: no reutiliza su logica de reglas, para que
un error del motor no se 'auto-apruebe'. Lee los mismos umbrales de config.
"""
import numpy as np
import pandas as pd


def validar(parrilla: pd.DataFrame, clientes: pd.DataFrame, cfg) -> dict:
    camp = cfg.campanas.set_index("id")
    df = clientes.set_index("id_cliente").loc[parrilla.id_cliente]
    a = parrilla.set_index("id_cliente")
    v = {f"R{i:02d}": 0 for i in range(1, 17)}
    up = float(cfg.p("priorizacion.umbral_score_producto"))
    uc = float(cfg.p("canal.umbral_score_canal"))
    tope_sem = int(cfg.p("politica_contacto.max_contactos_semana"))
    asign = a[a.estado == "asignado"]
    for cid, fila in asign.iterrows():
        c = df.loc[cid]
        ch = fila.canal
        prods = [x for x in (fila.campana_1, fila.campana_2) if isinstance(x, str) and x]
        for p in prods:
            k = camp.loc[p]
            v["R01"] += int(c.en_mora == 1)
            v["R02"] += int(k.producto == "TER" and c.calificacion_riesgo not in ("E", "A", "B"))
            v["R03"] += int(k.producto == "TER" and c.edad_equipo_meses < 18)
            v["R04"] += int(k.producto == "VCH" and c.tiene_hogar == 1)
            v["R05"] += int(k.producto == "OTT" and c.cantidad_ott >= 3)
            v["R06"] += int(k.producto in str(c.productos_ofertados_mes).split("|"))
            v["R07"] += int(c.quejas_90d >= 3)
            v["R08"] += int(c[k.columna_score] < up)
            v["R12"] += int(ch not in k.canales_permitidos.split("|"))
        if ch in ("whatsapp", "correo", "sms"):
            v["R09"] += int(c[f"autoriza_{ch}"] != 1)
        if ch == "asesor":
            v["R10"] += int(c.contactos_asesor_mes >= 2)
        v["R11"] += int(c[f"score_canal_{ch}"] < uc)
        v["R14"] += int(len(prods) > int(cfg.p(f"politica_contacto.max_productos_por_canal.{ch}")))
        v["R15"] += int(c.contactos_semana_actual + 1 > tope_sem)
    v["R13"] = int(parrilla.id_cliente.duplicated().sum())
    uso = asign.canal.value_counts()
    v["R16"] = int(sum(max(0, uso.get(ch, 0) - cfg.cupo(ch)) for ch in cfg.canales))
    v["total"] = sum(v.values())
    return v

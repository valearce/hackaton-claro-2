"""Sondeo de comportamiento por estrato: qué consume y cómo se comporta cada estrato, y qué NO cambia entre ellos.

El CSV no trae «flujo» (compras, uso mes a mes, respuestas ni horarios): solo variables de consumo y
comportamiento por cliente. Este sondeo las resume por estrato y mide cuáles lo distinguen de verdad. Es el punto
de partida de los clusters por comportamiento.

    python -m modelo.experimentos.comportamiento"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..rutas import DATOS
from .sectores import filtrar_region

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "evaluacion"
UMBRAL_DISTINGUE = 0.3  # diferencia entre el estrato más alto y el más bajo, en desviaciones de la población


def variables(b):
    """(id, nombre, unidad, serie por cliente). Los porcentajes son medias de 0/1 por 100."""
    pct = lambda s: s.astype(float) * 100
    return [
        ("hogar", "Tienen servicio Hogar", "%", pct(b["tiene_hogar"])),
        ("netflix", "Tienen Netflix", "%", pct(b["tiene_netflix"])),
        ("amazon", "Tienen Amazon Prime", "%", pct(b["tiene_amazon_prime"])),
        ("win", "Tienen Win", "%", pct(b["tiene_win"])),
        ("ott", "Plataformas de streaming por cliente", "", b["cantidad_ott"].astype(float)),
        ("banca", "Usan banca digital", "%", pct(b["usa_banca_digital"])),
        ("compras", "Compran en línea", "%", pct(b["compras_digitales"])),
        ("redes", "Activos en redes sociales", "%", pct(b["usa_redes_sociales"])),
        ("consumo", "Consumo del plan de datos", "%", b["consumo_datos_pct"].astype(float)),
        ("ilimitado", "Plan de datos ilimitado", "%", pct(b["plan_datos_gb"].astype(float).eq(999))),
        ("postpago", "Línea postpago", "%", pct(b["tipo_linea"].eq("Postpago"))),
        ("arpu", "ARPU móvil (COP al mes)", "COP", b["arpu_movil"].astype(float)),
        ("gama_alta", "Equipo de gama alta", "%", pct(b["gama_equipo"].eq("Alta"))),
        ("edad", "Edad (años)", "", b["edad"].astype(float)),
        ("antiguedad", "Antigüedad (meses)", "", b["antiguedad_meses"].astype(float)),
        ("churn", "Riesgo de fuga", "", b["riesgo_churn"].astype(float)),
        ("mora", "En mora", "%", pct(b["en_mora"])),
        ("quejas", "Quejas en 90 días por cliente", "", b["quejas_90d"].astype(float)),
    ]


def sondeo(region):
    """Medias por estrato, tamaño de efecto contra la población y si la variable distingue a los estratos."""
    estrato = region["estrato"].astype(int)
    salida = []
    for id_, nombre, unidad, serie in variables(region):
        medias = serie.groupby(estrato).mean()
        desviacion = float(serie.std(ddof=0)) or 1.0
        efecto = (medias - serie.mean()) / desviacion
        rango = float(efecto.max() - efecto.min())
        salida.append({"id": id_, "nombre": nombre, "unidad": unidad, "bogota": float(serie.mean()),
                       "valores": {str(e): float(v) for e, v in medias.items()},
                       "efecto": {str(e): float(v) for e, v in efecto.items()},
                       "rango_efecto": rango, "distingue": rango >= UMBRAL_DISTINGUE})
    salida.sort(key=lambda v: -v["rango_efecto"])
    por_estrato = {}
    for e in sorted(estrato.unique()):
        fuertes = sorted((v for v in salida if v["distingue"]), key=lambda v: -abs(v["efecto"][str(e)]))
        por_estrato[str(e)] = {"clientes": int((estrato == e).sum()),
                               "destaca": [{"id": v["id"], "nombre": v["nombre"], "efecto": v["efecto"][str(e)]}
                                           for v in fuertes if v["efecto"][str(e)] > 0][:3],
                               "menos": [{"id": v["id"], "nombre": v["nombre"], "efecto": v["efecto"][str(e)]}
                                         for v in fuertes if v["efecto"][str(e)] < 0][:3]}
    return {"umbral_distingue": UMBRAL_DISTINGUE, "variables": salida, "estratos": por_estrato}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", type=Path, default=DATOS)
    ap.add_argument("--config", type=Path, default=AQUI / "config.json")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    region = filtrar_region(pd.read_csv(args.datos, keep_default_na=False), config["region"])
    resultado = {"descripcion": "Sondeo de comportamiento por estrato (ver comportamiento.py)", "region": config["region"],
                 "clientes": int(len(region)),
                 "nota": "El CSV no trae flujo (compras, uso mes a mes, respuestas ni horarios): son variables de consumo y comportamiento por cliente.",
                 **sondeo(region)}
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / "comportamiento.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    distinguen = [v["nombre"] for v in resultado["variables"] if v["distingue"]]
    print(f"{len(distinguen)} de {len(resultado['variables'])} variables distinguen a los estratos: " + "; ".join(distinguen))


if __name__ == "__main__":
    main()

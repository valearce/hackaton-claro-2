"""Exporta los clusters y la publicidad por cluster a la consola del Grupo 5 (proyecto hackatonv.2).

La consola no tiene mapa: muestra cuántos clusters se hicieron, qué publicidad recibe cada uno y su rendimiento.
Este script corre todo el pipeline sobre los 100.000 clientes (no solo Bogotá) y escribe, dentro de la consola:

    app/static/datos/clusters.json   clusters, publicidad por cluster y rendimiento (precalculado)
    datos/clusters.csv               cluster y sector de cada cliente (la consola lo usa para el desglose en vivo)

    python -m modelo.experimentos.exportar_app --app C:\\ruta\\a\\hackatonv.2

El desglose del motor por cluster se calcula en vivo en la consola con cada simulación; aquí solo va lo que no
depende de la configuración que negocio mueva (los clusters y los mensajes)."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from ..nba import Engine, load_config
from ..rutas import DATOS
from . import propuestas, simulador as sim
from .sectores import (RASGOS, config_perfil, construir_sectores, nombrar_perfiles, rasgos_cliente, segmentar)

AQUI = Path(__file__).resolve().parent
ADVERTENCIA = ("Los clusters son descriptivos (se forman con consumo de datos, streaming, uso digital y Hogar). El rendimiento de los "
               "mensajes es simulado con supuestos declarados: el CSV del reto no trae compras ni respuestas.")


def publicidad_por_cluster(recs, config, tabla, campanas, nombres_cluster):
    """Por cluster y campaña: reparto esperado de las propuestas, la principal, su texto y la recomendada en cada estrato."""
    filas_z = {f.sector: {r: float(getattr(f, f"z_{r}")) for r in RASGOS} for f in tabla.itertuples()}
    por = {}
    for r in recs:
        if r["sector"].endswith("otros"):
            continue
        por.setdefault((r["sector"].split("-")[1], r["campana"]), []).append(r)
    variantes = list(config["variantes"])
    nombres = propuestas.nombres_variantes(config)
    salida = []
    for (cluster, camp), lista in sorted(por.items()):
        peso = {v: 0.0 for v in variantes}
        for r in lista:
            probs = {r["recomendada"]: r["p_mejor"], **{a["variante"]: a["p_mejor"] for a in r["alternativas"]}}
            for v, p in probs.items():
                peso[v] += r["contactos"] * p
        total = sum(peso.values()) or 1.0
        reparto = {v: peso[v] / total for v in variantes}
        principal = max(reparto, key=reparto.get)
        mayor = max(lista, key=lambda r: r["contactos"])
        texto = propuestas.redactar(config, campanas[camp], principal, filas_z[mayor["sector"]], mayor["canal_tipico"])
        salida.append({
            "cluster": cluster, "campana": camp, "contactos": int(sum(r["contactos"] for r in lista)),
            "principal": principal, "principal_nombre": nombres[principal], "reparto": {v: round(reparto[v], 4) for v in variantes},
            "texto": texto, "canal_tipico": mayor["canal_tipico"],
            "por_estrato": [{"estrato": r["estrato"], "contactos": r["contactos"], "variante": r["recomendada"],
                             "nombre": r["recomendada_nombre"], "p_mejor": round(r["p_mejor"], 3),
                             "lift_estimado_pct": round(r["lift_estimado_pct"], 1), "texto": r["texto"]}
                            for r in sorted(lista, key=lambda r: r["estrato"])]})
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", type=Path, default=DATOS)
    ap.add_argument("--config", type=Path, default=AQUI / "config.json")
    ap.add_argument("--app", type=Path, required=True, help="carpeta del proyecto de la consola (hackatonv.2)")
    ap.add_argument("--repeticiones", type=int)
    args = ap.parse_args()
    inicio = time.perf_counter()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    config["region"] = None  # la consola trabaja con los 100.000 clientes
    perfiles = json.loads((AQUI.parent / "config" / "perfiles.json").read_text(encoding="utf-8-sig"))
    nba = load_config()
    datos = pd.read_csv(args.datos, keep_default_na=False)

    print(f"NBA: asignando {len(datos):,} clientes", flush=True)
    parrilla, _ = Engine(datos, nba, config["fecha"]).optimize()
    cfg_perfil = config_perfil(config, perfiles)
    tabla, sector_de, z = construir_sectores(datos, cfg_perfil, config["sectores"], config["semilla"])
    perfil_cliente = segmentar(datos, cfg_perfil, config["sectores"]["k_perfiles"], config["sectores"]["componentes_pca"], config["semilla"])
    nombres = nombrar_perfiles(rasgos_cliente(datos), perfil_cliente)
    contactos = sim.contactos_de_parrilla(datos, parrilla, nba, sector_de, len(tabla))
    print(f"{len(datos):,} clientes, {len(tabla)} segmentos, {len(contactos['p0']):,} contactos", flush=True)

    k = config["sectores"]["k_perfiles"]
    masks = {f"P{c + 1}": perfil_cliente[contactos["fila"]] == c for c in range(k)}
    reps = args.repeticiones or config["experimento"]["repeticiones"]
    base, primera = sim.evaluar(contactos, z, config, reps, subconjuntos=masks)
    sensibilidad = []
    for esc in config["verdad_simulada"]["escenarios"]:
        r, _ = sim.evaluar(contactos, z, config, config["experimento"]["repeticiones_sensibilidad"], esc)
        sensibilidad.append({"nombre": esc["nombre"], "sector": r["politicas"]["bandido_sector"]["mejora_pct_media"],
                             "global": r["politicas"]["ganador_global"]["mejora_pct_media"]})
        print(f"  {esc['nombre']}: sector {sensibilidad[-1]['sector']:+.2f} %, A/B global {sensibilidad[-1]['global']:+.2f} %", flush=True)
    recs = sim.recomendaciones(contactos, tabla, config, primera, nba["campanas"])
    campanas = {c["id"]: c for c in nba["campanas"]}

    rasgos = rasgos_cliente(datos)
    estrato = datos["estrato"].astype(int).to_numpy()
    clusters = []
    for c in range(k):
        m = perfil_cliente == c
        clusters.append({
            "id": f"P{c + 1}", "nombre": nombres[c], "clientes": int(m.sum()),
            "estratos": {str(e): int((m & (estrato == e)).sum()) for e in range(1, 7)},
            "rasgos": {r: round(float(rasgos.loc[m, r].mean()), 4) for r in ("hogar", "netflix", "amazon", "win", "banca", "compras", "redes", "ilimitado", "postpago")},
            "consumo_datos_pct": round(float(rasgos.loc[m, "consumo"].mean()), 1),
            "mejora_publicidad": {p: round(base["subconjuntos"][f"P{c + 1}"]["politicas"][pol][clave], 2)
                                  for p, pol in (("sector", "bandido_sector"), ("global", "ganador_global"))
                                  for clave in ("mejora_pct_media",)} | {
                "p5": round(base["subconjuntos"][f"P{c + 1}"]["politicas"]["bandido_sector"]["mejora_pct_p5"], 2),
                "p95": round(base["subconjuntos"][f"P{c + 1}"]["politicas"]["bandido_sector"]["mejora_pct_p95"], 2),
                "contactos": base["subconjuntos"][f"P{c + 1}"]["contactos"]}})
    p = base["politicas"]
    resumen = {
        "advertencia": ADVERTENCIA,
        "meta": {"clientes": int(len(datos)), "clusters": k, "segmentos": int(len(tabla)), "contactos": int(len(contactos["p0"])),
                 "perfil": config["sectores"]["perfil"], "variables": config["sectores"]["variables_comportamiento"]["binarias"]
                 + config["sectores"]["variables_comportamiento"]["numericas"], "fecha": config["fecha"]},
        "campanas": {cid: c["nombre"] for cid, c in campanas.items()},
        "variantes": propuestas.nombres_variantes(config),
        "clusters": clusters,
        "publicidad": publicidad_por_cluster(recs, config, tabla, campanas, nombres),
        "rendimiento": {
            "politicas": {n: {"mejora_pct": round(p[n]["mejora_pct_media"], 2), "p5": round(p[n]["mejora_pct_p5"], 2), "p95": round(p[n]["mejora_pct_p95"], 2)}
                          for n in ("bandido_sector", "ganador_global", "bandido_global", "oraculo")},
            "curvas": {n: [round(v, 3) for v in base["curva_acumulada_pct"][n]] for n in ("bandido_sector", "ganador_global", "bandido_global", "oraculo")},
            "identificacion_pct": round(base["identificacion_pct"], 1), "repeticiones": reps, "oleadas": config["experimento"]["oleadas"],
            "sensibilidad": sensibilidad},
        "segundos": round(time.perf_counter() - inicio, 1)}

    salida_json = args.app / "app" / "static" / "datos" / "clusters.json"
    salida_json.parent.mkdir(parents=True, exist_ok=True)
    salida_json.write_text(json.dumps(resumen, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    sectores_id = tabla["sector"].to_numpy()[sector_de]
    pd.DataFrame({"id_cliente": datos["id_cliente"], "cluster": [f"P{c + 1}" for c in perfil_cliente], "estrato": estrato,
                  "sector": sectores_id}).to_csv(args.app / "datos" / "clusters.csv", index=False)
    print(f"Escrito {salida_json} y datos/clusters.csv ({resumen['segundos']} s)")
    for c in clusters:
        print(f"  {c['id']} {c['clientes']:>6,} clientes · {c['nombre']}")


if __name__ == "__main__":
    main()

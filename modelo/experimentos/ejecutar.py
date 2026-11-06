"""Ejecuta el experimento completo: parrilla NBA -> sectores de Bogotá -> propuestas -> simulación.

    python -m modelo.experimentos
    python -m modelo.experimentos --parrilla modelo/resultados/nba/parrilla_optimo.csv   # reutiliza una parrilla

Escribe en modelo/evaluacion/: experimentos.json (lo lee el mapa), propuestas_por_sector.csv y una gráfica."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .motor_analisis import Engine, load_config
from ..rutas import DATOS, RAIZ
from . import propuestas, simulador as sim, viabilidad
from .sectores import RASGOS, config_perfil, construir_sectores, filtrar_region, indices_region

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "evaluacion"
ADVERTENCIA = ("Resultados sobre un mundo simulado con supuestos declarados: el CSV del reto no trae compras ni respuestas. "
               "Demuestran que el mecanismo aprende y cuánto ganaría si esos supuestos fueran ciertos; no prueban "
               "que las propuestas funcionen en clientes reales.")


def escribir_json(ruta, valor):
    ruta.write_text(json.dumps(valor, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")


def grafica(ruta, base, escenarios):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colores = {"bandido_sector": "#DA291C", "ganador_global": "#555555", "bandido_global": "#999999", "oraculo": "#2a9d5b"}
    nombres = {"bandido_sector": "Bandido por sector", "ganador_global": "A/B global (ganador único)",
               "bandido_global": "Bandido global", "oraculo": "Oráculo (techo)"}
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(1, len(base["curva_acumulada_pct"]["oraculo"]) + 1)
    for p in ("oraculo", "bandido_sector", "bandido_global", "ganador_global"):
        ax[0].plot(x, base["curva_acumulada_pct"][p], label=nombres[p], color=colores[p], lw=2.4 if p == "bandido_sector" else 1.6)
    ax[0].axhline(0, color="#bbb", lw=1)
    ax[0].set(xlabel="Oleada de contactos", ylabel="Mejora acumulada del valor esperado vs. reparto uniforme (%)",
              title="Qué tan rápido aprende cada política")
    ax[0].legend(frameon=False, fontsize=9)
    ancho = 0.26
    pos = np.arange(len(escenarios))
    for i, p in enumerate(("bandido_sector", "bandido_global", "ganador_global")):
        ax[1].bar(pos + (i - 1) * ancho, [e["politicas"][p]["mejora_pct_media"] for e in escenarios], ancho,
                  label=nombres[p], color=colores[p])
    ax[1].set_xticks(pos, [e["nombre"].replace(" entre sectores", "\nentre sectores").replace(" del informe", "\ndel informe")
                           for e in escenarios], fontsize=8)
    ax[1].axhline(0, color="#bbb", lw=1)
    ax[1].set(ylabel="Mejora vs. reparto uniforme (%)", title="Cuánto importan las diferencias entre sectores")
    ax[1].legend(frameon=False, fontsize=9)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", type=Path, default=DATOS)
    ap.add_argument("--config", type=Path, default=AQUI / "config.json")
    ap.add_argument("--parrilla", type=Path, help="CSV de una parrilla NBA ya calculada (si no, se calcula)")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--repeticiones", type=int)
    ap.add_argument("--sin-grafico", action="store_true")
    ap.add_argument("--sin-restricciones", action="store_true", help="No corre las restricciones hipotéticas (cada una vuelve a correr el motor, ~25 s)")
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    perfiles = json.loads((AQUI.parent / "config" / "perfiles.json").read_text(encoding="utf-8-sig"))
    nba = load_config()
    datos = pd.read_csv(args.datos, keep_default_na=False)
    inicio = time.perf_counter()
    motor = Engine(datos, nba, config["fecha"])
    if args.parrilla:
        parrilla = pd.read_csv(args.parrilla, keep_default_na=False)
    else:
        print(f"NBA: asignando {len(datos):,} clientes", flush=True)
        parrilla, _ = motor.optimize()
    region = filtrar_region(datos, config["region"])
    idx_region = indices_region(datos, config["region"])
    tabla, sector_de, z = construir_sectores(region, config_perfil(config, perfiles), config["sectores"], config["semilla"])
    contactos = sim.contactos_de_parrilla(region, parrilla, nba, sector_de, len(tabla))
    print(f"{config['region']}: {len(region):,} clientes, {len(tabla)} sectores, {len(contactos['p0']):,} contactos", flush=True)

    # viabilidad: reglas actuales y, para cada restricción hipotética, una corrida real del motor con la regla añadida
    vias = [viabilidad.escenario(motor, parrilla, idx_region, sector_de, tabla, contactos, "base", "Reglas actuales")]
    for h in ([] if args.sin_restricciones else config.get("restricciones_hipoteticas", [])):
        print(f"  restricción «{h['nombre']}»: corriendo el motor", flush=True)
        motor_h, parrilla_h, nba_h = viabilidad.correr_escenario(datos, nba, h["regla"], config["fecha"])
        contactos_h = sim.contactos_de_parrilla(region, parrilla_h, nba_h, sector_de, len(tabla))
        vias.append(viabilidad.escenario(motor_h, parrilla_h, idx_region, sector_de, tabla, contactos_h, h["id"], h["nombre"], h["regla"]))
    for v in vias:
        v["delta_valor_total"] = round(v["valor_total"] - vias[0]["valor_total"], 2)
        v["delta_valor_total_pct"] = round(100 * v["delta_valor_total"] / vias[0]["valor_total"], 2)
        v["delta_valor_region"] = round(v["valor_region"] - vias[0]["valor_region"], 2)

    reps = args.repeticiones or config["experimento"]["repeticiones"]
    base, primera = sim.evaluar(contactos, z, config, reps)
    escenarios = []
    for escenario in config["verdad_simulada"]["escenarios"]:
        r, _ = sim.evaluar(contactos, z, config, config["experimento"]["repeticiones_sensibilidad"], escenario)
        escenarios.append({**escenario, **r})
        print(f"  {escenario['nombre']}: bandido por sector {r['politicas']['bandido_sector']['mejora_pct_media']:+.2f} %, "
              f"A/B global {r['politicas']['ganador_global']['mejora_pct_media']:+.2f} %", flush=True)
    recs = sim.recomendaciones(contactos, tabla, config, primera, nba["campanas"])

    args.salida.mkdir(parents=True, exist_ok=True)
    nombres_campana = {c["id"]: c["nombre"] for c in nba["campanas"]}
    campo_csv = ["sector", "nombre", "estrato", "clientes", "campana", "contactos", "canal_tipico", "recomendada_nombre",
                 "p_mejor", "lift_estimado_pct", "tasa_esperada_pct", "texto"]
    plano = pd.DataFrame(recs)
    plano["lift_ic90_pct"] = [f"{a:+.0f} a {b:+.0f}" for a, b in plano["lift_ic90_pct"]]
    plano[campo_csv + ["lift_ic90_pct"]].round(4).to_csv(args.salida / "propuestas_por_sector.csv", index=False, encoding="utf-8")
    resumen = {
        "descripcion": "Propuestas por sector (estrato x perfil) con reparto bayesiano; ver modelo/experimentos/README.md",
        "advertencia": ADVERTENCIA, "fecha": config["fecha"], "region": config["region"],
        "datos": {"clientes_region": int(len(region)), "sectores": int(len(tabla)), "contactos": int(len(contactos["p0"])),
                  "valor_esperado_parrilla_region": float((contactos["p0"] * contactos["vn"]).sum())},
        "supuestos": {"verdad_simulada": config["verdad_simulada"], "experimento": config["experimento"],
                      "variantes": {k: {"nombre": v["nombre"], "afinidad": v["afinidad"]} for k, v in config["variantes"].items()}},
        "campanas": nombres_campana, "variantes": propuestas.nombres_variantes(config),
        "rendimiento": base, "escenarios": escenarios,
        "viabilidad": {"campanas": {c["id"]: {"nombre": c["nombre"], "valor_negocio": c["valor_negocio"]} for c in nba["campanas"]},
                       "escenarios": vias},
        "acierto_recomendacion_pct": float(100 * np.mean([r["acierto"] for r in recs])),
        "sectores": [{**{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in fila.items()
                         if not k.startswith("rasgo_")}} for fila in tabla.to_dict("records")],
        "recomendaciones": recs,
        "tiempo_segundos": round(time.perf_counter() - inicio, 1),
    }
    escribir_json(args.salida / "experimentos.json", resumen)
    if not args.sin_grafico:
        grafica(args.salida / "experimentos_rendimiento.png", base, escenarios)
    p = base["politicas"]
    print(f"\nRendimiento vs. reparto uniforme ({reps} repeticiones, escenario base):")
    for nombre in sim.POLITICAS:
        v = p[nombre]
        print(f"  {nombre:16s} {v['mejora_pct_media']:+6.2f} %  (5-95 %: {v['mejora_pct_p5']:+.2f} a {v['mejora_pct_p95']:+.2f})")
    print(f"Identificación de la mejor propuesta: {base['identificacion_pct']:.0f} % de los contactos")
    print(f"Escrito en {args.salida}")


if __name__ == "__main__":
    main()

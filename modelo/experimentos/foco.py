"""Foco en los clusters más probables: ¿cuánto sube el valor si se corre el motor NBA enfocado en ellos?

Un cluster «muy probable» es un sector (estrato x perfil) con mucho valor esperado por cliente. El motor NBA
maximiza el valor total con cupos limitados, así que «enfocar» tiene tres lecturas, y las tres se miden:

1. Cupo aislado: el motor corre solo con los clientes del cluster y todo el cupo de canales es para ellos. Es el
   techo de lo que se podría ganar ahí, y no es alcanzable (nadie más recibiría nada).
2. Mismo presupuesto, con prioridad: se corre la población completa con los mismos cupos, pero la utilidad de los
   clientes del cluster pesa N veces más. Lo que sube en el cluster se le quita a otros clientes; el valor total
   no puede superar al del óptimo global.
3. Propuestas de mensaje: encima de lo anterior, la mejora del reparto por sector medida en el simulador (supuestos
   declarados: el CSV no trae respuestas reales).

    python -m modelo.experimentos.foco"""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .motor_analisis import Bundle, Engine, load_config
from ..rutas import DATOS
from . import simulador as sim, viabilidad
from .sectores import config_perfil, construir_sectores, filtrar_region, indices_region

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "evaluacion"


class EngineFoco(Engine):
    """Motor NBA donde la utilidad de cada cliente se multiplica por un peso (los demás datos no cambian)."""

    def __init__(self, data, config, as_of, peso):
        self._peso = np.asarray(peso, dtype=float)
        super().__init__(data, config, as_of)

    def bundles(self, objective):
        return [Bundle(b.picks, b.utility * self._peso, b.expected) for b in super().bundles(objective)]


def valor_por_cliente(motor, parrilla):
    """Valor esperado (score producto x score canal x valor) de cada cliente, en el orden del motor."""
    g = parrilla.set_index("id_cliente").reindex(motor.ids)
    ids = [c["id"] for c in motor.campaigns]
    salida = np.zeros(motor.n)
    for col in ("campana_1", "campana_2"):
        filas = np.flatnonzero((g["estado"] == "asignado").to_numpy() & (g[col].fillna("") != "").to_numpy())
        j = np.array([ids.index(x) for x in g[col].to_numpy()[filas]], dtype=int)
        k = np.array([motor.channels.index(x) for x in g["canal"].to_numpy()[filas]], dtype=int)
        salida[filas] += motor.product_scores[filas, j] * motor.channel_scores[filas, k] * motor.values[j]
    return salida


def ranking_sectores(celdas_lista, tabla, criterio="valor_por_cliente"):
    """Sectores de más a menos probables. Por defecto: valor esperado por cliente de la parrilla actual."""
    valor = {}
    for c in celdas_lista:
        valor[c["sector"]] = valor.get(c["sector"], 0.0) + c["valor"]
    filas = []
    for i, f in enumerate(tabla.itertuples()):
        if f.sector.endswith("otros"):  # celda residual que junta perfiles pequeños: no es un cluster
            continue
        filas.append({"indice": i, "sector": f.sector, "nombre": f.nombre, "estrato": int(f.estrato), "clientes": int(f.clientes),
                      "valor": round(valor.get(f.sector, 0.0), 3),
                      "valor_por_cliente": round(valor.get(f.sector, 0.0) / f.clientes, 5)})
    clave = "valor" if criterio == "valor_total" else "valor_por_cliente"
    return sorted(filas, key=lambda r: -r[clave])


def medir(motor, parrilla, valor_cli, foco_filas, region_filas):
    """Valor dentro del foco, en el resto de la región y en todo el país, y clientes con acción en el foco."""
    g = parrilla.set_index("id_cliente").reindex(motor.ids)
    con_accion = (g["estado"] == "asignado").to_numpy()
    resto = region_filas & ~foco_filas
    return {"valor_foco": float(valor_cli[foco_filas].sum()), "valor_resto_region": float(valor_cli[resto].sum()),
            "valor_total": float(valor_cli.sum()), "clientes_con_accion": int(con_accion[foco_filas].sum())}


def correr_foco(datos, nba, config, fecha, foco, sector_por_fila, region_filas, base, valor_cli_base, mejora_propuestas):
    """Corre las tres lecturas de «enfocar» para un conjunto de sectores. Devuelve un dict listo para JSON."""
    sectores = [r["indice"] for r in foco["sectores"]]
    foco_filas = np.isin(sector_por_fila, sectores)
    ref = medir(base["motor"], base["parrilla"], valor_cli_base, foco_filas, region_filas)
    mejora = mejora_propuestas / 100

    def con_propuestas(valor):
        return valor * (1 + mejora)
    salida = {"nombre": foco["nombre"], "sectores": [{k: r[k] for k in ("sector", "nombre", "clientes", "valor_por_cliente")} for r in foco["sectores"]],
              "clientes": int(foco_filas.sum()), "base": {**ref, "valor_foco_con_propuestas": con_propuestas(ref["valor_foco"])},
              "mejora_propuestas_pct": mejora_propuestas}

    # 1) cupo aislado: el cluster solo, con todo el cupo de canales
    sub = datos.iloc[np.flatnonzero(foco_filas)].reset_index(drop=True)
    motor = Engine(sub, nba, fecha)
    parrilla, _ = motor.optimize()
    v = valor_por_cliente(motor, parrilla)
    con_accion = int((parrilla["estado"] == "asignado").sum())
    salida["aislado"] = {"valor_foco": float(v.sum()), "clientes_con_accion": con_accion,
                         "delta_foco": float(v.sum() - ref["valor_foco"]),
                         "delta_foco_pct": float(100 * (v.sum() / ref["valor_foco"] - 1)) if ref["valor_foco"] else None,
                         "valor_foco_con_propuestas": con_propuestas(float(v.sum()))}

    # 2) mismo presupuesto, con prioridad: toda la población, la utilidad del foco pesa `peso` veces más
    salida["prioridad"] = []
    for peso in foco["pesos"]:
        inicio = time.perf_counter()
        motor_w = EngineFoco(datos, nba, fecha, np.where(foco_filas, peso, 1.0))
        parrilla_w, _ = motor_w.optimize()
        r = medir(motor_w, parrilla_w, valor_por_cliente(motor_w, parrilla_w), foco_filas, region_filas)
        salida["prioridad"].append({
            "peso": peso, **r, "delta_foco": r["valor_foco"] - ref["valor_foco"],
            "delta_foco_pct": float(100 * (r["valor_foco"] / ref["valor_foco"] - 1)) if ref["valor_foco"] else None,
            "delta_resto_region": r["valor_resto_region"] - ref["valor_resto_region"],
            "delta_total": r["valor_total"] - ref["valor_total"],
            "delta_total_pct": float(100 * (r["valor_total"] / ref["valor_total"] - 1)),
            "valor_foco_con_propuestas": con_propuestas(r["valor_foco"]),
            "segundos": round(time.perf_counter() - inicio, 1)})
        print(f"    prioridad x{peso}: foco {salida['prioridad'][-1]['delta_foco_pct']:+.1f} %, resto de Bogotá "
              f"{salida['prioridad'][-1]['delta_resto_region']:+.1f}, total {salida['prioridad'][-1]['delta_total']:+.2f}", flush=True)
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", type=Path, default=DATOS)
    ap.add_argument("--config", type=Path, default=AQUI / "config.json")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    perfiles = json.loads((AQUI.parent / "config" / "perfiles.json").read_text(encoding="utf-8-sig"))
    nba, fecha = load_config(), config["fecha"]
    datos = pd.read_csv(args.datos, keep_default_na=False)
    print("Foco: corriendo el motor NBA con toda la población (referencia)", flush=True)
    motor = Engine(datos, nba, fecha)
    parrilla, _ = motor.optimize()
    region = filtrar_region(datos, config["region"])
    idx = indices_region(datos, config["region"])
    tabla, sector_de, z = construir_sectores(region, config_perfil(config, perfiles), config["sectores"], config["semilla"])
    contactos = sim.contactos_de_parrilla(region, parrilla, nba, sector_de, len(tabla))
    ranking = ranking_sectores(viabilidad.celdas(motor, idx, sector_de, tabla, contactos), tabla, config["foco"]["criterio"])
    sector_por_fila = np.full(len(datos), -1)
    sector_por_fila[idx] = sector_de
    region_filas = sector_por_fila >= 0
    valor_base = valor_por_cliente(motor, parrilla)

    focos = [{**f, "sectores": ranking[:f["n"]],
              "nombre": f["nombre"]} for f in config["foco"]["focos"]]
    masks = {f["nombre"]: np.isin(contactos["sector"], [r["indice"] for r in f["sectores"]]) for f in focos}
    print("Foco: midiendo la mejora de las propuestas de mensaje en esos sectores (simulado)", flush=True)
    resumen_sim, _ = sim.evaluar(contactos, z, config, config["experimento"]["repeticiones"], subconjuntos=masks)
    resultados = []
    for f in focos:
        print(f"  {f['nombre']}: {sum(r['clientes'] for r in f['sectores']):,} clientes", flush=True)
        mejora = resumen_sim["subconjuntos"][f["nombre"]]["politicas"]["bandido_sector"]["mejora_pct_media"]
        r = correr_foco(datos, nba, config, fecha, f, sector_por_fila, region_filas, {"motor": motor, "parrilla": parrilla}, valor_base, mejora)
        r["mejora_propuestas_p5"] = resumen_sim["subconjuntos"][f["nombre"]]["politicas"]["bandido_sector"]["mejora_pct_p5"]
        r["mejora_propuestas_p95"] = resumen_sim["subconjuntos"][f["nombre"]]["politicas"]["bandido_sector"]["mejora_pct_p95"]
        resultados.append(r)
    args.salida.mkdir(parents=True, exist_ok=True)
    resumen = {"descripcion": "Foco en los clusters más probables: tres lecturas de «enfocar» el motor NBA (ver foco.py)",
               "advertencia": "El cupo aislado es un techo no alcanzable. La prioridad reasigna cupos: lo que sube en el foco baja en otros clientes. "
                              "La mejora de las propuestas es simulada (el CSV no trae respuestas reales).",
               "criterio": config["foco"]["criterio"], "region": config["region"], "fecha": fecha,
               "ranking": [{k: r[k] for k in ("sector", "nombre", "clientes", "valor_por_cliente")} for r in ranking],
               "focos": resultados}
    (args.salida / "foco.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Escrito en {args.salida / 'foco.json'}")


if __name__ == "__main__":
    main()

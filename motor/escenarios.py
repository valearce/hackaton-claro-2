"""Escenarios de cambio de negocio resueltos solo con configuracion."""
import sys, json; sys.path.insert(0, "motor")
import numpy as np, pandas as pd
from nba import Config, Orquestador
from validar import validar
cl = pd.read_csv("datos/clientes.csv")
out = []
def run(nombre, alg="optimo", overrides=None, mod=None, validar_=False, datos=cl):
    cfg = Config.cargar("config", overrides)
    if mod: mod(cfg)
    r = Orquestador(cfg, datos).correr(alg)
    m = dict(escenario=nombre, algoritmo=alg, **{k: v for k, v in r.metricas.items() if k != "uso_por_canal"},
             **{f"uso_{k}": v for k, v in r.metricas["uso_por_canal"].items()}, sombra=r.precios_sombra)
    if validar_: m["violaciones"] = validar(r.parrilla, datos, cfg)["total"]
    out.append(m); print(json.dumps(m, default=str), flush=True)

run("Linea base", "codicioso", validar_=True)
run("Optimo global", validar_=True)
# jerarquia: negocio pone OTT primero y decide cuanto valor sacrifica por respetarla
for b in [0, 0.02, 0.05, 0.1, 0.2]:
    run(f"Jerarquia OTT>TER>VCH, bono {b}", overrides={"priorizacion.jerarquia": "C-OTT|C-TER|C-VCH", "optimizacion.bono_jerarquia": b})
run("Cupo asesor 2.500 -> 5.000", overrides={"canal.capacidad_por_corrida.asesor": 5000})
run("Umbral score producto 0,35 -> 0,40", overrides={"priorizacion.umbral_score_producto": 0.40})
def regla_prepago(cfg):
    cfg.reglas.loc[len(cfg.reglas)] = ["R20", "Terminales no en prepago", "elegibilidad", "campana", "C-TER", "tipo_linea", "==", "Prepago", "excluir", "1"]
run("Regla nueva: sin terminales en prepago", mod=regla_prepago, validar_=False)
def pausar_ott(cfg): cfg.campanas.loc[cfg.campanas.id == "C-OTT", "activa"] = 0
run("Pausar campana OTT", mod=pausar_ott)
# canal nuevo: notificacion en la SuperApp Mi Claro (columna nueva en la base)
cl2 = cl.copy(); rng = np.random.default_rng(7)
cl2["score_canal_app"] = np.round(rng.beta(4, 5, len(cl2)) * cl2.compras_digitales.clip(0.6, 1), 4)
def canal_app(cfg):
    cfg.campanas["canales_permitidos"] = cfg.campanas.canales_permitidos + "|app"
run("Canal nuevo: SuperApp Mi Claro (cupo 10.000)", datos=cl2, mod=canal_app,
    overrides={"canal.capacidad_por_corrida.app": 10000, "politica_contacto.max_productos_por_canal.app": 2})
pd.DataFrame(out).to_csv("salidas/escenarios.csv", index=False)

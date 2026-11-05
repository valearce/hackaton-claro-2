"""Precalcula los escenarios que muestra la maqueta de la consola -> salidas/consola_datos.json"""
import sys, json, time; sys.path.insert(0, "motor")
import numpy as np, pandas as pd
from nba import Config, Orquestador
cl = pd.read_csv("datos/clientes.csv")
def corre(ov=None, mod=None, datos=cl, alg="optimo"):
    cfg = Config.cargar("config", ov)
    if mod: mod(cfg)
    o = Orquestador(cfg, datos); r = o.correr(alg)
    m = r.metricas
    return {"valor": m["valor_esperado"], "clientes": m["clientes_con_accion"], "productos": m["productos_asignados"],
            "jerarquia": float(m["indicador_jerarquia_pct"]), "uso": {k: int(v) for k, v in m["uso_por_canal"].items()},
            "sombra": r.precios_sombra}, r, o
t = time.time()
D = {}
D["base"], _, _ = corre(alg="codicioso")
D["optimo"], r_opt, o_opt = corre()
D["grid"] = [dict(asesor=a, whatsapp=w, **corre({"canal.capacidad_por_corrida.asesor": a, "canal.capacidad_por_corrida.whatsapp": w})[0])
             for a in [0, 1250, 2500, 3750, 5000, 7500] for w in [5000, 10000, 15000, 20000, 25000]]
D["umbral"] = [dict(umbral=u, **corre({"priorizacion.umbral_score_producto": u})[0]) for u in [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]]
D["jerarquia"] = {}
for nombre, orden in [("VCH > TER > OTT", "C-VCH|C-TER|C-OTT"), ("OTT > TER > VCH", "C-OTT|C-TER|C-VCH"), ("TER > VCH > OTT", "C-TER|C-VCH|C-OTT")]:
    D["jerarquia"][nombre] = [dict(bono=b, **corre({"priorizacion.jerarquia": orden, "optimizacion.bono_jerarquia": b})[0]) for b in [0, 0.02, 0.05, 0.1, 0.2, 0.4]]
def regla(*filas):
    def f(cfg):
        for fl in filas: cfg.reglas.loc[len(cfg.reglas)] = list(fl)
    return f
cl_app = cl.copy(); rng = np.random.default_rng(7)
cl_app["score_canal_app"] = np.round(rng.beta(4, 5, len(cl_app)) * cl_app.compras_digitales.clip(0.6, 1), 4)
def app(cfg): cfg.campanas["canales_permitidos"] = cfg.campanas.canales_permitidos + "|app"
def pausa(cfg): cfg.campanas.loc[cfg.campanas.id == "C-OTT", "activa"] = 0
ej = [
 ("No ofrecer terminales a clientes prepago", [["R20", "Terminales no en prepago", "elegibilidad", "campana", "C-TER", "tipo_linea", "==", "Prepago", "excluir", "1"]], {}, None),
 ("Hogar solo para estratos 3 o más", [["R21", "Hogar desde estrato 3", "elegibilidad", "campana", "C-VCH", "estrato", "<", "3", "excluir", "1"]], {}, None),
 ("No escribir por SMS a clientes de 70 años o más", [["R22", "Sin SMS a 70+", "canal", "canal", "sms", "edad", ">=", "70", "excluir", "1"]], {}, None),
 ("Terminales solo si el equipo es gama baja o media y el riesgo de churn es de 0,3 o más",
  [["R23", "Terminales: retencion", "elegibilidad", "campana", "C-TER", "gama_equipo", "en", "Baja|Media", "exigir", "1"],
   ["R23", "Terminales: retencion", "elegibilidad", "campana", "C-TER", "riesgo_churn", ">=", "0.3", "exigir", "1"]], {}, None),
 ("Pausar la campaña OTT", [], {}, "pausa"),
 ("Agregar el canal SuperApp Mi Claro con 10.000 cupos", [], {"canal.capacidad_por_corrida.app": 10000, "politica_contacto.max_productos_por_canal.app": 2}, "app"),
]
D["ejemplos"] = []
for texto, filas, ov, extra in ej:
    mod = regla(*filas) if filas else (pausa if extra == "pausa" else app)
    m = corre(ov, mod, datos=cl_app if extra == "app" else cl)[0]
    D["ejemplos"].append({"texto": texto, "filas": filas, "parametros": ov,
                          "accion": {"pausa": "config_campanas: C-OTT activa = 0", "app": "config_campanas: canales_permitidos += app; columna nueva score_canal_app"}.get(extra, ""), **m})
D["costo_reglas"] = pd.read_csv("salidas/costo_reglas.csv").to_dict("records")
# clientes de ejemplo para la explicacion
p = r_opt.parrilla; df = o_opt.df
def cli(i):
    f = p.iloc[i]; c = df.iloc[i]
    k = {ch: q for q, ch in enumerate(o_opt.canales)}
    vals = {ch: (None if not np.isfinite(o_opt._u[i, q]) else round(float(o_opt._v[i, q]), 3)) for ch, q in k.items()}
    return {"id": f.id_cliente, "estado": f.estado, "canal": f.canal, "c1": f.campana_1, "c2": f.campana_2, "razon": f.razon,
            "perfil": {"region": c.region, "estrato": int(c.estrato), "edad": int(c.edad), "linea": c.tipo_linea, "riesgo": c.calificacion_riesgo,
                       "hogar": int(c.tiene_hogar), "ott": int(c.cantidad_ott), "equipo_meses": int(c.edad_equipo_meses)},
            "scores": {"VCH": float(c.score_venta_cruzada_hogar), "TER": float(c.score_terminales), "OTT": float(c.score_upgrade_ott)},
            "valor_por_canal": vals}
idx = []
for ch in ["asesor", "whatsapp", "correo", "sms"]:
    cand = np.flatnonzero((p.canal == ch).values)
    idx.append(int(cand[len(cand) // 3]))
idx.append(int(np.flatnonzero(p.razon.str.startswith("Sin cupo").values)[0]))
idx.append(int(np.flatnonzero(p.razon.str.startswith("Sin campana").values)[5]))
D["clientes"] = [cli(i) for i in idx]
json.dump(D, open("salidas/consola_datos.json", "w"), ensure_ascii=False, default=float)
print("ok", round(time.time() - t, 1), "s", len(json.dumps(D, default=float)) // 1024, "KB")
print(json.dumps(D["ejemplos"], ensure_ascii=False, default=float)[:1500])

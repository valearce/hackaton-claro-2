"""Prueba de robustez: N configuraciones de negocio al azar (lo que negocio podria pedir
el dia de la hackaton) -> el motor debe dar 0 violaciones y el solver rapido debe
coincidir con la programacion lineal exacta."""
import sys, time, json
sys.path.insert(0, "motor")
import numpy as np, pandas as pd
from nba import Config, Orquestador
from validar_generico import validar_generico

N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
rng = np.random.default_rng(42)
base = pd.read_csv("datos/clientes.csv").sample(30_000, random_state=1).reset_index(drop=True)
cols_num = ["edad", "estrato", "antiguedad_meses", "arpu_movil", "riesgo_churn", "consumo_datos_pct", "dias_ultimo_contacto"]
cols_cat = {"region": ["Bogota", "Antioquia", "Valle", "Costa"], "tipo_linea": ["Prepago", "Postpago"], "gama_equipo": ["Baja", "Media", "Alta"]}
resultados = []
for it in range(N):
    ov = {
        "priorizacion.umbral_score_producto": round(rng.uniform(.2, .5), 2),
        "canal.umbral_score_canal": round(rng.uniform(.1, .4), 2),
        "politica_contacto.max_contactos_semana": int(rng.integers(1, 5)),
        "optimizacion.bono_jerarquia": float(rng.choice([0, 0, .05, .2])),
        "priorizacion.jerarquia": "|".join(rng.permutation(["C-VCH", "C-TER", "C-OTT"])),
    }
    for ch, lo, hi in [("asesor", 0, 6000), ("whatsapp", 1000, 20000), ("correo", 1000, 30000), ("sms", 1000, 30000)]:
        ov[f"canal.capacidad_por_corrida.{ch}"] = int(rng.integers(lo, hi))
        ov[f"politica_contacto.max_productos_por_canal.{ch}"] = int(rng.integers(1, 3))
    cfg = Config.cargar("config", ov)
    datos = base
    # campanas: pausar alguna, cambiar canales
    for idx in cfg.campanas.index:
        if rng.random() < .15:
            cfg.campanas.loc[idx, "activa"] = 0
        if rng.random() < .3:
            chs = [c for c in ["asesor", "whatsapp", "correo", "sms"] if rng.random() < .6] or ["sms"]
            cfg.campanas.loc[idx, "canales_permitidos"] = "|".join(chs)
    # reglas: apagar alguna y crear reglas nuevas (simples y compuestas) sobre columnas al azar
    for idx in cfg.reglas.index:
        if rng.random() < .15:
            cfg.reglas.loc[idx, "activa"] = "0"
    for k in range(int(rng.integers(1, 4))):
        rid = f"RX{k}"
        alc = rng.choice(["global", "campana", "grupo"])
        alc_v = {"global": "", "campana": rng.choice(["C-VCH", "C-TER", "C-OTT"]), "grupo": rng.choice(["VCH", "TER", "OTT", "Upgrade"])}[alc]
        accion = rng.choice(["excluir", "exigir"], p=[.8, .2])
        for _ in range(int(rng.integers(1, 3))):  # 1 o 2 condiciones -> regla compuesta con Y
            if rng.random() < .6:
                col = rng.choice(cols_num); op = rng.choice(["<", ">=", "entre"])
                q = np.quantile(base[col], [rng.uniform(.05, .4), rng.uniform(.6, .95)])
                val = f"{q[0]:.4g}|{q[1]:.4g}" if op == "entre" else f"{q[int(op == '>=')]:.4g}"
            else:
                col = rng.choice(list(cols_cat)); op = rng.choice(["en", "no_en", "=="])
                val = rng.choice(cols_cat[col]) if op == "==" else "|".join(rng.choice(cols_cat[col], 2, replace=False))
            cfg.reglas.loc[len(cfg.reglas)] = [rid, "regla al azar", "elegibilidad", alc, alc_v, col, op, val, accion, "1"]
    if rng.random() < .3:  # regla de canal nueva
        cfg.reglas.loc[len(cfg.reglas)] = ["RXC", "canal al azar", "canal", "canal", rng.choice(["whatsapp", "sms"]), "edad", ">=", "70", "excluir", "1"]
    t = time.time()
    r_dual = Orquestador(Config(dict(cfg.params, **{"optimizacion.solver": "dual"}), cfg.campanas, cfg.reglas), datos)
    res = r_dual.correr("optimo"); dt = time.time() - t
    r_lp = Orquestador(Config(dict(cfg.params, **{"optimizacion.solver": "lp"}), cfg.campanas, cfg.reglas), datos).correr("optimo")
    base_r = Orquestador(cfg, datos).correr("codicioso")
    v = validar_generico(res.parrilla, datos, cfg)
    fila = dict(caso=it, violaciones=v["total"], valor_dual=res.metricas["valor_esperado"], valor_lp=r_lp.metricas["valor_esperado"],
                valor_codicioso=base_r.metricas["valor_esperado"], solver=r_dual.diagnostico["solver"],
                brecha=r_dual.diagnostico["brecha_optimalidad"], segundos=round(dt, 2))
    resultados.append(fila); print(json.dumps(fila), flush=True)
df = pd.DataFrame(resultados); df.to_csv("salidas/prueba_robustez.csv", index=False)
print("violaciones totales:", df.violaciones.sum(), "| max dif dual vs LP:", (df.valor_dual - df.valor_lp).abs().max(),
      "| mejora media vs codicioso: %.1f%%" % (100 * (df.valor_dual / df.valor_codicioso - 1).mean()))

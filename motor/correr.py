import sys, time, json; sys.path.insert(0, "motor")
import pandas as pd
from nba import Config, Orquestador
from validar import validar
cl = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "datos/clientes.csv")
cfg = Config.cargar("config")
t = time.time(); o = Orquestador(cfg, cl); print(f"preparar {time.time()-t:.1f}s")
for alg in ["codicioso", "optimo"]:
    t = time.time(); r = o.correr(alg); dt = time.time() - t
    r.parrilla.to_csv(f"salidas/parrilla_{alg}.csv", index=False)
    t = time.time(); v = validar(r.parrilla, cl, cfg); dv = time.time() - t
    print(alg, f"{dt:.1f}s", json.dumps(r.metricas), "sombra", r.precios_sombra, "violaciones", v["total"], f"(valid {dv:.0f}s)")

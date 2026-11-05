import sys; sys.path.insert(0, "motor")
import pandas as pd
from nba import Config, Orquestador
cfg = Config.cargar("config")
cl = pd.read_csv("config/casos_ejemplo_clientes.csv")
esp = pd.read_csv("config/casos_ejemplo_parrilla_esperada.csv").fillna("")
r = Orquestador(cfg, cl).correr("codicioso").parrilla
cmp = r.merge(esp, on="id_cliente", suffixes=("", "_esp"))
ok = True
for c in ["estado", "canal", "campana_1", "campana_2", "razon"]:
    bad = cmp[cmp[c] != cmp[c + "_esp"]]
    if len(bad): ok = False; print(c, "\n", bad[["id_cliente", c, c + "_esp"]].to_string())
print("CASOS OK" if ok else "DIFERENCIAS")

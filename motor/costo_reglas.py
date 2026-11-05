"""Radar de eficiencia: cuanto valor cuesta cada regla, umbral y cupo (apagandolo uno a la vez).
No es para violar reglas: es para que negocio sepa que le cuesta cada decision."""
import sys, json; sys.path.insert(0, "motor")
import pandas as pd
from nba import Config, Orquestador
cl = pd.read_csv("datos/clientes.csv")
def valor(ov=None, mod=None):
    cfg = Config.cargar("config", ov)
    if mod: mod(cfg)
    return Orquestador(cfg, cl).correr("optimo").metricas["valor_esperado"]
v0 = valor(); out = []
cfg0 = Config.cargar("config")
for _, r in cfg0.reglas.iterrows():
    def apagar(cfg, rid=r.id): cfg.reglas.loc[cfg.reglas.id == rid, "activa"] = "0"
    out.append(("regla", f"{r.id} {r['nombre']}", valor(mod=apagar) - v0))
out.append(("umbral", "Score minimo de producto 0,35 -> 0", valor({"priorizacion.umbral_score_producto": 0}) - v0))
out.append(("umbral", "Score minimo de canal 0,25 -> 0", valor({"canal.umbral_score_canal": 0}) - v0))
out.append(("politica", "Tope semanal 3 -> sin tope", valor({"politica_contacto.max_contactos_semana": 99}) - v0))
out.append(("politica", "Asesor 1 -> 2 productos", valor({"politica_contacto.max_productos_por_canal.asesor": 2}) - v0))
for ch in cfg0.canales:
    c = cfg0.cupo(ch)
    out.append(("cupo", f"Cupo {ch} +10% ({c} -> {int(c*1.1)})", valor({f"canal.capacidad_por_corrida.{ch}": int(c * 1.1)}) - v0))
df = pd.DataFrame(out, columns=["tipo", "palanca", "valor_ganado"]).sort_values("valor_ganado", ascending=False)
df["pct"] = (100 * df.valor_ganado / v0).round(2)
df.to_csv("salidas/costo_reglas.csv", index=False); print("base", v0); print(df.to_string(index=False))

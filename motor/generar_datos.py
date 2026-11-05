"""Genera 100.000 clientes sinteticos con el mismo esquema de casos_ejemplo_clientes.csv.

El kit del reto no trae clientes.csv; esto es un sustituto para prototipar.
Cuando llegue la base real, basta con apuntar el motor a ese archivo.
"""
import sys
import numpy as np
import pandas as pd

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
SALIDA = sys.argv[2] if len(sys.argv) > 2 else "datos/clientes.csv"
rng = np.random.default_rng(2026)


def beta(a, b, n=N):
    return rng.beta(a, b, n)


regiones = ["Bogota", "Antioquia", "Valle", "Costa", "Centro", "Santanderes", "Eje Cafetero", "Sur"]
df = pd.DataFrame({
    "id_cliente": [f"CL{i:06d}" for i in range(1, N + 1)],
    "region": rng.choice(regiones, N, p=[.25, .16, .13, .14, .1, .08, .07, .07]),
    "estrato": rng.choice([1, 2, 3, 4, 5, 6], N, p=[.12, .3, .3, .15, .08, .05]),
    "edad": rng.integers(18, 80, N),
    "antiguedad_meses": rng.integers(1, 180, N),
    "tipo_linea": rng.choice(["Postpago", "Prepago"], N, p=[.55, .45]),
})
df["plan_datos_gb"] = rng.choice([5, 10, 20, 40, 999], N, p=[.25, .25, .2, .15, .15])
df["consumo_datos_pct"] = np.round(rng.uniform(5, 100, N), 1)
df["arpu_movil"] = (rng.lognormal(10.4, 0.5, N) // 100 * 100).astype(int)
df["calificacion_riesgo"] = rng.choice(list("EABCP"), N, p=[.2, .3, .25, .15, .1])
df["en_mora"] = (rng.random(N) < np.where(df.calificacion_riesgo.isin(["C", "P"]), .25, .04)).astype(int)
df["dias_mora"] = np.where(df.en_mora == 1, rng.integers(1, 90, N), 0)
df["tiene_hogar"] = (rng.random(N) < .38).astype(int)
df["arpu_hogar"] = np.where(df.tiene_hogar == 1, (rng.lognormal(11.8, .3, N) // 100 * 100).astype(int), 0)
for ott, p in [("netflix", .35), ("amazon_prime", .22), ("win", .12)]:
    df[f"tiene_{ott}"] = (rng.random(N) < p).astype(int)
df["cantidad_ott"] = df.tiene_netflix + df.tiene_amazon_prime + df.tiene_win
df["usa_redes_sociales"] = (rng.random(N) < .8).astype(int)
df["usa_banca_digital"] = (rng.random(N) < .55).astype(int)
df["compras_digitales"] = (rng.random(N) < .45).astype(int)
df["edad_equipo_meses"] = rng.integers(1, 60, N)
df["gama_equipo"] = rng.choice(["Baja", "Media", "Alta"], N, p=[.35, .45, .2])
df["quejas_90d"] = rng.choice([0, 1, 2, 3, 4], N, p=[.7, .15, .08, .05, .02])
df["riesgo_churn"] = np.round(beta(2, 8), 4)
df["tiene_correo"] = (rng.random(N) < .85).astype(int)
df["autoriza_sms"] = (rng.random(N) < .85).astype(int)
df["autoriza_correo"] = ((rng.random(N) < .8) & (df.tiene_correo == 1)).astype(int)
df["autoriza_whatsapp"] = (rng.random(N) < .7).astype(int)

# historial de contactos del mes
for c, lam in [("asesor", .25), ("sms", .6), ("correo", .6), ("whatsapp", .4)]:
    df[f"contactos_{c}_mes"] = rng.poisson(lam, N)
df["contactos_mes"] = df[[f"contactos_{c}_mes" for c in ["asesor", "sms", "correo", "whatsapp"]]].sum(axis=1)
df["contactos_semana_actual"] = np.minimum(df.contactos_mes, rng.binomial(df.contactos_mes, .4))
df["canales_contactados_mes"] = [
    "|".join(c for c in ["asesor", "correo", "sms", "whatsapp"] if r[f"contactos_{c}_mes"] > 0)
    for _, r in df[[f"contactos_{c}_mes" for c in ["asesor", "correo", "sms", "whatsapp"]]].iterrows()
]
prods = np.array(["OTT", "TER", "VCH"])
mask = rng.random((N, 3)) < np.where(df.contactos_mes.values[:, None] > 0, .3, 0)
df["productos_ofertados_mes"] = ["|".join(prods[m]) for m in mask]
df["dias_ultimo_contacto"] = np.where(df.contactos_mes > 0, rng.integers(1, 30, N), rng.integers(31, 180, N))

# scores precalculados (sinteticos, con algo de logica de negocio)
df["score_terminales"] = np.round(np.clip(beta(4, 6) + (df.edad_equipo_meses - 30) / 300, 0, 1), 4)
df["score_venta_cruzada_hogar"] = np.round(np.clip(beta(3, 6) + (df.estrato - 3) * .02, 0, 1), 4)
df["score_upgrade_ott"] = np.round(np.clip(beta(5, 5) + df.usa_redes_sociales * .03, 0, 1), 4)
df["score_canal_asesor"] = np.round(beta(4, 6), 4)
df["score_canal_sms"] = np.round(beta(3, 6), 4)
df["score_canal_correo"] = np.round(np.clip(beta(3, 5) + df.usa_banca_digital * .03, 0, 1), 4)
df["score_canal_whatsapp"] = np.round(np.clip(beta(4, 5) + df.usa_redes_sociales * .04, 0, 1), 4)

cols = pd.read_csv("config/casos_ejemplo_clientes.csv", nrows=0).columns
assert set(cols) == set(df.columns), set(cols) ^ set(df.columns)
df = df[cols]
df.to_csv(SALIDA, index=False)
print(f"{len(df)} clientes -> {SALIDA} ({df.shape[1]} columnas)")

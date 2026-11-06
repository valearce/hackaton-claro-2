"""Simulador de oleadas de contacto para medir el rendimiento de repartir propuestas por sector.

El CSV del reto no trae compras ni respuestas, así que el efecto real de cada propuesta no se puede
medir con estos datos. El simulador crea un mundo oculto con supuestos declarados en `config.json`
(`verdad_simulada`): cada propuesta multiplica el score del reto por un `lift` que depende de la afinidad
entre su enfoque y los rasgos del sector. Las políticas no ven ese mundo: solo ven las compras simuladas
y deben descubrirlo. Todas las políticas se evalúan con las mismas oleadas y los mismos números aleatorios.

Lo que valida: que el mecanismo aprende y cuánto gana frente a un A/B clásico si los supuestos son ciertos.
Lo que NO valida: que esos efectos existan en clientes reales; eso lo tiene que decir una prueba real."""
import numpy as np
from scipy.stats import gamma

from . import bandido as B
from .sectores import RASGOS

POLITICAS = ("uniforme", "ganador_global", "bandido_global", "bandido_sector", "oraculo")


def contactos_de_parrilla(datos, parrilla, config_nba, sector_de_cliente, n_sectores):
    """Un contacto por (cliente, campaña asignada) de la parrilla NBA, con su probabilidad base del reto."""
    ids = [c["id"] for c in config_nba["campanas"]]
    canales = list(config_nba["parametros"]["canal"]["capacidad_por_corrida"])
    col_canal = config_nba["parametros"]["canal"]["columnas_score"]
    valor = np.array([c["valor_negocio"] for c in config_nba["campanas"]])
    g = parrilla.set_index("id_cliente").reindex(datos["id_cliente"].astype(str))
    asignado = g["estado"].to_numpy() == "asignado"
    filas, campana, canal = [], [], []
    for col in ("campana_1", "campana_2"):
        idx = np.flatnonzero(asignado & (g[col].fillna("").to_numpy() != ""))
        filas.append(idx)
        campana.append(np.array([ids.index(x) for x in g[col].to_numpy()[idx]], dtype=int))
        canal.append(np.array([canales.index(x) for x in g["canal"].to_numpy()[idx]], dtype=int))
    fila, camp, can = np.concatenate(filas), np.concatenate(campana), np.concatenate(canal)
    sp = np.column_stack([datos[c["columna_score"]].astype(float).to_numpy() for c in config_nba["campanas"]])
    sc = np.column_stack([datos[col_canal[c]].astype(float).to_numpy() for c in canales])
    return {"fila": fila, "sector": np.asarray(sector_de_cliente)[fila], "campana": camp, "canal": can,
            "p0": sp[fila, camp] * sc[fila, can], "vn": valor[camp],
            "n_sectores": n_sectores, "n_campanas": len(ids), "campanas": ids, "canales": canales}


def matriz_afinidad(config):
    """K x rasgos, filas normalizadas: la dirección en que cada propuesta rinde mejor."""
    w = np.array([[v["afinidad"].get(r, 0.0) for r in RASGOS] for v in config["variantes"].values()], dtype=float)
    return w / np.linalg.norm(w, axis=1, keepdims=True)


def lift_verdad(z, config, n_campanas, rng, escenario=None):
    """Mundo oculto: lift[sector, campaña, variante]. `escenario` sobrescribe amplitud y ruido de sector."""
    v = {**config["verdad_simulada"], **(escenario or {})}
    w = matriz_afinidad(config)
    k, s = w.shape[0], z.shape[0]
    efecto_sector = v["amplitud_sector"] * (z @ w.T)
    efecto_campana = rng.normal(0, v["ruido_campana_variante"], (n_campanas, k))
    ruido = rng.normal(0, v["ruido_sector"], (s, n_campanas, k))
    return np.exp(efecto_sector[:, None, :] + efecto_campana[None] + ruido)


def _fabricas(contactos, lift, config, k):
    exp = config["experimento"]
    return {
        "uniforme": lambda: B.Uniforme(contactos, k),
        "ganador_global": lambda: B.GanadorGlobal(contactos, k, exp, exp["oleadas"]),
        "bandido_global": lambda: B.BandidoGlobal(contactos, k, exp),
        "bandido_sector": lambda: B.BandidoSector(contactos, k, exp),
        "oraculo": lambda: B.Oraculo(contactos, lift),
    }


def simular(contactos, lift, config, semilla):
    """Corre todas las políticas sobre las mismas oleadas. Devuelve resultados y las políticas ya entrenadas."""
    exp = config["experimento"]
    n, k = len(contactos["p0"]), lift.shape[2]
    rng = np.random.default_rng(semilla)
    lotes = np.array_split(rng.permutation(n), exp["oleadas"])
    u = rng.random((n, k))
    s, c, p0, vn = contactos["sector"], contactos["campana"], contactos["p0"], contactos["vn"]
    resultados, politicas = {}, {}
    for i, (nombre, fabrica) in enumerate(_fabricas(contactos, lift, config, k).items()):
        pol, rp = fabrica(), np.random.default_rng([semilla, i])
        elegida = np.empty(n, dtype=int)
        for lote in lotes:
            v = pol.elegir(lote, rp)
            elegida[lote] = v
            p = np.minimum(p0[lote] * lift[s[lote], c[lote], v], 0.99)
            pol.aprender(lote, v, u[lote, v] < p)
        p = np.minimum(p0 * lift[s, c, elegida], 0.99)
        resultados[nombre] = {"valor": float((p * vn).sum()), "conversiones": float(p.sum()),
                              "curva": np.array([(p[l] * vn[l]).sum() for l in lotes]), "valor_contacto": p * vn}
        politicas[nombre] = pol
    return resultados, politicas


def identificacion(contactos, lift, politica):
    """Porcentaje de contactos cuyo sector x campaña tiene bien identificada la mejor propuesta."""
    n_c = contactos["n_campanas"]
    estimada = politica.lift_posterior().argmax(axis=1).reshape(contactos["n_sectores"], n_c)
    real = lift.argmax(axis=2)
    expuestos = np.bincount(contactos["sector"] * n_c + contactos["campana"], minlength=estimada.size).reshape(estimada.shape)
    return float(100 * (expuestos * (estimada == real)).sum() / expuestos.sum())


def evaluar(contactos, z, config, repeticiones, escenario=None, semilla=None, subconjuntos=None):
    """Repite el experimento con mundos ocultos distintos y resume el rendimiento de cada política.

    `subconjuntos` ({nombre: máscara de contactos}) mide además la mejora dentro de esos contactos (p. ej. los de
    los sectores en foco); el aprendizaje sigue usando todos los contactos de la región."""
    semilla = config["semilla"] if semilla is None else semilla
    sub_valores = {n: {p: [] for p in POLITICAS} for n in (subconjuntos or {})}
    valores = {p: [] for p in POLITICAS}
    por_oleada = {p: [] for p in POLITICAS}
    acumulada = {p: [] for p in POLITICAS}
    acierto = []
    primera = None
    for r in range(repeticiones):
        lift = lift_verdad(z, config, contactos["n_campanas"], np.random.default_rng([semilla, 999, r]), escenario)
        res, pols = simular(contactos, lift, config, semilla * 1000 + r)
        uni_ola = res["uniforme"]["curva"]
        for p in POLITICAS:
            valores[p].append(res[p]["valor"])
            por_oleada[p].append(100 * (res[p]["curva"] / uni_ola - 1))
            acumulada[p].append(100 * (np.cumsum(res[p]["curva"]) / np.cumsum(uni_ola) - 1))
            for nombre, mascara in (subconjuntos or {}).items():
                sub_valores[nombre][p].append(float(res[p]["valor_contacto"][mascara].sum()))
        acierto.append(identificacion(contactos, lift, pols["bandido_sector"]))
        if r == 0:
            primera = {"lift": lift, "politicas": pols, "resultados": res}
    uni = np.array(valores["uniforme"])
    ora = np.array(valores["oraculo"])
    resumen = {"repeticiones": repeticiones, "politicas": {}, "identificacion_pct": float(np.mean(acierto)),
               "curva_por_oleada_pct": {}, "curva_acumulada_pct": {}}
    posible = np.where(ora - uni > 1e-9, ora - uni, np.nan)
    for p in POLITICAS:
        v = np.array(valores[p])
        mejora = 100 * (v / uni - 1)
        resumen["politicas"][p] = {
            "valor_medio": float(v.mean()), "mejora_pct_media": float(mejora.mean()),
            "mejora_pct_p5": float(np.percentile(mejora, 5)), "mejora_pct_p95": float(np.percentile(mejora, 95)),
            "captura_pct": float(np.nanmean(100 * (v - uni) / posible)) if np.isfinite(posible).any() else None}
        resumen["curva_por_oleada_pct"][p] = np.mean(por_oleada[p], axis=0).tolist()
        resumen["curva_acumulada_pct"][p] = np.mean(acumulada[p], axis=0).tolist()
    if subconjuntos:
        resumen["subconjuntos"] = {}
        for nombre, mascara in subconjuntos.items():
            base_sub = np.array(sub_valores[nombre]["uniforme"])
            resumen["subconjuntos"][nombre] = {"contactos": int(mascara.sum()), "politicas": {
                p: {"mejora_pct_media": float(np.mean(100 * (np.array(sub_valores[nombre][p]) / base_sub - 1))),
                    "mejora_pct_p5": float(np.percentile(100 * (np.array(sub_valores[nombre][p]) / base_sub - 1), 5)),
                    "mejora_pct_p95": float(np.percentile(100 * (np.array(sub_valores[nombre][p]) / base_sub - 1), 95))}
                for p in POLITICAS}}
    return resumen, primera


def recomendaciones(contactos, tabla_sectores, config, primera, campanas_nba, muestras=4000, semilla=0):
    """Reparto de propuestas por sector x campaña tras el aprendizaje, con texto adaptado."""
    from .propuestas import nombres_variantes, redactar
    pol = primera["politicas"]["bandido_sector"]
    verdad = primera["lift"]
    forma, tasa = pol.posterior()
    p = B.prob_mejor(forma, tasa, muestras, np.random.default_rng(semilla))
    lift = forma / tasa
    n_c, claves = contactos["n_campanas"], list(config["variantes"])
    nombres = nombres_variantes(config)
    celda = contactos["sector"] * n_c + contactos["campana"]
    expuestos = np.bincount(celda, minlength=p.shape[0])
    suma_p0 = np.bincount(celda, weights=contactos["p0"], minlength=p.shape[0])
    campanas = {c["id"]: c for c in campanas_nba}
    salida = []
    for s, fila in tabla_sectores.reset_index(drop=True).iterrows():
        zs = {r: float(fila[f"z_{r}"]) for r in RASGOS}
        for j, cid in enumerate(contactos["campanas"]):
            i = s * n_c + j
            if expuestos[i] == 0:
                continue
            orden = np.argsort(-p[i])
            mejor = int(orden[0])
            en_celda = celda == i
            canal = contactos["canales"][int(np.bincount(contactos["canal"][en_celda]).argmax())]
            tasa_base = suma_p0[i] / expuestos[i]
            bajo, alto = gamma.ppf([0.05, 0.95], a=forma[i, mejor], scale=1 / tasa[i, mejor])
            salida.append({
                "lift_ic90_pct": [float(100 * (bajo - 1)), float(100 * (alto - 1))],
                "sector": fila["sector"], "nombre": fila["nombre"], "estrato": int(fila["estrato"]),
                "clientes": int(fila["clientes"]), "campana": cid, "contactos": int(expuestos[i]), "canal_tipico": canal,
                "recomendada": claves[mejor], "recomendada_nombre": nombres[claves[mejor]],
                "p_mejor": float(p[i, mejor]), "lift_estimado_pct": float(100 * (lift[i, mejor] - 1)),
                "tasa_esperada_pct": float(100 * tasa_base * lift[i, mejor]),
                "texto": redactar(config, campanas[cid], claves[mejor], zs, canal),
                "alternativas": [{"variante": claves[int(k)], "nombre": nombres[claves[int(k)]], "p_mejor": float(p[i, k])}
                                 for k in orden[1:]],
                "mejor_real_simulada": claves[int(verdad[s, j].argmax())],
                "acierto": claves[int(verdad[s, j].argmax())] == claves[mejor]})
    return salida

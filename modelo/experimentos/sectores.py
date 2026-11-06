"""Sectores = estrato (lo que conoce el mapa de Bogotá) x perfil de consumo (segmentación del modelo).

Los clientes del reto no tienen coordenadas ni manzana: el mapa solo permite agrupar por estrato. Por eso
un sector es una celda estrato x perfil, no un polígono. El perfil usa las mismas variables que
`modelo/config/perfiles.json`; aquí la segmentación es descriptiva (PCA + KMeans sobre todos los clientes
de la región), no un modelo entrenado con validación."""
import unicodedata

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

RASGOS = ["postpago", "hogar", "gama_alta", "gama_media", "arpu", "ott", "antiguedad", "estrato", "consumo", "edad", "digital",
          "banca", "compras", "redes", "netflix", "amazon", "win", "ilimitado"]
ETIQUETAS = {
    "banca+": "usa banca digital", "banca-": "no usa banca digital",
    "compras+": "compra en línea", "compras-": "no compra en línea",
    "redes+": "activo en redes", "redes-": "poco activo en redes",
    "netflix+": "con Netflix", "netflix-": "sin Netflix", "amazon+": "con Amazon Prime", "amazon-": "sin Amazon Prime",
    "win+": "con Win", "win-": "sin Win", "ilimitado+": "plan de datos ilimitado", "ilimitado-": "plan de datos limitado",
    "postpago+": "postpago", "postpago-": "prepago",
    "hogar+": "con Hogar", "hogar-": "sin Hogar",
    "gama_alta+": "equipo de gama alta", "gama_alta-": "equipo de gama baja o media",
    "gama_media+": "equipo de gama media", "gama_media-": "equipo de gama alta o baja",
    "arpu+": "gasto móvil alto", "arpu-": "gasto móvil bajo",
    "ott+": "con streaming", "ott-": "sin streaming",
    "antiguedad+": "clientes antiguos", "antiguedad-": "clientes recientes",
    "consumo+": "alto consumo de datos", "consumo-": "bajo consumo de datos",
    "edad+": "mayores", "edad-": "jóvenes",
    "digital+": "muy digitales", "digital-": "poco digitales",
}
UMBRAL_EFECTO = 0.4  # diferencia mínima (en desviaciones de la población) para describir un rasgo


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(c)).strip().casefold()


def filtrar_region(datos, region):
    """Clientes de una región (sin distinguir tildes ni mayúsculas); `None` deja todos."""
    if region is None:
        return datos.reset_index(drop=True)
    objetivo = _sin_tildes(region)
    return datos[datos["region"].map(_sin_tildes) == objetivo].reset_index(drop=True)


def indices_region(datos, region):
    """Posiciones (0..n-1) en `datos` de los clientes de la región, en el mismo orden que `filtrar_region`."""
    if region is None:
        return np.arange(len(datos))
    objetivo = _sin_tildes(region)
    return np.flatnonzero((datos["region"].map(_sin_tildes) == objetivo).to_numpy())


def rasgos_cliente(datos):
    """Rasgos interpretables por cliente: es lo que usan las propuestas para adaptar el texto."""
    digital = datos[["usa_redes_sociales", "usa_banca_digital", "compras_digitales"]].astype(float).mean(axis=1)
    return pd.DataFrame({
        "postpago": datos["tipo_linea"].eq("Postpago").astype(float),
        "hogar": datos["tiene_hogar"].astype(float),
        "gama_alta": datos["gama_equipo"].eq("Alta").astype(float),
        "gama_media": datos["gama_equipo"].eq("Media").astype(float),
        "arpu": np.log1p(datos["arpu_movil"].astype(float)),
        "ott": datos["cantidad_ott"].astype(float),
        "antiguedad": datos["antiguedad_meses"].astype(float),
        "estrato": datos["estrato"].astype(float),
        "consumo": datos["consumo_datos_pct"].astype(float),
        "edad": datos["edad"].astype(float),
        "digital": digital,
        "banca": datos["usa_banca_digital"].astype(float),
        "compras": datos["compras_digitales"].astype(float),
        "redes": datos["usa_redes_sociales"].astype(float),
        "netflix": datos["tiene_netflix"].astype(float),
        "amazon": datos["tiene_amazon_prime"].astype(float),
        "win": datos["tiene_win"].astype(float),
        "ilimitado": datos["plan_datos_gb"].astype(float).eq(999).astype(float),
    })[RASGOS]


def config_perfil(config, perfiles):
    """Variables con las que se agrupa a los clientes: `comportamiento` (consumo de datos, streaming, uso digital y
    Hogar; sin tipo de línea, ARPU ni gama) o `contrato` (las de config/perfiles.json). Se elige en config.json."""
    s = config["sectores"]
    if s.get("perfil", "contrato") == "comportamiento":
        return {**s["variables_comportamiento"], "plan_ilimitado": perfiles["plan_ilimitado"]}
    return perfiles


def matriz_perfil(datos, config):
    """Misma codificación que `Preprocessor` del modelo, aprendida sobre estos clientes."""
    columnas = config["numericas"] + config["binarias"]
    crudo = datos[columnas].apply(pd.to_numeric, errors="coerce").astype(float)
    ilimitado = config["plan_ilimitado"]
    mascara = crudo[ilimitado["columna"]].eq(ilimitado["valor"])
    crudo["plan_ilimitado"] = mascara.astype(float)
    crudo.loc[mascara, ilimitado["columna"]] = np.nan
    for columna in config["log1p"]:
        crudo[columna] = np.log1p(crudo[columna])
    crudo = crudo.fillna(crudo.median())
    categorias = [pd.get_dummies(datos[c].astype(str), prefix=c).astype(float) for c in config["categoricas"]]
    x = pd.concat([crudo, *categorias], axis=1)
    desviacion = x.std().replace(0, 1)
    return ((x - x.mean()) / desviacion).to_numpy(np.float32)


def segmentar(datos, config_perfil, k, componentes, semilla):
    """Etiqueta de perfil por cliente (0 = el más numeroso). Determinista con la semilla."""
    matriz = matriz_perfil(datos, config_perfil)
    latentes = PCA(n_components=componentes, random_state=semilla).fit_transform(matriz)
    etiquetas = KMeans(n_clusters=k, n_init=10, random_state=semilla).fit_predict(latentes)
    orden = pd.Series(etiquetas).value_counts().index.tolist()
    reasignar = {viejo: nuevo for nuevo, viejo in enumerate(orden)}
    return np.array([reasignar[e] for e in etiquetas])


def efecto(rasgos, grupos):
    """Tamaño de efecto de cada grupo: (media del grupo - media de la población) / desviación de la población.
    Un valor de 0,4 es una diferencia visible; 0,05 es ruido (por eso no se estandariza entre grupos)."""
    desviacion = rasgos.std(ddof=0).replace(0, 1)
    return (rasgos.groupby(grupos).mean() - rasgos.mean()) / desviacion


def describir(fila, maximo=3, excluir=()):
    """Frase con los rasgos que más distinguen a un grupo (solo los que superan el umbral)."""
    fuertes = fila.drop(list(excluir)).loc[lambda s: s.abs() >= UMBRAL_EFECTO].sort_values(key=abs, ascending=False).head(maximo)
    frases = [ETIQUETAS[f"{rasgo}{'+' if valor > 0 else '-'}"] for rasgo, valor in fuertes.items()]
    texto = " · ".join(frases)
    return texto[0].upper() + texto[1:] if texto else "Perfil promedio"


def nombrar_perfiles(rasgos, perfiles):
    """Nombre corto de cada perfil a partir de los rasgos que de verdad lo distinguen."""
    z = efecto(rasgos, perfiles)
    return {perfil: describir(fila, excluir=("estrato",)) for perfil, fila in z.iterrows()}


def construir_sectores(datos, config_perfil, config_sectores, semilla):
    """Devuelve (tabla de sectores, índice de sector por cliente, z de rasgos por sector)."""
    rasgos = rasgos_cliente(datos)
    perfiles = segmentar(datos, config_perfil, config_sectores["k_perfiles"], config_sectores["componentes_pca"], semilla)
    nombres = nombrar_perfiles(rasgos, perfiles)
    estrato = datos["estrato"].astype(int).to_numpy()
    clave = pd.Series([f"E{e}-P{p + 1}" for e, p in zip(estrato, perfiles)])
    minimo = config_sectores["min_clientes"]
    tamano = clave.map(clave.value_counts())
    # las celdas pequeñas se funden con el resto de su estrato: un sector sin datos no se puede evaluar
    clave = clave.where(tamano >= minimo, pd.Series([f"E{e}-otros" for e in estrato]))
    perfil_de = pd.Series(perfiles)
    filas = []
    for sector in sorted(clave.unique(), key=lambda s: (int(s[1]), s[3:] != "otros", s)):
        miembros = (clave == sector).to_numpy()
        e = int(sector[1])
        if sector.endswith("otros"):
            perfil, etiqueta = "otros", "Otros perfiles"
        else:
            perfil = sector.split("-")[1]
            etiqueta = nombres[int(perfil[1:]) - 1]
        medias = rasgos[miembros].mean()
        filas.append({"sector": sector, "estrato": e, "perfil": perfil, "etiqueta": etiqueta,
                      "nombre": f"Estrato {e} · {etiqueta}", "clientes": int(miembros.sum()),
                      **{f"rasgo_{r}": float(medias[r]) for r in RASGOS}})
    tabla = pd.DataFrame(filas)
    indice = {s: i for i, s in enumerate(tabla["sector"])}
    por_cliente = clave.map(indice).to_numpy(int)
    z = efecto(rasgos, por_cliente)  # una fila por sector, en el orden de la tabla
    for r in RASGOS:
        tabla[f"z_{r}"] = z[r].to_numpy()
    return tabla, por_cliente, z.to_numpy()

"""Consola del Orquestador NBA (Streamlit).

Correr:  streamlit run app.py
Negocio edita campanas, reglas y parametros como tablas, o pide un cambio en espanol
(copiloto con modelo de lenguaje si hay ANTHROPIC_API_KEY). Todo cambio se simula
contra la version publicada antes de publicarse, y queda versionado en config/versiones/.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ / "motor"))
from frases import frase, frase_sin_accion  # noqa: E402
from nba import OPERADORES, Config, Orquestador  # noqa: E402
from validar_generico import validar_generico  # noqa: E402

st.set_page_config(page_title="Consola Orquestador NBA", layout="wide")
NOMBRE = {"asesor": "Asesor", "whatsapp": "WhatsApp", "correo": "Correo", "sms": "SMS"}


# ----------------------------------------------------------------------------- estado
@st.cache_data(show_spinner="Cargando base de clientes...")
def cargar_clientes(ruta: str) -> pd.DataFrame:
    return pd.read_csv(ruta)


def cfg_desde(estado) -> Config:
    p = {r.parametro: r.valor for r in estado["params"].itertuples()}
    from nba import _num
    return Config({k: _num(v) for k, v in p.items()}, estado["campanas"].copy(), estado["reglas"].copy().fillna("").astype(str))


def estado_inicial():
    c = Config.cargar(str(RAIZ / "config"))
    params = pd.DataFrame({"parametro": list(c.params), "valor": [str(v) for v in c.params.values()]})
    for k, v in {"optimizacion.algoritmo": "optimo", "optimizacion.bono_jerarquia": "0", "optimizacion.solver": "dual"}.items():
        if k not in params.parametro.values:
            params.loc[len(params)] = [k, v]
    return {"params": params, "campanas": c.campanas.copy(), "reglas": c.reglas.copy()}


if "publicada" not in st.session_state:
    st.session_state.publicada = estado_inicial()
    st.session_state.borrador = {k: v.copy() for k, v in st.session_state.publicada.items()}
    st.session_state.version = 1
    st.session_state.historial = [(1, "Configuración inicial del reto")]


def correr(estado, clientes, algoritmo=None):
    cfg = cfg_desde(estado)
    t = time.time()
    o = Orquestador(cfg, clientes)
    r = o.correr(algoritmo)
    return o, r, time.time() - t, cfg


# ----------------------------------------------------------------------------- copiloto
ESQUEMA = """Devuelve SOLO un JSON con esta forma:
{"filas": [{"id": "R2x", "nombre": "...", "tipo": "elegibilidad|canal", "alcance_nivel": "global|campana|grupo|canal",
  "alcance_valores": "C-TER o whatsapp|sms ...", "atributo": "<columna>", "operador": "== != < <= > >= en no_en contiene no_contiene entre",
  "valor": "...", "accion": "excluir|exigir", "activa": "1"}],
 "parametros": {"<parametro>": "<valor>"}, "campanas": {"<id campana>": {"activa": 0}}, "explicacion": "una frase"}
Reglas: 'excluir' saca al cliente cuando la condicion se cumple; 'exigir' lo saca cuando NO se cumple.
Varias filas con el mismo id se combinan con Y. Listas con '|'. Usa solo columnas que existan."""


def copiloto(pedido, clientes, estado):
    from anthropic import Anthropic
    contexto = {
        "columnas": {c: str(t) for c, t in clientes.dtypes.items()},
        "ejemplos_valores": {c: clientes[c].dropna().astype(str).unique()[:6].tolist() for c in clientes.columns if clientes[c].dtype == object},
        "campanas": estado["campanas"][["id", "producto", "objetivo", "canales_permitidos", "activa"]].to_dict("records"),
        "reglas_actuales": estado["reglas"].to_dict("records"),
        "parametros": dict(zip(estado["params"].parametro, estado["params"].valor)),
    }
    msg = Anthropic().messages.create(
        model=os.environ.get("NBA_MODELO", "claude-sonnet-5-5"), max_tokens=1500,
        system="Traduces pedidos de negocio de una telco a configuracion de un motor Next Best Action. " + ESQUEMA,
        messages=[{"role": "user", "content": f"Contexto:\n{json.dumps(contexto, ensure_ascii=False, default=str)}\n\nPedido: {pedido}"}])
    texto = msg.content[0].text
    return json.loads(texto[texto.find("{"): texto.rfind("}") + 1])


def validar_propuesta(prop, clientes, estado):
    errores = []
    camp_ids = set(estado["campanas"].id)
    for f in prop.get("filas", []):
        if f.get("atributo") not in clientes.columns:
            errores.append(f"La columna '{f.get('atributo')}' no existe en la base.")
        if f.get("operador") not in OPERADORES:
            errores.append(f"Operador desconocido: {f.get('operador')}.")
        if f.get("alcance_nivel") == "campana" and not set(str(f.get("alcance_valores")).split("|")) <= camp_ids:
            errores.append(f"Campaña desconocida en {f.get('alcance_valores')}.")
    for k in prop.get("campanas", {}):
        if k not in camp_ids:
            errores.append(f"Campaña desconocida: {k}.")
    return errores


def aplicar_propuesta(prop, estado):
    nuevo = {k: v.copy() for k, v in estado.items()}
    cols = list(nuevo["reglas"].columns)
    for f in prop.get("filas", []):
        nuevo["reglas"].loc[len(nuevo["reglas"])] = [str(f.get(c, "")) for c in cols]
    for k, v in prop.get("parametros", {}).items():
        m = nuevo["params"].parametro == k
        if m.any():
            nuevo["params"].loc[m, "valor"] = str(v)
        else:
            nuevo["params"].loc[len(nuevo["params"])] = [k, str(v)]
    for cid, cambios in prop.get("campanas", {}).items():
        for col, v in cambios.items():
            nuevo["campanas"].loc[nuevo["campanas"].id == cid, col] = v
    return nuevo


# ----------------------------------------------------------------------------- pagina
st.title("Consola del Orquestador NBA")
ruta = st.sidebar.text_input("Base de clientes (CSV)", str(RAIZ / "datos" / "clientes.csv"))
if not Path(ruta).exists():
    st.error("No encuentro la base de clientes en esa ruta. Genera una de prueba con `python3 motor/generar_datos.py`.")
    st.stop()
clientes = cargar_clientes(ruta)
st.sidebar.caption(f"{len(clientes):,} clientes · {clientes.shape[1]} columnas".replace(",", "."))
st.sidebar.markdown(f"**Versión publicada:** v{st.session_state.version}")
for v, t in reversed(st.session_state.historial):
    st.sidebar.caption(f"v{v} · {t}")

pub = st.session_state.publicada
bor = st.session_state.borrador

with st.expander("Pedir un cambio en español (copiloto)", expanded=True):
    pedido = st.text_area("Cambio", placeholder="Ej.: no ofrecer terminales a clientes prepago de estrato 1 o 2", key="pedido")
    if st.button("Traducir a configuración", disabled=not pedido):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.warning("El copiloto necesita la variable ANTHROPIC_API_KEY. Mientras tanto, edita las tablas de abajo.")
        else:
            with st.spinner("Traduciendo..."):
                try:
                    prop = copiloto(pedido, clientes, bor)
                    st.session_state.prop = prop
                except Exception as e:  # noqa: BLE001
                    st.error(f"No pude traducir el pedido: {e}")
    prop = st.session_state.get("prop")
    if prop:
        st.write(prop.get("explicacion", ""))
        if prop.get("filas"):
            st.dataframe(pd.DataFrame(prop["filas"]), hide_index=True)
        if prop.get("parametros") or prop.get("campanas"):
            st.json({k: prop[k] for k in ("parametros", "campanas") if prop.get(k)})
        errs = validar_propuesta(prop, clientes, bor)
        for e in errs:
            st.error(e)
        if st.button("Agregar al borrador", disabled=bool(errs)):
            st.session_state.borrador = aplicar_propuesta(prop, bor)
            st.session_state.prop = None
            st.rerun()

st.subheader("Borrador de configuración")
t1, t2, t3 = st.tabs(["Reglas", "Campañas", "Parámetros"])
with t1:
    bor["reglas"] = st.data_editor(bor["reglas"], num_rows="dynamic", width="stretch", key="ed_reglas")
with t2:
    bor["campanas"] = st.data_editor(bor["campanas"], num_rows="dynamic", width="stretch", key="ed_camp")
with t3:
    bor["params"] = st.data_editor(bor["params"], num_rows="dynamic", width="stretch", key="ed_params")

try:
    o_pub, r_pub, _, _ = correr(pub, clientes)
    o_bor, r_bor, seg, cfg_bor = correr(bor, clientes)
    _, r_base, _, _ = correr(bor, clientes, "codicioso")
except Exception as e:  # noqa: BLE001
    st.error(f"El borrador no se puede ejecutar: {e}")
    st.stop()

st.subheader("Impacto del borrador frente a la versión publicada")
mp, mb = r_pub.metricas, r_bor.metricas
c = st.columns(5)
c[0].metric("Valor esperado", f"{mb['valor_esperado']:,.1f}", f"{100 * (mb['valor_esperado'] / mp['valor_esperado'] - 1):+.1f}%")
c[1].metric("Clientes con acción", f"{mb['clientes_con_accion']:,}", f"{mb['clientes_con_accion'] - mp['clientes_con_accion']:+,}")
c[2].metric("Productos", f"{mb['productos_asignados']:,}", f"{mb['productos_asignados'] - mp['productos_asignados']:+,}")
c[3].metric("Jerarquía", f"{mb['indicador_jerarquia_pct']:.1f}%", f"{mb['indicador_jerarquia_pct'] - mp['indicador_jerarquia_pct']:+.1f} pts")
c[4].metric("Frente a la línea base", f"{100 * (mb['valor_esperado'] / r_base.metricas['valor_esperado'] - 1):+.1f}%")
st.caption(f"Corrida en {seg:.1f} s · solver {o_bor.diagnostico.get('solver')} · brecha de optimalidad {o_bor.diagnostico.get('brecha_optimalidad', 0):.1e}")

cc = st.columns(2)
uso = pd.DataFrame({"canal": list(mb["uso_por_canal"]), "usados": list(mb["uso_por_canal"].values()),
                    "cupo": [cfg_bor.cupo(ch) for ch in mb["uso_por_canal"]],
                    "precio sombra": [r_bor.precios_sombra.get(ch, 0) for ch in mb["uso_por_canal"]]})
cc[0].markdown("**Uso de cupos y precio sombra** (valor de un cupo más)")
cc[0].dataframe(uso, hide_index=True, width="stretch")
if cc[1].button("Validar el borrador (todas las reglas, cliente por cliente)"):
    v = validar_generico(r_bor.parrilla, clientes, cfg_bor)
    (cc[1].success if v["total"] == 0 else cc[1].error)(f"{v['total']} violaciones")
    cc[1].json(v)

col_pub = st.columns([1, 3])
nota = col_pub[1].text_input("Qué cambia en esta versión", key="nota")
if col_pub[0].button("Publicar borrador", type="primary", disabled=not nota):
    st.session_state.version += 1
    v = st.session_state.version
    destino = RAIZ / "config" / "versiones" / f"v{v}"
    destino.mkdir(parents=True, exist_ok=True)
    bor["params"].to_csv(destino / "config_parametros.csv", index=False)
    bor["campanas"].to_csv(destino / "config_campanas.csv", index=False)
    bor["reglas"].to_csv(destino / "config_reglas.csv", index=False)
    st.session_state.publicada = {k: x.copy() for k, x in bor.items()}
    st.session_state.historial.append((v, nota))
    st.rerun()

st.subheader("Por qué este cliente")
cid = st.text_input("Id de cliente", r_bor.parrilla.id_cliente.iat[0])
fila = np.flatnonzero(o_bor.df.id_cliente.values == cid)
if len(fila):
    i = int(fila[0])
    k = int(o_bor._elec[i]) if hasattr(o_bor, "_elec") else -1
    if k >= 0:
        st.info(frase(o_bor, i, k, o_bor._combo[i, k], r_bor.precios_sombra))
    else:
        st.info(frase_sin_accion(o_bor, i))
    st.caption("Motor: " + r_bor.parrilla.razon.iat[i])
else:
    st.warning("No encuentro ese cliente en la base.")

st.subheader("Parrilla")
st.dataframe(r_bor.parrilla.head(200), hide_index=True, width="stretch")
st.download_button("Descargar parrilla (CSV)", r_bor.parrilla.to_csv(index=False).encode(), "parrilla.csv", "text/csv")

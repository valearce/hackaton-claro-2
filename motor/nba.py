"""Orquestador NBA configurable — prototipo.

Todo numero o regla de negocio vive en config/ (CSV). El codigo solo sabe:
  1. evaluar reglas declarativas (atributo, operador, valor) sobre cualquier columna,
  2. armar las opciones de contacto posibles por cliente,
  3. repartir cupos (codicioso = linea base, u optimo global = programacion lineal),
  4. explicar cada decision.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


# ----------------------------------------------------------------------------- config
def _lista(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() == "":
        return []
    return [x.strip() for x in str(v).split("|") if x.strip()]


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return v


@dataclass
class Config:
    params: dict
    campanas: pd.DataFrame
    reglas: pd.DataFrame

    @classmethod
    def cargar(cls, carpeta="config", overrides: dict | None = None):
        p = pd.read_csv(f"{carpeta}/config_parametros.csv", dtype=str)
        params = {r.parametro: _num(r.valor) for r in p.itertuples()}
        if overrides:
            params.update(overrides)
        camp = pd.read_csv(f"{carpeta}/config_campanas.csv", dtype={"activa": int})
        reglas = pd.read_csv(f"{carpeta}/config_reglas.csv", dtype=str).fillna("")
        return cls(params, camp, reglas)

    def p(self, clave, defecto=None):
        return self.params.get(clave, defecto)

    @property
    def canales(self):
        pref = "canal.capacidad_por_corrida."
        return [k[len(pref):] for k in self.params if k.startswith(pref)]

    def cupo(self, c):
        return int(self.p(f"canal.capacidad_por_corrida.{c}"))

    def tope(self, c):
        return int(self.p(f"politica_contacto.max_productos_por_canal.{c}", 1))

    def campanas_activas(self, fecha=None):
        c = self.campanas[self.campanas.activa == 1].copy()
        fecha = fecha or self.p("corrida.fecha")
        if fecha:
            c = c[(c.vigencia_inicio <= fecha) & (c.vigencia_fin >= fecha)]
        return c.reset_index(drop=True)


# ----------------------------------------------------------------------------- reglas
OPERADORES = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    "<": lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
    ">": lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "en": lambda s, v: s.astype(str).isin([str(x) for x in _lista(v)]),
    "no_en": lambda s, v: ~s.astype(str).isin([str(x) for x in _lista(v)]),
    "contiene": lambda s, v: s.fillna("").astype(str).str.split("|").apply(lambda xs: str(v) in xs),
    "no_contiene": lambda s, v: ~s.fillna("").astype(str).str.split("|").apply(lambda xs: str(v) in xs),
    "entre": lambda s, v: s.between(*[_num(x) for x in _lista(v)]),
}


def evaluar_regla(df, regla, campana=None):
    """Devuelve una Serie booleana: True = la condicion de la regla se cumple."""
    if regla.atributo not in df.columns:
        raise KeyError(f"Regla {regla.id}: la columna '{regla.atributo}' no existe en la base")
    valor = regla.valor
    if campana is not None and valor == "$producto":
        valor = campana.producto
    if regla.operador not in ("en", "no_en", "contiene", "no_contiene", "entre"):
        valor = _num(valor)
    cond = OPERADORES[regla.operador](df[regla.atributo], valor).fillna(False).astype(bool)
    # accion 'excluir' = excluye cuando la condicion es cierta; 'exigir' = excluye cuando NO lo es
    return cond if regla.accion == "excluir" else ~cond


def excluye(df, filas, campana=None):
    """Regla compuesta: varias filas con el mismo id se combinan con Y.
    Devuelve True donde la regla EXCLUYE al cliente."""
    cond = np.ones(len(df), bool)
    for r in filas:
        cond &= evaluar_regla(df, r._replace(accion="excluir"), campana).values
    return cond if filas[0].accion == "excluir" else ~cond


def agrupar(reglas):
    """Lista de reglas (cada una = lista de filas con el mismo id), en orden de aparicion."""
    return [list(g.itertuples()) for _, g in reglas.groupby("id", sort=False)]


def aplica_a_campana(regla, camp):
    nivel, vals = regla.alcance_nivel, _lista(regla.alcance_valores)
    if nivel == "global":
        return True
    if nivel == "campana":
        return camp.id in vals
    if nivel == "grupo":  # grupo de campanas: por producto u objetivo
        return camp.producto in vals or camp.objetivo in vals
    return False


# ----------------------------------------------------------------------------- motor
@dataclass
class Resultado:
    parrilla: pd.DataFrame
    metricas: dict
    precios_sombra: dict = field(default_factory=dict)


class Orquestador:
    def __init__(self, cfg: Config, clientes: pd.DataFrame):
        self.cfg = cfg
        self.df = clientes.reset_index(drop=True)
        self.camp = cfg.campanas_activas()
        self.canales = cfg.canales
        self._preparar()

    # -- 1. elegibilidad ------------------------------------------------------
    def _preparar(self):
        cfg, df, camp = self.cfg, self.df, self.camp
        n, P, C = len(df), len(camp), len(self.canales)
        reglas = cfg.reglas[cfg.reglas.activa.astype(str) == "1"]
        self.sp = np.column_stack([df[c].values for c in camp.columna_score]) if P else np.zeros((n, 0))
        self.vn = camp.valor_negocio.values.astype(float)
        self.sc = np.column_stack([df[f"score_canal_{c}"].values for c in self.canales])

        # razones de exclusion por campana (primera regla que la tumba)
        self.razon_camp = np.full((n, P), "", dtype=object)
        elig = np.ones((n, P), bool)
        umbral_p = float(cfg.p("priorizacion.umbral_score_producto", 0))
        reglas_eleg = agrupar(reglas[reglas.tipo == "elegibilidad"])
        for j, c in camp.iterrows():
            for filas in reglas_eleg:
                if aplica_a_campana(filas[0], c):
                    m = excluye(df, filas, c) & elig[:, j]
                    self.razon_camp[m, j] = filas[0].id
                    elig[m, j] = False
            m = (self.sp[:, j] < umbral_p) & elig[:, j]
            self.razon_camp[m, j] = "umbral_score_producto"
            elig[m, j] = False
        self.elig = elig

        canal_ok = np.ones((n, C), bool)
        umbral_c = float(cfg.p("canal.umbral_score_canal", 0))
        reglas_canal = agrupar(reglas[reglas.tipo == "canal"])
        for k, ch in enumerate(self.canales):
            for filas in reglas_canal:
                r = filas[0]
                if r.alcance_nivel == "global" or ch in _lista(r.alcance_valores):
                    canal_ok[:, k] &= ~excluye(df, filas)
            canal_ok[:, k] &= self.sc[:, k] >= umbral_c
        self.canal_ok = canal_ok

        # politica de contacto: tope semanal
        tope_sem = int(cfg.p("politica_contacto.max_contactos_semana", 99))
        self.bloq_semana = df["contactos_semana_actual"].values >= tope_sem

        # campana x canal permitido
        self.permite = np.array([[ch in _lista(c.canales_permitidos) for ch in self.canales]
                                 for _, c in camp.iterrows()]).reshape(P, C)

        # jerarquia: rango 0 = la preferida
        jer = _lista(cfg.p("priorizacion.jerarquia"))
        rango = {cid: i for i, cid in enumerate(jer)}
        self.rango = np.array([rango.get(cid, len(jer)) for cid in camp.id])
        r_elig = np.where(elig, self.rango[None, :], 10**6)
        self.top_jer = np.where(elig.any(1), r_elig.argmin(1), -1)  # campana de mayor jerarquia elegible

    # -- 2. opciones (canal, combo de campanas) por cliente -------------------
    def _opciones(self, bono_jer: float):
        """Para cada cliente y canal: el mejor combo de campanas y su utilidad."""
        n, C, P = len(self.df), len(self.canales), len(self.camp)
        mejor_u = np.full((n, C), -np.inf)
        mejor_v = np.zeros((n, C))
        mejor_combo = np.empty((n, C), dtype=object)
        for k, ch in enumerate(self.canales):
            perm = [j for j in range(P) if self.permite[j, k]]
            for t in range(1, self.cfg.tope(ch) + 1):
                for combo in itertools.combinations(perm, t):
                    ok = self.elig[:, list(combo)].all(1) & self.canal_ok[:, k] & ~self.bloq_semana
                    v = self.sc[:, k] * (self.sp[:, list(combo)] * self.vn[list(combo)]).sum(1)
                    u = v + bono_jer * np.isin(self.top_jer, combo)
                    u = np.where(ok, u, -np.inf)
                    mejor = u > mejor_u[:, k]
                    mejor_u[mejor, k], mejor_v[mejor, k] = u[mejor], v[mejor]
                    mejor_combo[np.flatnonzero(mejor), k] = [combo] * int(mejor.sum())
        return mejor_u, mejor_v, mejor_combo

    # -- 3a. linea base (codiciosa, segun el documento del reto) --------------
    def _codicioso(self):
        cfg = self.cfg
        w = {k: float(cfg.p(f"priorizacion.pesos.{k}")) for k in ("score_producto", "valor_negocio", "jerarquia")}
        P = len(self.camp)
        nivel_jer = 1 - self.rango / max(P - 1, 1)  # 1, 0.5, 0
        punt = w["score_producto"] * self.sp + w["valor_negocio"] * self.vn + w["jerarquia"] * nivel_jer
        punt = np.where(self.elig, punt, -np.inf)
        orden = np.argsort(-punt.max(1), kind="stable")
        cupo = {ch: cfg.cupo(ch) for ch in self.canales}
        asign = {}
        for i in orden:
            if self.bloq_semana[i] or not np.isfinite(punt[i]).any():
                continue
            for k in np.argsort(-self.sc[i], kind="stable"):
                ch = self.canales[k]
                if not self.canal_ok[i, k] or cupo[ch] <= 0:
                    continue
                cands = [j for j in np.argsort(-punt[i], kind="stable")
                         if self.elig[i, j] and self.permite[j, k]]
                if not cands:
                    continue
                asign[i] = (k, tuple(cands[: cfg.tope(ch)]))
                cupo[ch] -= 1
                break
        return asign, {}

    # -- 3b. optimo global ---------------------------------------------------
    # El reparto es un problema de transporte: cada cliente elige a lo sumo una
    # opcion (canal + combo) y cada canal tiene cupo. Dos solvers exactos:
    #   'dual': precios sombra por descenso coordinado sobre los C precios de canal
    #           (misma idea de dualidad lagrangiana que usa Alibaba a escala, KDD'19);
    #           devuelve ademas una cota superior => certificado de optimalidad.
    #   'lp'  : programacion lineal con HiGHS (respaldo si el certificado no cierra).
    def _optimo(self, metodo=None):
        metodo = metodo or self.cfg.p("optimizacion.solver", "dual")
        bono = float(self.cfg.p("optimizacion.bono_jerarquia", 0))
        u, v, combo = self._opciones(bono)
        cap = np.array([self.cfg.cupo(ch) for ch in self.canales], float)
        if metodo == "dual":
            elec, lam, gap = self._dual(u, cap)
            if gap > float(self.cfg.p("optimizacion.tolerancia_brecha", 1e-6)):
                metodo = "lp"  # el certificado no cerro: resolver exacto con HiGHS
        if metodo == "lp":
            elec, lam = self._lp(u, cap)
            gap = 0.0
        self._u, self._v, self._combo, self._elec = u, v, combo, elec
        sombra = {ch: round(float(lam[k]), 4) for k, ch in enumerate(self.canales)}
        self.diagnostico = {"solver": metodo, "brecha_optimalidad": float(gap)}
        return elec, sombra

    def _dual(self, u, cap, iters=500):
        U = np.where(np.isfinite(u), u, -1e9)
        n, C = U.shape
        lam = np.zeros(C)
        for _ in range(iters):
            prev = lam.copy()
            for k in range(C):
                otros = np.delete(U - lam, k, axis=1).max(1) if C > 1 else np.full(n, -np.inf)
                d = U[:, k] - np.maximum(0.0, otros)       # ganancia de elegir k frente a lo siguiente mejor
                pos = d[d > 0]
                c = int(cap[k])
                lam[k] = 0.0 if len(pos) <= c else np.partition(pos, len(pos) - c - 1)[len(pos) - c - 1]
            if np.abs(lam - prev).max() < 1e-12:
                break
        neto = U - lam
        orden = np.sort(np.concatenate([neto, np.zeros((n, 1))], 1), 1)  # 0 = opcion "sin accion"
        holgura = orden[:, -1] - orden[:, -2]  # que tan clara es la decision de cada cliente
        dual = np.maximum(0, neto.max(1)).sum() + (cap * lam).sum()
        mejor = neto.argmax(1)
        base = np.where(neto[np.arange(n), mejor] > 0, mejor, -1)
        for eps in (0.0, 1e-6, 1e-4, 1e-3, 1e-2):
            # los clientes con decision clara se quedan con su mejor opcion a precios sombra;
            # los "en disputa" (empates o casi) se resuelven exacto con un LP pequeno
            disputa = holgura <= eps
            elec = np.where(disputa, -1, base)
            resid = cap - np.bincount(elec[elec >= 0], minlength=C)
            if (resid < 0).any():
                continue
            ids = np.flatnonzero(disputa & np.isfinite(u).any(1))
            if len(ids):
                e_sub, _ = self._lp(u[ids], resid)
                elec[ids] = e_sub
            primal = U[np.flatnonzero(elec >= 0), elec[elec >= 0]].sum()
            brecha = (dual - primal) / max(dual, 1e-9)
            if brecha <= float(self.cfg.p("optimizacion.tolerancia_brecha", 1e-6)):
                break
        return elec, lam, brecha

    def _lp(self, u, cap):
        n, C = u.shape
        filas, cols = np.nonzero(np.isfinite(u))
        nv = len(filas)
        if nv == 0:
            return np.full(n, -1), np.zeros(C)
        A = coo_matrix((np.ones(2 * nv), (np.concatenate([filas, n + cols]), np.concatenate([np.arange(nv)] * 2))),
                       shape=(n + C, nv)).tocsr()
        sol = linprog(-u[filas, cols], A_ub=A, b_ub=np.concatenate([np.ones(n), cap]), bounds=(0, 1), method="highs-ds")
        assert sol.status == 0, sol.message
        elec = np.full(n, -1)
        x = sol.x > 0.5
        elec[filas[x]] = cols[x]
        return elec, -sol.ineqlin.marginals[n:]

    # -- 4. parrilla + explicacion -------------------------------------------
    def correr(self, algoritmo=None) -> Resultado:
        algoritmo = algoritmo or self.cfg.p("optimizacion.algoritmo", "optimo")
        n = len(self.df)
        ids_c = self._ids_c = self.camp.id.values
        self._prods = self.camp.producto.values
        c1, c2 = np.full(n, "", dtype=object), np.full(n, "", dtype=object)
        canal = np.full(n, "", dtype=object)
        razon = np.empty(n, dtype=object)
        self.diagnostico = {"solver": "codicioso"}
        if algoritmo == "optimo":
            elec, sombra = self._optimo()
            asign = {int(i): (int(elec[i]), self._combo[i, elec[i]]) for i in np.flatnonzero(elec >= 0)}
        else:
            asign, sombra = self._codicioso()
        for i, (k, combo) in asign.items():
            canal[i] = self.canales[k]
            c1[i] = ids_c[combo[0]]
            if len(combo) > 1:
                c2[i] = ids_c[combo[1]]
            razon[i] = self._razon(i, k, combo, algoritmo, sombra)
        for i in np.flatnonzero(canal == ""):
            razon[i] = self._razon_sin(i)
        parr = pd.DataFrame({"id_cliente": self.df.id_cliente.values,
                             "estado": np.where(canal != "", "asignado", "sin_accion"),
                             "canal": canal, "campana_1": c1, "campana_2": c2, "razon": razon})
        return Resultado(parr, self.metricas(parr), sombra)

    def _razon(self, i, k, combo, alg, sombra):
        ch = self.canales[k]
        if alg != "optimo":
            return f"Mejor canal habilitado con cupo ({ch}); {len(combo)} producto(s) segun tope del canal"
        prods = self._prods
        txt = f"Optimo global: {ch} con {'+'.join(prods[j] for j in combo)} (valor {self._v[i, k]:.3f})"
        alt = [(self._v[i, q], self.canales[q]) for q in range(len(self.canales))
               if q != k and np.isfinite(self._u[i, q])]
        if alt:
            a = max(alt)
            txt += f"; mejor alternativa {a[1]} {a[0]:.3f}"
        if sombra.get(ch, 0) > 0:
            txt += f"; costo de oportunidad del cupo {ch} {sombra[ch]:.3f}"
        return txt

    def _razon_sin(self, i):
        if self.bloq_semana[i]:
            return "Tope semanal de contactos"
        if not self.elig[i].any():
            return "Sin campana elegible (" + ";".join(
                f"{self._ids_c[j]}:{self.razon_camp[i, j]}" for j in range(len(self._ids_c))) + ")"
        if not (self.canal_ok[i][None, :] & self.permite[self.elig[i]]).any():
            return "Sin canal habilitado para sus campanas elegibles"
        return "Sin cupo disponible en sus canales (otros clientes generaban mas valor)"

    def metricas(self, parr):
        idx = {c: j for j, c in enumerate(self.camp.id)}
        kch = {c: k for k, c in enumerate(self.canales)}
        a = parr[parr.estado == "asignado"]
        ii = a.index.values
        valor, nprod, jer_ok = 0.0, 0, 0
        for col in ("campana_1", "campana_2"):
            m = a[col] != ""
            j = a.loc[m, col].map(idx).values.astype(int)
            k = a.loc[m, "canal"].map(kch).values.astype(int)
            r = ii[m.values]
            valor += float((self.sp[r, j] * self.sc[r, k] * self.vn[j]).sum())
            nprod += int(m.sum())
        top = self.top_jer[ii]
        recibio = np.zeros(len(ii), bool)
        for col in ("campana_1", "campana_2"):
            recibio |= a[col].map(idx).fillna(-2).values.astype(int) == top
        return {
            "valor_esperado": round(valor, 1),
            "clientes_con_accion": int(len(a)),
            "productos_asignados": nprod,
            "indicador_jerarquia_pct": round(100 * recibio.mean(), 1) if len(a) else 0.0,
            "uso_por_canal": a.canal.value_counts().reindex(self.canales, fill_value=0).to_dict(),
        }

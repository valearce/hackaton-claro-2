"""Motor de análisis de los experimentos (LP/HiGHS): expone elegibilidad, bloqueos y paquetes por cliente.

Es la versión previa del motor, conservada solo para explicar viabilidad y simular escenarios.
El resultado oficial (parrilla, valor y certificado) lo da `modelo.nba` (OR-Tools)."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import math
import operator
import time

import numpy as np
import pandas as pd

CONFIG = Path(__file__).resolve().parents[1] / "config"
OUTPUT_COLUMNS = ["id_cliente", "estado", "canal", "campana_1", "campana_2", "razon"]
OPS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
       "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def load_config(directory=CONFIG):
    directory = Path(directory)
    return {key: json.loads((directory / f"{key}.json").read_text(encoding="utf-8-sig"))
            for key in ("campanas", "reglas", "parametros")}


def applies(rule, campaign=None, channel=None):
    scope = rule["alcance"]
    level, values = scope["nivel"], scope.get("valores", [])
    if level == "global":
        return True
    if level == "canal":
        return channel in values
    field = {"campana": "id", "producto": "producto", "objetivo": "objetivo"}.get(level)
    if field is None:
        raise ValueError(f"Alcance desconocido: {level}")
    return campaign is not None and campaign[field] in values


def operand(value, campaign):
    if isinstance(value, list):
        return [operand(item, campaign) for item in value]
    if value == "$producto":
        if campaign is None:
            raise ValueError("$producto requiere una campaña")
        return campaign["producto"]
    if isinstance(value, str) and value.startswith("$"):
        raise ValueError(f"Referencia no reconocida: {value}")
    return value


def condition_mask(data, condition, campaign):
    if "todas" in condition:
        return np.logical_and.reduce([condition_mask(data, item, campaign) for item in condition["todas"]])
    if "alguna" in condition:
        return np.logical_or.reduce([condition_mask(data, item, campaign) for item in condition["alguna"]])
    column, op = condition["atributo"], condition["operador"]
    if column not in data:
        raise ValueError(f"La regla usa una columna ausente: {column}")
    series = data[column]
    value = operand(condition["valor"], campaign)
    if op in OPS:
        return OPS[op](series, value).to_numpy(dtype=bool)
    if op in ("en", "no_en"):
        values = value if isinstance(value, list) else [value]
        mask = series.isin(values).to_numpy()
        return ~mask if op == "no_en" else mask
    if op == "contiene":
        return series.astype(str).str.split("|", regex=False).map(lambda items: str(value) in items).to_numpy()
    raise ValueError(f"Operador no soportado: {op}")


def numeric_column(data, column, score=False):
    values = pd.to_numeric(data[column], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Valores no finitos en {column}")
    if score and ((values < 0).any() or (values > 1).any()):
        raise ValueError(f"El score {column} está fuera de [0, 1]")
    return values


@dataclass
class Bundle:
    picks: np.ndarray
    utility: np.ndarray
    expected: np.ndarray


class Engine:
    def __init__(self, data, config, as_of=None):
        self.data = data.reset_index(drop=True).copy()
        self.config = config
        self.params = config["parametros"]
        self.campaigns = config["campanas"]
        self.rules = [rule for rule in config["reglas"] if rule["activa"]]
        self.day = date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or date.today())
        self.n, self.m = len(data), len(self.campaigns)
        self.channels = list(self.params["canal"]["capacidad_por_corrida"])
        self.k = len(self.channels)
        self._validate()
        self.ids = self.data["id_cliente"].astype(str).to_numpy()
        self.capacity = np.array([self.params["canal"]["capacidad_por_corrida"][c] for c in self.channels], dtype=int)
        self.limits = np.array([self.params["politica_contacto"]["max_productos_por_canal"][c] for c in self.channels], dtype=int)
        hierarchy = self.params["priorizacion"]["jerarquia"]
        hierarchy = hierarchy + [c["id"] for c in self.campaigns if c["id"] not in hierarchy]
        self.rank = np.array([hierarchy.index(c["id"]) for c in self.campaigns])
        self.active = np.array([c["activa"] and date.fromisoformat(c["vigencia_inicio"]) <= self.day <= date.fromisoformat(c["vigencia_fin"]) for c in self.campaigns])
        self.product_scores = np.column_stack([numeric_column(self.data, c["columna_score"], score=True) for c in self.campaigns])
        self.channel_scores = np.column_stack([numeric_column(self.data, self.params["canal"]["columnas_score"][c], score=True) for c in self.channels])
        self.values = np.array([c["valor_negocio"] for c in self.campaigns])
        self.value_product = self.product_scores * self.values
        weights = self.params["priorizacion"]["pesos"]
        rank_level = 1 - self.rank / max(self.m - 1, 1)
        self.priority = (weights["score_producto"] * self.product_scores
                         + weights["valor_negocio"] * self.values
                         + weights["jerarquia"] * rank_level)
        week_column = self.params["politica_contacto"].get("columna_contactos_semana", "contactos_semana_actual")
        self.weekly_ok = numeric_column(self.data, week_column) < self.params["politica_contacto"]["max_contactos_semana"]
        self.product_ok = np.broadcast_to(self.active, (self.n, self.m)).copy()
        self.product_blocks = [[] for _ in self.campaigns]
        for j, campaign in enumerate(self.campaigns):
            low_score = self.product_scores[:, j] < self.params["priorizacion"]["umbral_score_producto"]
            self.product_ok[:, j] &= ~low_score
            self.product_blocks[j].append((low_score, "Score de producto inferior al umbral"))
            for rule in self.rules:
                if rule["tipo"] == "elegibilidad" and applies(rule, campaign):
                    mask = condition_mask(self.data, rule["condicion"], campaign)
                    self.product_ok[:, j] &= ~mask
                    self.product_blocks[j].append((mask, rule["nombre"]))
        self.feasible = []
        for h, channel in enumerate(self.channels):
            allowed = self.product_ok.copy()
            channel_ok = self.weekly_ok & (self.channel_scores[:, h] >= self.params["canal"]["umbral_score_canal"])
            allowed &= channel_ok[:, None]
            for j, campaign in enumerate(self.campaigns):
                if channel not in campaign["canales_permitidos"]:
                    allowed[:, j] = False
                for rule in self.rules:
                    if rule["tipo"] == "canal" and applies(rule, campaign, channel):
                        allowed[:, j] &= ~condition_mask(self.data, rule["condicion"], campaign)
            self.feasible.append(allowed)

    def _validate(self):
        if self.n == 0 or self.m == 0 or self.k == 0:
            raise ValueError("Se necesitan clientes, campañas y canales")
        if self.data["id_cliente"].isna().any() or self.data["id_cliente"].astype(str).eq("").any() or self.data["id_cliente"].duplicated().any():
            raise ValueError("id_cliente debe ser único y no vacío")
        if len({c["id"] for c in self.campaigns}) != self.m:
            raise ValueError("IDs de campaña duplicados")
        if self.params["politica_contacto"]["canales_por_cliente"] != 1:
            raise ValueError("El contrato de salida de esta versión admite un canal por cliente")
        if self.params["priorizacion"]["modo"] not in ("ponderado", "jerarquia_estricta"):
            raise ValueError("Modo de priorización desconocido")
        if self.params["canal"]["criterio"] not in ("score_canal", "orden_preferencia"):
            raise ValueError("Criterio de canal desconocido")
        weights = self.params["priorizacion"]["pesos"]
        if set(weights) != {"score_producto", "valor_negocio", "jerarquia"}:
            raise ValueError("Se requieren exactamente los tres pesos documentados")
        if any(not 0 <= float(v) <= 1 for v in weights.values()) or not math.isclose(sum(weights.values()), 1, abs_tol=1e-9):
            raise ValueError("Los pesos deben estar entre 0 y 1 y sumar 1")
        for key in ("umbral_score_producto",):
            if not 0 <= self.params["priorizacion"][key] <= 1:
                raise ValueError(f"Umbral inválido: {key}")
        if not 0 <= self.params["canal"]["umbral_score_canal"] <= 1:
            raise ValueError("Umbral de canal inválido")
        for channel in self.channels:
            capacity = self.params["canal"]["capacidad_por_corrida"][channel]
            limit = self.params["politica_contacto"]["max_productos_por_canal"][channel]
            if type(capacity) is not int or capacity < 0 or type(limit) is not int or not 0 <= limit <= 2:
                raise ValueError("Cupos enteros no negativos; el CSV fijo admite hasta dos productos")
        for campaign in self.campaigns:
            if not 0 <= campaign["valor_negocio"] <= 1:
                raise ValueError("Valor de negocio fuera de [0, 1]")
            if set(campaign["canales_permitidos"]) - set(self.channels):
                raise ValueError(f"Canal no configurado en {campaign['id']}")
        for rule in self.rules:
            if rule["accion"] != "excluir" or rule["tipo"] not in ("elegibilidad", "canal"):
                raise ValueError(f"Regla no soportada: {rule['id']}")
            if rule["tipo"] == "elegibilidad" and rule["alcance"]["nivel"] == "canal":
                raise ValueError("Una regla de elegibilidad no puede tener alcance canal; usa tipo canal")
            self._validate_condition(rule["condicion"])
        weekly = numeric_column(self.data, self.params["politica_contacto"].get("columna_contactos_semana", "contactos_semana_actual"))
        if (weekly < 0).any() or (weekly != np.floor(weekly)).any():
            raise ValueError("Los contactos semanales deben ser enteros no negativos")

    def _validate_condition(self, condition):
        for connective in ("todas", "alguna"):
            if connective in condition:
                if not condition[connective]:
                    raise ValueError("Una condición compuesta no puede estar vacía")
                for item in condition[connective]:
                    self._validate_condition(item)
                return
        column = condition["atributo"]
        if column not in self.data:
            raise ValueError(f"La regla usa una columna ausente: {column}")
        series = self.data[column]
        if series.isna().any() or (condition["operador"] != "contiene" and series.astype(str).eq("").any()):
            raise ValueError(f"Datos ausentes en una columna usada por las reglas: {column}")
        if pd.api.types.is_numeric_dtype(series):
            numeric_column(self.data, column)

    def bundles(self, objective):
        metric = self.value_product if objective == "valor_esperado" else self.priority
        strict = self.params["priorizacion"]["modo"] == "jerarquia_estricta"
        top = np.argmin(np.where(self.product_ok, self.rank, self.m + 1), axis=1)
        product_codes = np.array([c["producto"] for c in self.campaigns])
        rows = np.arange(self.n)
        result = []
        for h, allowed in enumerate(self.feasible):
            # Las claves posteriores tienen mayor prioridad en lexsort.
            tie_values = {"score_producto": self.product_scores,
                          "valor_negocio": np.broadcast_to(self.values, metric.shape),
                          "jerarquia": np.broadcast_to(-self.rank, metric.shape)}
            keys = [np.broadcast_to(np.arange(self.m), metric.shape)]
            for criterion in reversed(self.params["priorizacion"]["desempate"]):
                if criterion not in tie_values:
                    raise ValueError(f"Criterio de desempate desconocido: {criterion}")
                keys.append(-tie_values[criterion])
            keys.append(np.where(allowed, -metric, np.inf))
            if strict:
                keys.append(np.where(allowed, self.rank, self.m + 1))
            order = np.lexsort(tuple(keys), axis=1)
            picks = np.full((self.n, 2), -1, dtype=int)
            filled = np.zeros(self.n, dtype=int)
            for position in range(self.m):
                candidate = order[:, position]
                ok = allowed[rows, candidate] & (filled < self.limits[h])
                duplicate = (picks[:, 0] >= 0) & (product_codes[np.maximum(picks[:, 0], 0)] == product_codes[candidate])
                ok &= ~duplicate
                chosen = rows[ok]
                picks[chosen, filled[chosen]] = candidate[chosen]
                filled[chosen] += 1
            if strict:
                picks[~np.any(picks == top[:, None], axis=1)] = -1
            utility = np.zeros(self.n)
            expected = np.zeros(self.n)
            for slot in range(2):
                valid = picks[:, slot] >= 0
                r, j = rows[valid], picks[valid, slot]
                utility[r] += metric[r, j] * self.channel_scores[r, h]
                expected[r] += self.value_product[r, j] * self.channel_scores[r, h]
            result.append(Bundle(picks, utility, expected))
        return result

    def baseline(self):
        start = time.perf_counter()
        bundles = self.bundles("prioridad")
        best = np.max(np.where(self.product_ok, self.priority, -np.inf), axis=1)
        if self.params["priorizacion"]["modo"] == "jerarquia_estricta":
            rank = np.min(np.where(self.product_ok, self.rank, self.m + 1), axis=1)
            order = np.lexsort((self.ids, -best, rank))
        else:
            order = np.lexsort((self.ids, -best))
        selected = np.full(self.n, -1, dtype=int)
        remaining = self.capacity.copy()
        preference = self.params["canal"]["orden_preferencia"]
        channel_rank = {c: i for i, c in enumerate(preference)}
        for row in order:
            options = [h for h, bundle in enumerate(bundles) if remaining[h] > 0 and bundle.picks[row, 0] >= 0]
            if not options:
                continue
            options.sort(key=lambda h: ((-self.channel_scores[row, h]) if self.params["canal"]["criterio"] == "score_canal" else 0,
                                        channel_rank.get(self.channels[h], self.k)))
            selected[row] = options[0]
            remaining[options[0]] -= 1
        grid = self.grid(selected, bundles, "Línea base")
        return grid, {"metodo": "baseline", "segundos": time.perf_counter() - start}

    def optimize(self):
        from scipy.optimize import linprog  # solo aquí: la regla simple (baseline) no necesita scipy
        from scipy.sparse import coo_matrix
        start = time.perf_counter()
        objective = self.params["optimizacion"]["objetivo"]
        if objective not in ("valor_esperado", "prioridad"):
            raise ValueError("Objetivo debe ser valor_esperado o prioridad")
        bundles = self.bundles(objective)
        utility = np.column_stack([b.utility for b in bundles])
        valid = np.column_stack([b.picks[:, 0] >= 0 for b in bundles]) & (utility > 0)
        valid[:, self.capacity == 0] = False
        customer, channel = np.nonzero(valid)
        selected = np.full(self.n, -1, dtype=int)
        diagnostics = {"metodo": "optimo", "objetivo": objective, "variables": len(customer)}
        if len(customer):
            variables = np.arange(len(customer))
            matrix = coo_matrix((np.ones(2 * len(customer)),
                                 (np.r_[customer, self.n + channel], np.r_[variables, variables])),
                                shape=(self.n + self.k, len(customer))).tocsr()
            solved = linprog(-utility[customer, channel], A_ub=matrix,
                             b_ub=np.r_[np.ones(self.n), self.capacity], bounds=(0, 1),
                             method="highs-ds", options={"time_limit": self.params["optimizacion"].get("limite_segundos", 600)})
            if not solved.success:
                raise RuntimeError(f"El optimizador no acreditó optimalidad: {solved.message}")
            deviation = np.max(np.abs(solved.x - np.rint(solved.x)))
            if deviation > self.params["optimizacion"].get("tolerancia_entera", 1e-6):
                raise RuntimeError(f"Solución fraccionaria: {deviation}; no se redondea silenciosamente")
            chosen = solved.x > 0.5
            selected[customer[chosen]] = channel[chosen]
            diagnostics.update({"estado_solver": solved.message, "objetivo_optimo": float(-solved.fun),
                                "desviacion_entera_maxima": float(deviation), "iteraciones": int(solved.nit)})
        diagnostics["segundos"] = time.perf_counter() - start
        return self.grid(selected, bundles, f"Asignación global ({objective})"), diagnostics

    def grid(self, selected, bundles, description):
        records = []
        for row, channel in enumerate(selected):
            if channel >= 0:
                picks = [int(j) for j in bundles[channel].picks[row] if j >= 0]
                campaign_ids = [self.campaigns[j]["id"] for j in picks]
                reason = f"{description}; {self.channels[channel]}; {len(picks)} producto(s); valor esperado {bundles[channel].expected[row]:.6f}"
                records.append((self.ids[row], "asignado", self.channels[channel], campaign_ids[0], campaign_ids[1] if len(picks) > 1 else "", reason))
            else:
                if not self.weekly_ok[row]:
                    reason = "Tope semanal de contactos"
                elif not self.product_ok[row].any():
                    causes = []
                    for j, campaign in enumerate(self.campaigns):
                        if not self.active[j]:
                            causes.append(f"{campaign['id']}: inactiva o fuera de vigencia")
                        else:
                            failed = next((name for mask, name in self.product_blocks[j] if mask[row]), "Sin elegibilidad")
                            causes.append(f"{campaign['id']}: {failed}")
                    reason = "Sin campaña elegible (" + "; ".join(causes) + ")"
                elif not any(b.picks[row, 0] >= 0 for b in bundles):
                    reason = "Sin canal habilitado compatible: autorización, score, reglas o prioridad estricta"
                elif not any(b.utility[row] > 0 for b in bundles):
                    reason = "Sin valor positivo para la estrategia seleccionada"
                else:
                    reason = "Sin cupo disponible en los canales compatibles"
                records.append((self.ids[row], "sin_accion", "", "", "", reason))
        return pd.DataFrame(records, columns=OUTPUT_COLUMNS)


def condition_scalar(row, condition, campaign):
    """Intérprete escalar para auditar la salida sin reutilizar máscaras del motor."""
    if "todas" in condition:
        return all(condition_scalar(row, c, campaign) for c in condition["todas"])
    if "alguna" in condition:
        return any(condition_scalar(row, c, campaign) for c in condition["alguna"])
    actual = row[condition["atributo"]]
    expected = operand(condition["valor"], campaign)
    op = condition["operador"]
    if op in OPS:
        return bool(OPS[op](actual, expected))
    if op == "contiene":
        return str(expected) in str(actual).split("|")
    if op in ("en", "no_en"):
        values = expected if isinstance(expected, list) else [expected]
        return (actual not in values) if op == "no_en" else (actual in values)
    raise ValueError(f"Operador no soportado: {op}")


def validate_grid(data, grid, config, as_of=None):
    """Auditoría fila a fila de reglas, contactos, canales, cupos y valor oficial."""
    day = date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or date.today())
    params = config["parametros"]
    campaigns = {c["id"]: c for c in config["campanas"]}
    source = data.set_index("id_cliente").to_dict("index")
    errors = {f"R{i:02d}": set() for i in range(1, 17)}
    details = []
    usage = {channel: 0 for channel in params["canal"]["capacidad_por_corrida"]}
    total_value = 0.0
    product_count = 0
    hierarchy_hits = 0
    assigned_count = 0

    def fail(code, customer, reason):
        errors.setdefault(code, set()).add(customer)
        if len(details) < 50:
            details.append({"control": code, "id_cliente": customer, "razon": reason})

    if list(grid.columns) != OUTPUT_COLUMNS or len(grid) != len(data) or set(grid.id_cliente) != set(source) or grid.id_cliente.duplicated().any():
        fail("FORMATO", "parrilla", "Una fila por cliente, IDs únicos y columnas exactas")
    week_column = params["politica_contacto"].get("columna_contactos_semana", "contactos_semana_actual")
    hierarchy = params["priorizacion"]["jerarquia"] + [c for c in campaigns if c not in params["priorizacion"]["jerarquia"]]
    for result in grid.to_dict("records"):
        customer = result["id_cliente"]
        if customer not in source:
            continue
        row = source[customer]
        picked = [result[c] for c in ("campana_1", "campana_2") if result[c]]
        if result["estado"] == "sin_accion":
            if picked or result["canal"]:
                fail("FORMATO", customer, "sin_accion contiene una asignación")
            continue
        channel = result["canal"]
        if result["estado"] != "asignado" or channel not in usage or not picked:
            fail("R13", customer, "Estado o canal inválido")
            continue
        assigned_count += 1
        usage[channel] += 1
        if row[week_column] + 1 > params["politica_contacto"]["max_contactos_semana"]:
            fail("R15", customer, "Se supera el tope semanal")
        if len(picked) > params["politica_contacto"]["max_productos_por_canal"][channel]:
            fail("R14", customer, "Demasiados productos en el contacto")
        q = row[params["canal"]["columnas_score"][channel]]
        if q < params["canal"]["umbral_score_canal"]:
            fail("R11", customer, "Score de canal inferior al umbral")
        eligible = []
        for campaign_id in hierarchy:
            campaign = campaigns[campaign_id]
            active = campaign["activa"] and date.fromisoformat(campaign["vigencia_inicio"]) <= day <= date.fromisoformat(campaign["vigencia_fin"])
            if active and row[campaign["columna_score"]] >= params["priorizacion"]["umbral_score_producto"] and not any(
                rule["activa"] and rule["tipo"] == "elegibilidad" and applies(rule, campaign)
                and condition_scalar(row, rule["condicion"], campaign) for rule in config["reglas"]
            ):
                eligible.append(campaign_id)
        hierarchy_hits += bool(eligible and eligible[0] in picked)
        products = []
        for campaign_id in picked:
            if campaign_id not in campaigns:
                fail("FORMATO", customer, "Campaña desconocida")
                continue
            campaign = campaigns[campaign_id]
            products.append(campaign["producto"])
            if not campaign["activa"] or not date.fromisoformat(campaign["vigencia_inicio"]) <= day <= date.fromisoformat(campaign["vigencia_fin"]):
                fail("VIGENCIA", customer, "Campaña inactiva o fuera de vigencia")
            if channel not in campaign["canales_permitidos"]:
                fail("R12", customer, "Canal no permitido por la campaña")
            score = row[campaign["columna_score"]]
            if score < params["priorizacion"]["umbral_score_producto"]:
                fail("R08", customer, "Score de producto inferior al umbral")
            for rule in config["reglas"]:
                if rule["activa"] and applies(rule, campaign, channel) and condition_scalar(row, rule["condicion"], campaign):
                    fail(rule.get("control", rule["id"]), customer, rule["nombre"])
            total_value += score * q * campaign["valor_negocio"]
            product_count += 1
        if len(products) != len(set(products)):
            fail("R14", customer, "Se repite el mismo producto en el contacto")
    excess = {}
    for channel, count in usage.items():
        overflow = count - params["canal"]["capacidad_por_corrida"][channel]
        if overflow > 0:
            fail("R16", channel, "Cupo de canal superado")
            excess[channel] = overflow
    counts = {key: len(customers) for key, customers in errors.items()}
    return {"violaciones": sum(counts.values()), "controles": counts, "muestras_errores": details,
            "exceso_cupos": excess, "clientes": len(data), "clientes_con_accion": assigned_count,
            "productos_asignados": product_count, "valor_esperado": total_value,
            "indicador_jerarquia": hierarchy_hits / assigned_count if assigned_count else None,
            "uso_canales": usage}

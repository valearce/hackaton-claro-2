"""Problema NBA exacto: reglas y paquetes de uno/dos productos por canal."""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

INT_LIMIT = np.iinfo(np.int64).max // 8
OUTPUT = ["id_cliente", "estado", "canal", "campana_1", "campana_2", "razon"]
TEXT_COLUMNS = {"id_cliente", "region", "tipo_linea", "calificacion_riesgo", "gama_equipo",
                "canales_contactados_mes", "productos_ofertados_mes"}
BINARY_COLUMNS = {"en_mora", "tiene_hogar", "tiene_netflix", "tiene_amazon_prime", "tiene_win",
                  "usa_redes_sociales", "usa_banca_digital", "compras_digitales", "tiene_correo",
                  "autoriza_sms", "autoriza_correo", "autoriza_whatsapp"}
NUMBER_COLUMNS = BINARY_COLUMNS | {"edad", "estrato", "antiguedad_meses", "plan_datos_gb", "consumo_datos_pct",
    "arpu_movil", "dias_mora", "arpu_hogar", "cantidad_ott", "edad_equipo_meses", "quejas_90d", "riesgo_churn",
    "contactos_mes", "contactos_semana_actual", "contactos_asesor_mes", "contactos_sms_mes", "contactos_correo_mes",
    "contactos_whatsapp_mes", "dias_ultimo_contacto"}


def canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def number(value):
    try:
        result = Decimal(str(int(value) if isinstance(value, bool) else value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Valor numérico inválido: {value!r}") from error
    if not result.is_finite():
        raise ValueError("Los números deben ser finitos")
    return result


def integer(value, scale):
    numerator, denominator = number(value).as_integer_ratio()
    result, remainder = divmod(numerator * scale, denominator)
    if remainder:
        raise ValueError("La escala no representa exactamente el decimal")
    if abs(result) > INT_LIMIT:
        raise OverflowError("Coeficiente fuera del rango entero seguro")
    return result


def decimal_string(numerator, scale):
    """Escalas potencia de diez, sin división flotante ni contexto Decimal."""
    digits = len(str(scale)) - 1
    if scale != 10 ** digits:
        raise ValueError("La escala debe ser una potencia de diez")
    sign = "-" if numerator < 0 else ""
    whole, fraction = divmod(abs(int(numerator)), scale)
    suffix = str(fraction).zfill(digits).rstrip("0") if digits else ""
    return f"{sign}{whole}" + (f".{suffix}" if suffix else "")


def scope_matches(rule, campaign, channel=None):
    scope = rule["alcance"]
    level = scope["nivel"]
    if level == "global":
        return True
    if level == "canal":
        return channel in scope.get("valores", [])
    field = {"campana": "id", "producto": "producto", "objetivo": "objetivo"}.get(level)
    if field is None:
        raise ValueError(f"Alcance no reconocido: {level}")
    return campaign[field] in scope.get("valores", [])


def condition_columns(condition):
    if "todas" in condition or "alguna" in condition:
        items = condition.get("todas", condition.get("alguna"))
        if not items:
            raise ValueError("Condición compuesta vacía")
        return set().union(*(condition_columns(item) for item in items))
    return {condition["atributo"]}


def condition_mask(frame, condition, campaign):
    if "todas" in condition:
        return np.logical_and.reduce([condition_mask(frame, item, campaign) for item in condition["todas"]])
    if "alguna" in condition:
        return np.logical_or.reduce([condition_mask(frame, item, campaign) for item in condition["alguna"]])
    actual = frame[condition["atributo"]]

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, str) and value.startswith("$"):
            if value != "$producto":
                raise ValueError(f"Referencia no reconocida: {value}")
            return campaign["producto"]
        return number(value) if isinstance(value, (int, float, Decimal)) else value

    expected = resolve(condition["valor"])
    op = condition["operador"]
    if op == "contiene":
        return actual.astype(str).map(lambda value: str(expected) in value.split("|")).to_numpy(bool)
    if op in ("en", "no_en"):
        values = expected if isinstance(expected, list) else [expected]
        mask = actual.isin(values).to_numpy(bool)
        return ~mask if op == "no_en" else mask
    if op == "==":
        result = actual == expected
    elif op == "!=":
        result = actual != expected
    elif op == "<":
        result = actual < expected
    elif op == "<=":
        result = actual <= expected
    elif op == ">":
        result = actual > expected
    elif op == ">=":
        result = actual >= expected
    else:
        raise ValueError(f"Operador no reconocido: {op}")
    return result.to_numpy(bool)


class ExactProblem:
    @classmethod
    def from_csv(cls, path, config, day):
        path = Path(path)
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
        return cls(raw, config, day, hashlib.sha256(path.read_bytes()).hexdigest())

    def __init__(self, raw, config, day, data_hash=None):
        self.config = config
        self.day = date.fromisoformat(day).isoformat()
        self.data_hash = data_hash or hashlib.sha256(raw.to_csv(index=False).encode()).hexdigest()
        self.config_hash = canonical_hash(config)
        campaigns = config["campanas"]
        params = config["parametros"]
        if params["optimizacion"]["objetivo"] != "valor_esperado" or params["priorizacion"]["modo"] != "ponderado":
            raise ValueError("El motor NBA admite únicamente valor_esperado en modo ponderado")
        if params["politica_contacto"]["canales_por_cliente"] != 1:
            raise ValueError("Se requiere un canal por cliente")
        maximum_week = params["politica_contacto"]["max_contactos_semana"]
        if type(maximum_week) is not int or maximum_week < 0:
            raise ValueError("Tope semanal debe ser entero no negativo")
        for threshold in (params["priorizacion"]["umbral_score_producto"], params["canal"]["umbral_score_canal"]):
            if not 0 <= number(threshold) <= 1:
                raise ValueError("Umbral fuera de [0,1]")
        self.ids = np.asarray(raw.id_cliente.astype(str).tolist(), dtype=str)
        self.n = len(self.ids)
        if not self.n or any(not value.strip() for value in self.ids) or len(set(self.ids)) != self.n:
            raise ValueError("Se requieren IDs únicos no vacíos y al menos un cliente")
        self.channels = list(params["canal"]["capacidad_por_corrida"])
        self.campaign_ids = [campaign["id"] for campaign in campaigns]
        self.products = [campaign["producto"] for campaign in campaigns]
        self.k, self.m = len(self.channels), len(campaigns)
        if not self.k or not self.m or len(set(self.campaign_ids)) != self.m:
            raise ValueError("Se requieren campañas únicas y canales")
        capacities = [params["canal"]["capacidad_por_corrida"][h] for h in self.channels]
        limits = [params["politica_contacto"]["max_productos_por_canal"][h] for h in self.channels]
        if any(type(c) is not int or not 0 <= c <= INT_LIMIT for c in capacities):
            raise ValueError("Capacidades enteras no negativas dentro del rango seguro")
        if any(type(c) is not int or not 0 <= c <= 2 for c in limits):
            raise ValueError("El contrato admite entre cero y dos productos")
        self.capacities = np.array(capacities, dtype=np.int64)
        self.limits = np.array(limits, dtype=np.int64)
        week = params["politica_contacto"].get("columna_contactos_semana", "contactos_semana_actual")
        rules = [rule for rule in config["reglas"] if rule["activa"]]
        score_columns = {c["columna_score"] for c in campaigns} | set(params["canal"]["columnas_score"].values())
        required = {"id_cliente", week} | score_columns
        for rule in rules:
            if rule["accion"] != "excluir" or rule["tipo"] not in ("canal", "elegibilidad"):
                raise ValueError("Solo se admiten reglas de exclusión de elegibilidad/canal")
            if rule["tipo"] == "elegibilidad" and rule["alcance"]["nivel"] == "canal":
                raise ValueError("Elegibilidad con alcance canal no es un contrato admitido")
            required |= condition_columns(rule["condicion"])
        if required - set(raw.columns):
            raise ValueError(f"Columnas ausentes: {sorted(required - set(raw.columns))}")
        frame = raw.copy()
        numeric = (NUMBER_COLUMNS | score_columns) & set(frame.columns)
        # Columnas nuevas se tipan igual que la lectura CSV del motor; sus
        # valores se convierten desde el texto original, nunca desde un float.
        for column in required - TEXT_COLUMNS - numeric:
            try:
                frame[column].map(number)
            except ValueError:
                continue
            numeric.add(column)
        for column in numeric:
            frame[column] = frame[column].map(number)
        for column in BINARY_COLUMNS & set(frame.columns):
            if not frame[column].isin([Decimal(0), Decimal(1)]).all():
                raise ValueError(f"Binaria inválida: {column}")
        if "calificacion_riesgo" in frame and not frame.calificacion_riesgo.isin(["E", "A", "B", "C", "P"]).all():
            raise ValueError("Calificación de riesgo fuera del dominio E/A/B/C/P")
        if any(not frame[c].map(lambda v: Decimal(0) <= v <= Decimal(1)).all() for c in score_columns):
            raise ValueError("Score fuera de [0,1]")
        if not frame[week].map(lambda v: v >= 0 and v == v.to_integral_value()).all():
            raise ValueError("Los contactos semanales deben ser enteros no negativos")
        values = [number(c["valor_negocio"]) for c in campaigns]
        if any(not 0 <= value <= 1 for value in values):
            raise ValueError("Valor de negocio fuera de [0,1]")
        product_digits = max(max(0, -value.as_tuple().exponent) for c in campaigns for value in frame[c["columna_score"]])
        channel_digits = max(max(0, -value.as_tuple().exponent) for h in self.channels for value in frame[params["canal"]["columnas_score"][h]])
        value_digits = max(max(0, -value.as_tuple().exponent) for value in values)
        if product_digits + channel_digits + value_digits > 15:
            raise OverflowError("Precisión decimal excesiva para los backends int64; no se redondea")
        ps, cs, vs = 10 ** product_digits, 10 ** channel_digits, 10 ** value_digits
        self.scale = ps * cs * vs
        if self.scale * 2 * (self.n + self.k + 3) > INT_LIMIT:
            raise OverflowError("Escala/rango de costes inseguro para el solver de flujo")
        self.product_cost = np.column_stack([np.fromiter((integer(v, ps) * integer(values[j], vs)
            for v in frame[c["columna_score"]]), dtype=np.int64, count=self.n) for j, c in enumerate(campaigns)])
        self.channel_cost = np.column_stack([np.fromiter((integer(v, cs) for v in frame[params["canal"]["columnas_score"][h]]),
            dtype=np.int64, count=self.n) for h in self.channels])
        product_allowed = np.zeros((self.n, self.m), dtype=bool)
        for j, campaign in enumerate(campaigns):
            if set(campaign["canales_permitidos"]) - set(self.channels):
                raise ValueError("La campaña usa un canal no configurado")
            start, end = (date.fromisoformat(campaign[key]).isoformat() for key in ("vigencia_inicio", "vigencia_fin"))
            if start > end:
                raise ValueError("La vigencia final precede a la inicial")
            active = campaign["activa"] and start <= self.day <= end
            mask = (frame[campaign["columna_score"]] >= number(params["priorizacion"]["umbral_score_producto"])).to_numpy(bool, copy=True)
            mask &= bool(active)
            for rule in rules:
                if rule["tipo"] == "elegibilidad" and scope_matches(rule, campaign):
                    mask &= ~condition_mask(frame, rule["condicion"], campaign)
            product_allowed[:, j] = mask
        self.allowed = np.zeros((self.n, self.k, self.m), dtype=bool)
        self.weights = np.zeros((self.n, self.k), dtype=np.int64)
        self.picks = np.full((self.n, self.k, 2), -1, dtype=np.int32)
        self.packages_examined = 0
        for h, channel in enumerate(self.channels):
            channel_ok = ((frame[week] + 1 <= number(params["politica_contacto"]["max_contactos_semana"])) &
                (frame[params["canal"]["columnas_score"][channel]] >= number(params["canal"]["umbral_score_canal"]))).to_numpy(bool)
            for j, campaign in enumerate(campaigns):
                mask = product_allowed[:, j] & channel_ok & (channel in campaign["canales_permitidos"])
                for rule in rules:
                    if rule["tipo"] == "canal" and scope_matches(rule, campaign, channel):
                        mask &= ~condition_mask(frame, rule["condicion"], campaign)
                self.allowed[:, h, j] = mask
            filled = np.zeros(self.n, dtype=np.int8)
            for size in range(1, int(self.limits[h]) + 1):
                for combination in itertools.combinations(range(self.m), size):
                    if len({self.products[j] for j in combination}) != size:
                        continue
                    valid = self.allowed[:, h, combination].all(axis=1)
                    self.packages_examined += int(valid.sum())
                    weight = self.product_cost[:, combination].sum(axis=1) * self.channel_cost[:, h]
                    better = valid & ((weight > self.weights[:, h]) | ((weight == self.weights[:, h]) & (size > filled)))
                    self.weights[better, h] = weight[better]
                    self.picks[better, h, :] = -1
                    for slot, j in enumerate(combination):
                        self.picks[better, h, slot] = j
                    filled[better] = size
            # Orden de presentación por aporte, sin alterar la elección óptima.
            both = self.picks[:, h, 1] >= 0
            rows = np.flatnonzero(both)
            swap = self.product_cost[rows, self.picks[rows, h, 1]] > self.product_cost[rows, self.picks[rows, h, 0]]
            rows = rows[swap]
            self.picks[rows, h] = self.picks[rows, h, ::-1]

    def grid(self, selected, description):
        records = []
        for i, h in enumerate(selected):
            if h < 0:
                reason = ("Ningún paquete compatible con reglas y umbrales tiene valor positivo" if not self.weights[i].any()
                          else "Cupos compatibles asignados a alternativas de mayor valor global")
                records.append((self.ids[i], "sin_accion", "", "", "", reason))
            else:
                picks = [self.campaign_ids[j] for j in self.picks[i, h] if j >= 0]
                records.append((self.ids[i], "asignado", self.channels[h], picks[0], picks[1] if len(picks) > 1 else "",
                    f"{description}; valor exacto {decimal_string(int(self.weights[i, h]), self.scale)}"))
        return pd.DataFrame(records, columns=OUTPUT)

    def evaluate_grid(self, grid):
        if list(grid.columns) != OUTPUT or len(grid) != self.n or grid.id_cliente.duplicated().any() or set(grid.id_cliente) != set(self.ids):
            raise ValueError("Parrilla inválida: formato, filas o identificadores")
        ids = {value: i for i, value in enumerate(self.ids)}
        channels = {value: h for h, value in enumerate(self.channels)}
        campaigns = {value: j for j, value in enumerate(self.campaign_ids)}
        selected = np.full(self.n, -1, dtype=np.int32)
        usage = np.zeros(self.k, dtype=np.int64)
        total = 0
        for row in grid.to_dict("records"):
            i = ids[row["id_cliente"]]
            picks = [row[key] for key in ("campana_1", "campana_2") if row[key]]
            if row["estado"] == "sin_accion":
                if row["canal"] or picks:
                    raise ValueError("sin_accion con productos o canal")
                continue
            if row["estado"] != "asignado" or row["canal"] not in channels or not picks:
                raise ValueError("Estado/canal/producto inválido")
            h = channels[row["canal"]]
            if len(picks) > self.limits[h] or any(value not in campaigns for value in picks):
                raise ValueError("Límite de productos o campaña desconocida")
            js = [campaigns[value] for value in picks]
            if len({self.products[j] for j in js}) != len(js) or not self.allowed[i, h, js].all():
                raise ValueError("Producto repetido o asignación no elegible")
            total += sum(int(self.product_cost[i, j]) for j in js) * int(self.channel_cost[i, h])
            selected[i] = h
            usage[h] += 1
        if np.any(usage > self.capacities):
            raise ValueError("Se supera la capacidad de un canal")
        return selected, total, usage

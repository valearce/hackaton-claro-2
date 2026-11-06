"""Motor NBA: asignación por flujo de coste mínimo y auditoría de reglas."""
from datetime import date
from pathlib import Path
import json
import operator
import time

import pandas as pd

from ..optimizacion.problema import ExactProblem
from ..optimizacion.solvers import solve_flow
from ..optimizacion.certificado import create_certificate
from ..rutas import MODELO

CONFIG = MODELO / "config"
OUTPUT_COLUMNS = ["id_cliente", "estado", "canal", "campana_1", "campana_2", "razon"]
OPS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
       "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def load_config(directory=CONFIG):
    directory = Path(directory)
    return {key: json.loads((directory / f"{key}.json").read_text(encoding="utf-8-sig"))
            for key in ("campanas", "reglas", "parametros")}


class Engine:
    """Un único backend: OR-Tools; cada salida exige certificado exacto."""

    def __init__(self, data, config, as_of=None, datos_sha256=None):
        started = time.perf_counter()
        self.day = date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or date.today())
        backend = config["parametros"]["optimizacion"].get("backend", "flujo_ortools")
        if backend != "flujo_ortools":
            raise ValueError("El único backend del motor NBA es flujo_ortools")
        self.problem = ExactProblem(data.reset_index(drop=True), config, self.day.isoformat(), datos_sha256)
        self.preparation_seconds = time.perf_counter() - started
        self.certificate = None

    def optimize(self):
        started = time.perf_counter()
        self.certificate = None
        grid, solver = solve_flow(self.problem)
        stamp = time.perf_counter()
        certificate, proof = create_certificate(self.problem, grid)
        self.certificate = certificate
        diagnostics = {**solver, "metodo": "optimo", "objetivo": "valor_esperado",
                       "preparar_modelo_seg": self.preparation_seconds,
                       "certificar_seg": time.perf_counter() - stamp,
                       "certificado": proof,
                       "segundos": self.preparation_seconds + time.perf_counter() - started}
        return grid, diagnostics


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
    numeric = data.copy()
    text_columns = {"id_cliente", "region", "tipo_linea", "calificacion_riesgo", "gama_equipo",
                    "canales_contactados_mes", "productos_ofertados_mes"}
    for column in numeric.columns:
        if column not in text_columns:
            try:
                numeric[column] = pd.to_numeric(numeric[column], errors="raise")
            except (ValueError, TypeError):
                pass
    numeric["id_cliente"] = numeric["id_cliente"].astype(str)
    source = numeric.set_index("id_cliente").to_dict("index")
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

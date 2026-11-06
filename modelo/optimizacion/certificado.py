"""Certificados primal-dual enteros, verificables sin solver ni Lean.

Para cualquier asignación: valor <= sum(u_i) + sum(cap_h * v_h), si
u_i >= 0, v_h >= 0 y u_i + v_h >= peso_ih. Igualdad acredita optimalidad.
"""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .problema import ExactProblem, INT_LIMIT, decimal_string
from ..rutas import DATOS, MODELO

CONFIG = MODELO / "config"


def create_certificate(problem, grid):
    selected, primal, usage = problem.evaluate_grid(grid)
    # Condiciones de holgura complementaria. Se agregan por pareja de canales:
    # v_h - v_g <= peso_ih - peso_ig para clientes asignados a h.
    # Solo quedan k+1 nodos, aunque existan 100000 clientes.
    root = problem.k
    edges = []
    unassigned = selected < 0
    for h in range(problem.k):
        edges.append((h, root, 0))  # v_h >= 0
        if usage[h] < problem.capacities[h]:
            edges.append((root, h, 0))  # capacidad con holgura => precio cero
        if unassigned.any():
            edges.append((h, root, -int(problem.weights[unassigned, h].max())))
        assigned = np.flatnonzero(selected == h)
        if len(assigned):
            own = problem.weights[assigned, h]
            edges.append((root, h, int(own.min())))  # u_i >= 0
            for g in range(problem.k):
                edges.append((g, h, int((own - problem.weights[assigned, g]).min())))
    # Bellman-Ford exacto con una superfuente implícita. Un ciclo negativo
    # contradice la optimalidad de la parrilla, no se oculta con tolerancias.
    distances = [0] * (problem.k + 1)
    for iteration in range(problem.k + 1):
        changed = False
        for a, b, cost in edges:
            candidate = distances[a] + cost
            if distances[b] > candidate:
                distances[b] = candidate
                changed = True
        if not changed:
            break
        if iteration == problem.k:
            raise ValueError("La parrilla no admite certificado de optimalidad: ciclo negativo exacto")
    prices = np.array([distances[h] - distances[root] for h in range(problem.k)], dtype=np.int64)
    customers = np.zeros(problem.n, dtype=np.int64)
    assigned = np.flatnonzero(selected >= 0)
    customers[assigned] = problem.weights[assigned, selected[assigned]] - prices[selected[assigned]]
    certificate = {"esquema": 1, "datos_sha256": problem.data_hash, "config_sha256": problem.config_hash,
                   "fecha": problem.day, "denominador": problem.scale,
                   "u_clientes": customers.tolist(), "v_canales": prices.tolist()}
    summary = verify_certificate(problem, grid, certificate)
    if not summary["optimo_exacto"]:
        raise ValueError("El paquete seleccionado no alcanza la cota exacta; no se certifica optimalidad")
    return certificate, summary


def verify_certificate(problem, grid, certificate):
    expected = {"esquema": 1, "datos_sha256": problem.data_hash, "config_sha256": problem.config_hash,
                "fecha": problem.day, "denominador": problem.scale}
    if any(certificate.get(key) != value for key, value in expected.items()):
        raise ValueError("El certificado no corresponde a los datos, configuración, fecha o escala")
    u, v = certificate.get("u_clientes"), certificate.get("v_canales")
    if not isinstance(u, list) or not isinstance(v, list) or len(u) != problem.n or len(v) != problem.k:
        raise ValueError("Dimensiones del certificado inválidas")
    if any(type(value) is not int or not 0 <= value <= INT_LIMIT for value in u + v):
        raise ValueError("Multiplicadores deben ser enteros no negativos en rango seguro")
    u, v = np.array(u, dtype=np.int64), np.array(v, dtype=np.int64)
    if np.any(u[:, None] + v[None, :] < problem.weights):
        raise ValueError("Certificado dual infactible: existe una alternativa que supera su cota")
    _, primal, usage = problem.evaluate_grid(grid)
    bound = sum(map(int, u)) + sum(int(c) * int(price) for c, price in zip(problem.capacities, v))
    gap = bound - primal
    if gap < 0:
        raise ValueError("La cota dual quedó por debajo del primal")
    return {"certificado_dual_valido": True, "optimo_exacto": gap == 0,
            "objetivo": problem.objective, "valor_objetivo_exacto": decimal_string(primal, problem.scale),
            "valor_esperado_exacto": problem.expected_value(grid),
            "valor_numerador": primal, "cota_numerador": bound, "brecha_numerador": gap,
            "denominador": problem.scale, "valor_exacto": decimal_string(primal, problem.scale),
            "cota_exacta": decimal_string(bound, problem.scale), "brecha_exacta": decimal_string(gap, problem.scale),
            "alternativas_verificadas": problem.n * problem.k,
            "paquetes_factibles_enumerados": problem.packages_examined,
            "uso_canales": dict(zip(problem.channels, map(int, usage))),
            "precios_canales_numerador": dict(zip(problem.channels, map(int, v))),
            "limite": "Verificación entera en Python del modelo configurado. No es una prueba comprobada por Lean."}


def save_certificate(path, certificate):
    raw = json.dumps(certificate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    Path(path).write_bytes(gzip.compress(raw, mtime=0))


def read_certificate(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--fecha", default="2026-11-05")
    parser.add_argument("--parrilla", type=Path, required=True)
    parser.add_argument("--certificado", type=Path, required=True)
    args = parser.parse_args()
    config = {key: json.loads((args.config / f"{key}.json").read_text(encoding="utf-8-sig"))
              for key in ("campanas", "reglas", "parametros")}
    problem = ExactProblem.from_csv(args.datos, config, args.fecha)
    grid = pd.read_csv(args.parrilla, dtype=str, keep_default_na=False)
    report = verify_certificate(problem, grid, read_certificate(args.certificado))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["optimo_exacto"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

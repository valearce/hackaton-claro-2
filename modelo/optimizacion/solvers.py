"""Único backend NBA: flujo de coste mínimo exacto con OR-Tools."""
import importlib
from pathlib import Path
import sys
import time

import numpy as np

from .problema import INT_LIMIT
from ..rutas import RAIZ

ORTOOLS_VERSION = "9.15.6755"
LOCAL_ORTOOLS = RAIZ / ".local/python/ortools-linux"


def load_flow_module():
    """Carga únicamente graph; no importa CP-SAT ni protobuf Python."""
    if sys.platform != "linux":
        raise RuntimeError("El backend de flujo instalado es Linux; usa el entorno WSL estándar")
    if not LOCAL_ORTOOLS.is_dir():
        raise RuntimeError("Falta el módulo local OR-Tools; consulta modelo/docs/optimizador.md")
    sys.path.insert(0, str(LOCAL_ORTOOLS))
    try:
        ortools = importlib.import_module("ortools")
        module = importlib.import_module("ortools.graph.python.min_cost_flow")
    finally:
        sys.path.remove(str(LOCAL_ORTOOLS))
    if ortools.__version__ != ORTOOLS_VERSION or not Path(ortools.__file__).resolve().is_relative_to(LOCAL_ORTOOLS):
        raise RuntimeError("El módulo OR-Tools no coincide con la versión/ubicación fijada")
    return module


def edges_and_divisor(problem):
    eligible = (problem.weights > 0) & (problem.capacities[None, :] > 0)
    customer, channel = np.nonzero(eligible)
    weights = problem.weights[customer, channel]
    divisor = int(np.gcd.reduce(weights)) if len(weights) else 1
    return customer, channel, weights, max(divisor, 1)


def solve_flow(problem):
    module = load_flow_module()
    started = time.perf_counter()
    customer, channel, weights, divisor = edges_and_divisor(problem)
    source, sink = problem.n + problem.k, problem.n + problem.k + 1
    if sink >= np.iinfo(np.int32).max:
        raise OverflowError("Demasiados nodos para el backend de flujo")
    costs = weights // divisor
    if len(costs) and (int(costs.max()) * (sink + 2) > INT_LIMIT or sum(map(int, problem.weights.max(axis=1))) > INT_LIMIT):
        raise OverflowError("Costes/objetivo fuera del rango seguro de int64")
    flow = module.SimpleMinCostFlow()
    rows = np.arange(problem.n, dtype=np.int32)
    # Un arco sin acción por cliente evita obligar a usar ofertas o canales.
    flow.add_arcs_with_capacity_and_unit_cost(np.full(problem.n, source, dtype=np.int32), rows,
                                             np.ones(problem.n, dtype=np.int64), np.zeros(problem.n, dtype=np.int64))
    decision_arcs = flow.add_arcs_with_capacity_and_unit_cost(customer.astype(np.int32), (problem.n + channel).astype(np.int32),
                                             np.ones(len(customer), dtype=np.int64), -costs)
    flow.add_arcs_with_capacity_and_unit_cost(rows, np.full(problem.n, sink, dtype=np.int32),
                                             np.ones(problem.n, dtype=np.int64), np.zeros(problem.n, dtype=np.int64))
    flow.add_arcs_with_capacity_and_unit_cost(np.arange(problem.n, problem.n + problem.k, dtype=np.int32),
                                             np.full(problem.k, sink, dtype=np.int32), problem.capacities,
                                             np.zeros(problem.k, dtype=np.int64))
    flow.set_nodes_supplies(np.array([source, sink], dtype=np.int32), np.array([problem.n, -problem.n], dtype=np.int64))
    setup_end = time.perf_counter()
    status = flow.solve()
    if status != flow.OPTIMAL:
        raise RuntimeError(f"Flujo no acreditó óptimo: {status}; no se reduce precisión para forzarlo")
    solved_end = time.perf_counter()
    chosen = flow.flows(decision_arcs) == 1
    selected = np.full(problem.n, -1, dtype=np.int32)
    selected[customer[chosen]] = channel[chosen]
    exact_cost = sum(map(int, weights[chosen]))
    if -int(flow.optimal_cost()) * divisor != exact_cost:
        raise RuntimeError("El objetivo del solver no coincide con la reconstrucción exacta")
    grid = problem.grid(selected, "Flujo de coste mínimo exacto")
    finished = time.perf_counter()
    diagnostics = {"backend": "flujo_ortools", "ortools": ORTOOLS_VERSION, "estado": "OPTIMAL", "nodos": sink + 1,
                   "arcos": flow.num_arcs(), "divisor_costes": divisor,
                   "preparar_backend_seg": setup_end-started, "resolver_seg": solved_end-setup_end,
                   "reconstruir_seg": finished-solved_end, "total_backend_seg": finished-started}
    return grid, diagnostics

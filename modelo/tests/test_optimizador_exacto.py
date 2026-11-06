from copy import deepcopy
from fractions import Fraction
import itertools
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from modelo.optimizacion.certificado import create_certificate, verify_certificate, save_certificate, read_certificate
from modelo.optimizacion.problema import ExactProblem, decimal_string
from modelo.nba import Engine, load_config, validate_grid
from modelo.optimizacion.solvers import solve_lp, solve_flow
from modelo.tests.test_modelo import clients, DAY


class ExactTests(unittest.TestCase):
    def test_lp_matches_exhaustive_product_and_channel_choices(self):
        data = clients(3)
        config = load_config()
        config["parametros"]["canal"]["capacidad_por_corrida"].update(asesor=1, whatsapp=1, correo=1, sms=0)
        data["score_terminales"] = [.93, .76, .55]
        data["score_venta_cruzada_hogar"] = [.62, .95, .48]
        data["score_upgrade_ott"] = [.85, .54, .91]
        data["score_canal_asesor"] = [.92, .87, .65]
        data["score_canal_whatsapp"] = [.86, .55, .78]
        data["score_canal_correo"] = [.51, .72, .67]
        problem = ExactProblem(data, config, DAY)
        # Oráculo pequeño: enumera todos los paquetes y asignaciones globales,
        # sin usar weights, masks o bundles del motor/certificador.
        options = []
        for row in data.to_dict("records"):
            choices = [(None, Fraction(0))]
            for channel, capacity in config["parametros"]["canal"]["capacidad_por_corrida"].items():
                if not capacity:
                    continue
                campaigns = [c for c in config["campanas"] if channel in c["canales_permitidos"]]
                limit = config["parametros"]["politica_contacto"]["max_productos_por_canal"][channel]
                for size in range(1, limit + 1):
                    for package in itertools.combinations(campaigns, size):
                        value = sum(Fraction(str(row[c["columna_score"]])) * Fraction(str(c["valor_negocio"])) for c in package)
                        choices.append((channel, value * Fraction(str(row[f"score_canal_{channel}"]))))
            options.append(choices)
        best = Fraction(0)
        for assignment in itertools.product(*options):
            if any(sum(choice[0] == h for choice in assignment) > capacity for h, capacity in
                   config["parametros"]["canal"]["capacidad_por_corrida"].items()):
                continue
            best = max(best, sum(choice[1] for choice in assignment))
        grid, _ = solve_lp(problem)
        _, summary = create_certificate(problem, grid)
        self.assertEqual(Fraction(summary["valor_numerador"], problem.scale), best)
        self.assertTrue(summary["optimo_exacto"])
        self.assertEqual(validate_grid(data, grid, config, DAY)["violaciones"], 0)

    def test_decimal_value_is_exact_and_certificate_survives_reload(self):
        data = clients(1)
        config = load_config()
        for c in config["campanas"]:
            c["activa"] = c["producto"] == "TER"
        config["parametros"]["canal"]["capacidad_por_corrida"].update(asesor=1, whatsapp=0, correo=0, sms=0)
        data["score_terminales"], data["score_canal_asesor"] = .3501, .4392
        problem = ExactProblem(data, config, DAY)
        grid, _ = solve_lp(problem)
        certificate, summary = create_certificate(problem, grid)
        self.assertEqual(summary["valor_exacto"], "0.123011136")
        self.assertEqual(summary["brecha_numerador"], 0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            problem.save(path / "modelo.npz")
            restored = ExactProblem.load(path / "modelo.npz")
            save_certificate(path / "certificado.json.gz", certificate)
            self.assertEqual(verify_certificate(restored, grid, read_certificate(path / "certificado.json.gz")), summary)

    def test_checker_rejects_tampering_and_reports_nonzero_valid_bound(self):
        problem = ExactProblem(clients(2), load_config(), DAY)
        grid, _ = solve_lp(problem)
        certificate, _ = create_certificate(problem, grid)
        for key, replacement in (("datos_sha256", "otro"), ("config_sha256", "otro"), ("denominador", problem.scale * 10)):
            changed = deepcopy(certificate)
            changed[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_certificate(problem, grid, changed)
        changed = deepcopy(certificate)
        changed["u_clientes"] = [0] * problem.n
        changed["v_canales"] = [0] * problem.k
        with self.assertRaises(ValueError):
            verify_certificate(problem, grid, changed)
        changed = deepcopy(certificate)
        changed["u_clientes"][0] += 1
        report = verify_certificate(problem, grid, changed)
        self.assertTrue(report["certificado_dual_valido"])
        self.assertFalse(report["optimo_exacto"])
        self.assertEqual(report["brecha_numerador"], 1)
        invalid = grid.copy()
        invalid.loc[0, "campana_1"] = "INEXISTENTE"
        with self.assertRaises(ValueError):
            verify_certificate(problem, invalid, certificate)

    def test_greedy_cannot_receive_an_optimality_certificate(self):
        data = clients(2)
        config = load_config()
        for campaign in config["campanas"]:
            campaign["activa"] = campaign["producto"] == "TER"
        config["parametros"]["canal"]["capacidad_por_corrida"].update(asesor=1, whatsapp=1, correo=0, sms=0)
        data["score_terminales"] = [.95, .94]
        data["score_canal_asesor"] = [.9, .8]
        data["score_canal_whatsapp"] = [.89, .26]
        grid, _ = Engine(data, config, DAY).baseline()
        with self.assertRaises(ValueError):
            create_certificate(ExactProblem(data, config, DAY), grid)

    def test_independent_rules_cover_history_scopes_new_columns_and_boundaries(self):
        data = clients(4)
        config = load_config()
        data["grupo_nuevo"] = ["A", "B", "C", "A"]
        data["productos_ofertados_mes"] = ["TER|OTT", "", "VCH", "TERMINALES"]
        data["edad_equipo_meses"] = [18, 17, 30, 19]
        data["contactos_semana_actual"] = [2, 0, 3, 0]
        data["score_upgrade_ott"] = [.35, .3499, .8, .9]
        config["reglas"].append({"id":"EXTRA", "nombre":"Prueba", "tipo":"canal", "activa":True, "accion":"excluir",
            "alcance":{"nivel":"canal","valores":["correo"]}, "condicion":{"alguna":[
            {"atributo":"grupo_nuevo","operador":"en","valor":["B","C"]},
            {"todas":[{"atributo":"edad_equipo_meses","operador":"<","valor":18},
                      {"atributo":"en_mora","operador":"==","valor":0}]}]}})
        problem = ExactProblem(data, config, DAY)
        engine = Engine(data, config, DAY)
        for h, expected in enumerate(engine.feasible):
            np.testing.assert_array_equal(problem.allowed[:, h], expected)
        np.testing.assert_array_equal(problem.weights, np.rint(np.column_stack([b.expected for b in
            engine.bundles("valor_esperado")]) * problem.scale).astype(np.int64))

    def test_invalid_domains_and_excessive_precision_are_rejected(self):
        for column, value in (("en_mora", 2), ("calificacion_riesgo", "DESCONOCIDO"), ("score_terminales", "NaN")):
            data = clients(1)
            data[column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                ExactProblem(data, load_config(), DAY)
        data = clients(1)
        data["score_terminales"] = "0.80000000000000000000000000001"
        with self.assertRaises(OverflowError):
            ExactProblem(data, load_config(), DAY)


@unittest.skipUnless(os.environ.get("NBA_REQUIRE_CUDA") == "1", "El backend local de flujo se valida en WSL estándar")
class FlowTests(unittest.TestCase):
    def test_flow_matches_lp_including_empty_and_scarce_capacity(self):
        data = clients(4)
        data["score_canal_asesor"] = [.99, .89, .67, .52]
        data["score_canal_whatsapp"] = [.71, .62, .88, .82]
        for capacities in (dict(asesor=1, whatsapp=2, correo=0, sms=0), dict(asesor=0, whatsapp=0, correo=0, sms=0)):
            config = load_config()
            config["parametros"]["canal"]["capacidad_por_corrida"].update(capacities)
            problem = ExactProblem(data, config, DAY)
            lp, _ = solve_lp(problem)
            flow, _ = solve_flow(problem)
            _, first = create_certificate(problem, lp)
            _, second = create_certificate(problem, flow)
            self.assertEqual(first["valor_numerador"], second["valor_numerador"])
            self.assertEqual(validate_grid(data, flow, config, DAY)["violaciones"], 0)

    def test_exact_small_difference_is_not_lost_by_float_tolerance(self):
        data = clients(2)
        config = load_config()
        for c in config["campanas"]:
            c["activa"] = c["producto"] == "TER"
        config["parametros"]["canal"]["capacidad_por_corrida"].update(asesor=1, whatsapp=1, correo=0, sms=0)
        data["score_terminales"] = [.9999, 1.]
        data["score_canal_asesor"] = [.8001, .8001]
        data["score_canal_whatsapp"] = [.8, .8]
        problem = ExactProblem(data, config, DAY)
        lp, _ = solve_lp(problem)
        flow, _ = solve_flow(problem)
        for grid in (lp, flow):
            self.assertEqual(grid.canal.tolist(), ["whatsapp", "asesor"])
            self.assertTrue(create_certificate(problem, grid)[1]["optimo_exacto"])

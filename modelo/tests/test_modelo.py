from copy import deepcopy
import itertools
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from modelo.nba import Engine, load_config, validate_grid
from modelo.perfiles import Preprocessor

DAY = "2026-11-05"
MODEL = Path(__file__).resolve().parents[1]


def clients(n=4):
    source = pd.read_csv(MODEL / "kit_original/casos_ejemplo_clientes.csv", keep_default_na=False)
    data = pd.concat([source.iloc[[0]]] * n, ignore_index=True)
    data["id_cliente"] = [f"T{i:03d}" for i in range(n)]
    for column in ["en_mora", "quejas_90d", "contactos_semana_actual", "contactos_asesor_mes", "tiene_hogar", "cantidad_ott"]:
        data[column] = 0
    data["edad_equipo_meses"], data["calificacion_riesgo"] = 30, "E"
    data["productos_ofertados_mes"] = ""
    for column in ["autoriza_sms", "autoriza_correo", "autoriza_whatsapp"]:
        data[column] = 1
    for column in [c for c in data if c.startswith("score_")]:
        data[column] = 0.8
    return data


class NBATests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_optimizer_beats_greedy_on_scarce_channel(self):
        data = clients(2)
        for campaign in self.config["campanas"]:
            campaign["activa"] = campaign["producto"] == "TER"
        caps = self.config["parametros"]["canal"]["capacidad_por_corrida"]
        caps.update(asesor=1, whatsapp=1, correo=0, sms=0)
        data["score_terminales"] = [0.95, 0.94]
        data["score_canal_asesor"] = [0.9, 0.8]
        data["score_canal_whatsapp"] = [0.89, 0.26]
        engine = Engine(data, self.config, DAY)
        baseline, _ = engine.baseline()
        optimum, _ = engine.optimize()
        first = validate_grid(data, baseline, self.config, DAY)
        second = validate_grid(data, optimum, self.config, DAY)
        self.assertEqual(second["violaciones"], 0)
        self.assertGreater(second["valor_esperado"], first["valor_esperado"])
        self.assertEqual(optimum.canal.tolist(), ["whatsapp", "asesor"])

    def test_optimizer_matches_exhaustive_small_assignment(self):
        data = clients(4)
        data["score_canal_asesor"] = [0.9, 0.7, 0.8, 0.6]
        data["score_canal_whatsapp"] = [0.8, 0.8, 0.3, 0.4]
        self.config["parametros"]["canal"]["capacidad_por_corrida"].update(asesor=1, whatsapp=2, correo=0, sms=0)
        engine = Engine(data, self.config, DAY)
        bundles = engine.bundles("valor_esperado")
        best = 0
        for choice in itertools.product((-1, 0, 1), repeat=4):
            if choice.count(0) > 1 or choice.count(1) > 2:
                continue
            best = max(best, sum(bundles[h].expected[row] for row, h in enumerate(choice) if h >= 0))
        grid, _ = engine.optimize()
        audited = validate_grid(data, grid, self.config, DAY)
        self.assertEqual(audited["violaciones"], 0)
        self.assertAlmostEqual(best, audited["valor_esperado"], places=9)

    def test_boundaries_of_scores_age_calls_and_week(self):
        data = clients(4)
        data["score_terminales"] = [0.35, 0.3499, 0.8, 0.8]
        data["edad_equipo_meses"] = [18, 18, 17, 30]
        data["contactos_semana_actual"] = [2, 0, 0, 3]
        for campaign in self.config["campanas"]:
            campaign["activa"] = campaign["producto"] == "TER"
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertEqual(grid.estado.tolist(), ["asignado", "sin_accion", "sin_accion", "sin_accion"])
        self.assertEqual(validate_grid(data, grid, self.config, DAY)["violaciones"], 0)

    def test_history_uses_exact_product_tokens(self):
        data = clients(2)
        data["productos_ofertados_mes"] = ["TER|OTT|VCH", "TERMINALES"]
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertEqual(grid.estado.tolist(), ["sin_accion", "asignado"])

    def test_new_rule_new_column_and_deactivation(self):
        data = clients(2)
        data["grupo_nuevo"] = ["excluir", "contactar"]
        rule = {"id": "NUEVA", "nombre": "Público experimental", "tipo": "elegibilidad", "alcance": {"nivel": "global"},
                "condicion": {"atributo": "grupo_nuevo", "operador": "==", "valor": "excluir"}, "accion": "excluir", "activa": True}
        self.config["reglas"].append(rule)
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertEqual(grid.estado.tolist(), ["sin_accion", "asignado"])
        rule["activa"] = False
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertTrue(grid.estado.eq("asignado").all())

    def test_new_campaign_and_new_channel(self):
        data = clients(2)
        data["score_nuevo"], data["score_canal_nuevo"] = 0.99, 0.99
        for campaign in self.config["campanas"]:
            campaign["canales_permitidos"].append("nuevo")
        self.config["campanas"].append({"id": "C-NUEVA", "nombre": "Campaña nueva", "producto": "NUEVO", "objetivo": "Piloto", "columna_score": "score_nuevo", "valor_negocio": 1,
                                         "canales_permitidos": ["nuevo"], "vigencia_inicio": DAY, "vigencia_fin": DAY, "activa": True})
        params = self.config["parametros"]
        params["canal"]["capacidad_por_corrida"]["nuevo"] = 1
        params["canal"]["columnas_score"]["nuevo"] = "score_canal_nuevo"
        params["politica_contacto"]["max_productos_por_canal"]["nuevo"] = 2
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertEqual(grid.canal.eq("nuevo").sum(), 1)
        self.assertEqual(validate_grid(data, grid, self.config, DAY)["violaciones"], 0)

    def test_paused_and_expired_campaigns(self):
        data = clients(2)
        for campaign in self.config["campanas"]:
            campaign["activa"] = False
        grid, _ = Engine(data, self.config, DAY).optimize()
        self.assertTrue(grid.estado.eq("sin_accion").all())
        for campaign in self.config["campanas"]:
            campaign["activa"] = True
        grid, _ = Engine(data, self.config, "2027-01-01").optimize()
        self.assertTrue(grid.estado.eq("sin_accion").all())

    def test_invalid_input_is_not_silently_contacted(self):
        for column, value in [("score_terminales", np.nan), ("en_mora", np.nan), ("contactos_semana_actual", -1)]:
            with self.subTest(column=column):
                data = clients(2)
                data[column] = data[column].astype(float)
                data.loc[0, column] = value
                with self.assertRaises(ValueError):
                    Engine(data, self.config, DAY)
        data = clients(2)
        data.loc[1, "id_cliente"] = data.loc[0, "id_cliente"]
        with self.assertRaises(ValueError):
            Engine(data, self.config, DAY)

    def test_auditor_detects_tampered_assignment(self):
        data = clients(1)
        data["en_mora"], data["edad_equipo_meses"], data["calificacion_riesgo"] = 1, 1, "P"
        data["quejas_90d"], data["contactos_semana_actual"], data["contactos_asesor_mes"] = 3, 3, 2
        data["productos_ofertados_mes"] = "TER"
        data["score_terminales"], data["score_canal_asesor"] = 0.1, 0.1
        grid = pd.DataFrame([["T000", "asignado", "asesor", "C-TER", "C-OTT", "Manipulada"]],
                            columns=["id_cliente", "estado", "canal", "campana_1", "campana_2", "razon"])
        audit = validate_grid(data, grid, self.config, DAY)
        for control in ("R01", "R02", "R03", "R06", "R07", "R08", "R10", "R11", "R12", "R14", "R15"):
            self.assertGreater(audit["controles"][control], 0, control)


class ProfileTests(unittest.TestCase):
    def test_preprocessing_does_not_fit_heldout_or_treat_unlimited_as_999_gb(self):
        import json
        config = json.loads((MODEL / "config/perfiles.json").read_text(encoding="utf-8"))
        data = clients(4)
        data["plan_datos_gb"] = [2, 10, 999, 50]
        preprocessor = Preprocessor(config).fit(data.iloc[:3])
        self.assertEqual(preprocessor.medians["plan_datos_gb"], 6)
        before = preprocessor.to_dict()
        heldout = data.iloc[[3]].copy()
        heldout["arpu_movil"] = 9999999
        heldout["gama_equipo"] = "Nueva categoría"
        transformed = preprocessor.transform(heldout)
        self.assertEqual(preprocessor.to_dict(), before)
        self.assertTrue(np.isfinite(transformed).all())
        restored = Preprocessor.from_dict(before)
        np.testing.assert_allclose(restored.transform(data), preprocessor.transform(data))
        self.assertNotIn("id_cliente", preprocessor.features)
        self.assertFalse(any(name.startswith("score_") for name in preprocessor.features))


if __name__ == "__main__":
    unittest.main()

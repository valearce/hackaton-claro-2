"""Prueba integral pequeña: artefactos, particiones y selección sin usar test."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from modelo.comparar import load_reference, run_comparison
from modelo.perfiles import run_profiles
from modelo.tests.test_modelo import MODEL, clients


class ComparisonTests(unittest.TestCase):
    def test_end_to_end_uses_same_holdout_and_rejects_changed_artifacts(self):
        rng = np.random.default_rng(31)
        data = clients(240)
        profile_config = json.loads((MODEL / "config/perfiles.json").read_text(encoding="utf-8"))
        for column in profile_config["numericas"]:
            data[column] = rng.uniform(1, 100, len(data))
        for column in profile_config["binarias"]:
            data[column] = rng.integers(0, 2, len(data))
        data["tipo_linea"] = rng.choice(["Prepago", "Postpago"], len(data))
        data["gama_equipo"] = rng.choice(["Alta", "Media", "Baja"], len(data))
        profile_config.update(epocas=2, segmentos=3, muestra_silhouette=30)
        comparison_config = json.loads((MODEL / "config/comparacion.json").read_text(encoding="utf-8"))
        comparison_config.update(segmentos=3, muestra_calidad=30, muestra_vecinos=30,
                                 vecinos_calidad=5, bootstrap_repeticiones=20)
        comparison_config["gmm"].update(covarianzas=["diag"], n_init=1)
        comparison_config["isomap"].update(puntos_entrenamiento=100, vecinos=[15], vecinos_decoder=[3, 5])
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
            directory = Path(temporary)
            source = directory / "clientes.csv"
            data.to_csv(source, index=False)
            fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
            run_profiles(data, profile_config, directory / "perfiles", fingerprint)
            original_preprocessing = (directory / "perfiles/preprocesamiento.json").read_bytes()
            report = run_comparison(data, comparison_config, directory / "perfiles", directory / "comparacion", source)
            self.assertEqual(report["datos_sha256"], fingerprint)
            self.assertEqual(sum(report["particiones"].values()), len(data))
            self.assertEqual(len(report["resultados"]), 4)
            self.assertEqual((directory / "perfiles/preprocesamiento.json").read_bytes(), original_preprocessing)
            profiles = pd.read_csv(directory / "perfiles/perfiles_clientes.csv")
            errors = pd.read_csv(directory / "comparacion/errores_test.csv")
            self.assertEqual(errors.id_cliente.tolist(), profiles.loc[profiles.particion.eq("test"), "id_cliente"].tolist())
            for number, result in enumerate(report["resultados"], start=1):
                self.assertAlmostEqual(errors[f"mse_{number}"].mean(), result["mse_test"], places=10)
                self.assertTrue(np.isfinite(result["trustworthiness_test"]))
            isomap = report["resultados"][-1]
            self.assertEqual(isomap["mse_validacion"], min(v["mse_validacion"] for v in report["seleccion_solo_validacion"]["isomap"]))
            changed = data.copy()
            heldout_index = profiles.index[profiles.particion.eq("test")][0]
            changed.loc[heldout_index, "edad"] += 50
            with self.assertRaises(ValueError):
                load_reference(changed, directory / "perfiles")


if __name__ == "__main__":
    unittest.main()

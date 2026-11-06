from copy import deepcopy
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from modelo.experimentos import bandido as B, propuestas, simulador as sim, viabilidad as via
from modelo.experimentos.comportamiento import sondeo
from modelo.experimentos.exportar_app import publicidad_por_cluster
from modelo.experimentos.sectores import (UMBRAL_EFECTO, config_perfil, construir_sectores, describir, filtrar_region,
                                          indices_region)
from modelo.nba import Engine, load_config

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = json.loads((RAIZ / "modelo/experimentos/config.json").read_text(encoding="utf-8-sig"))
PERFILES = json.loads((RAIZ / "modelo/config/perfiles.json").read_text(encoding="utf-8-sig"))
CONFIG["sectores"]["min_clientes"] = 60  # la muestra de prueba es más pequeña que Bogotá completa
CONFIG["experimento"].update({"oleadas": 12, "muestras_probabilidad": 300})
NBA = load_config()


def setUpModule():
    global DATOS, REGION, TABLA, SECTOR, Z, PARRILLA, CONTACTOS, MOTOR, IDX
    DATOS = pd.read_csv(RAIZ / "datos/clientes.csv", nrows=14000, keep_default_na=False)
    REGION = filtrar_region(DATOS, "Bogota")
    IDX = indices_region(DATOS, "Bogota")
    TABLA, SECTOR, Z = construir_sectores(REGION, config_perfil(CONFIG, PERFILES), CONFIG["sectores"], CONFIG["semilla"])
    MOTOR = Engine(DATOS, NBA, CONFIG["fecha"])
    PARRILLA, _ = MOTOR.optimize()
    CONTACTOS = sim.contactos_de_parrilla(REGION, PARRILLA, NBA, SECTOR, len(TABLA))


class SectoresTest(unittest.TestCase):
    def test_todos_los_clientes_quedan_en_un_sector_y_los_sectores_no_son_diminutos(self):
        self.assertEqual(len(SECTOR), len(REGION))
        self.assertTrue(((SECTOR >= 0) & (SECTOR < len(TABLA))).all())
        self.assertEqual(int(TABLA["clientes"].sum()), len(REGION))
        propios = TABLA[~TABLA["sector"].str.endswith("otros")]
        self.assertTrue((propios["clientes"] >= CONFIG["sectores"]["min_clientes"]).all())

    def test_el_sector_hereda_el_estrato_del_mapa(self):
        estratos = REGION["estrato"].astype(int).to_numpy()
        for i, fila in TABLA.iterrows():
            self.assertTrue((estratos[SECTOR == i] == fila["estrato"]).all())

    def test_es_determinista(self):
        otra, indice, _ = construir_sectores(REGION, config_perfil(CONFIG, PERFILES), CONFIG["sectores"], CONFIG["semilla"])
        self.assertTrue((indice == SECTOR).all())
        self.assertEqual(list(otra["sector"]), list(TABLA["sector"]))

    def test_los_nombres_no_describen_diferencias_que_no_existen(self):
        sin_diferencias = pd.Series({"postpago": 0.05, "hogar": -0.1, "arpu": 0.02, "edad": 0.3})
        self.assertEqual(describir(sin_diferencias), "Perfil promedio")
        marcada = pd.Series({"postpago": -1.4, "hogar": 0.1, "edad": 0.2})
        self.assertIn("repago", describir(marcada))
        self.assertLess(0.3, UMBRAL_EFECTO + 1e-9)


class ViabilidadTest(unittest.TestCase):
    def test_los_indices_de_region_apuntan_a_los_mismos_clientes(self):
        self.assertTrue((DATOS.iloc[IDX]["id_cliente"].to_numpy() == REGION["id_cliente"].to_numpy()).all())

    def test_el_embudo_coincide_con_la_elegibilidad_del_motor(self):
        e = via.escenario(MOTOR, PARRILLA, IDX, SECTOR, TABLA, CONTACTOS, "base", "Reglas actuales")
        for j, camp in enumerate(NBA["campanas"]):
            suma = sum(c["elegibles"] for c in e["celdas"] if c["campana"] == camp["id"])
            self.assertEqual(suma, int(MOTOR.product_ok[IDX, j].sum()), camp["id"])
        for c in e["celdas"]:
            self.assertLessEqual(c["viables"], c["elegibles"])
            self.assertLessEqual(c["contactos"], c["viables"])
            self.assertEqual(c["bloqueada"], c["clientes"] > 0 and c["viables"] == 0)

    def test_el_embudo_cuenta_exactamente_a_quienes_la_regla_deja_fuera(self):
        e = via.escenario(MOTOR, PARRILLA, IDX, SECTOR, TABLA, CONTACTOS, "base", "Reglas actuales")
        con_hogar = REGION["tiene_hogar"].astype(int).to_numpy()
        nombres = TABLA["sector"].tolist()
        for c in e["celdas"]:
            if c["campana"] != "C-VCH":
                continue
            esperados = int(con_hogar[SECTOR == nombres.index(c["sector"])].sum())
            paso = [p for p in c["pasos"] if "Hogar" in p["nombre"]]
            self.assertEqual(paso[0]["solo"] if paso else 0, esperados, c["sector"])

    def test_una_restriccion_nueva_bloquea_su_celda_y_no_aumenta_el_valor(self):
        regla = {"id": "H1", "control": "H1", "nombre": "No ofrecer streaming a estrato 1", "tipo": "elegibilidad",
                 "alcance": {"nivel": "campana", "valores": ["C-OTT"]},
                 "condicion": {"atributo": "estrato", "operador": "==", "valor": 1}, "accion": "excluir", "activa": True}
        base = via.escenario(MOTOR, PARRILLA, IDX, SECTOR, TABLA, CONTACTOS, "base", "Reglas actuales")
        motor, parrilla, cfg = via.correr_escenario(DATOS, NBA, regla, CONFIG["fecha"])
        contactos = sim.contactos_de_parrilla(REGION, parrilla, cfg, SECTOR, len(TABLA))
        nuevo = via.escenario(motor, parrilla, IDX, SECTOR, TABLA, contactos, "H1", "H1", regla)
        e1 = TABLA.set_index("sector")["estrato"]
        for c in nuevo["celdas"]:
            if c["campana"] == "C-OTT" and e1[c["sector"]] == 1:
                self.assertEqual(c["contactos"], 0)
                self.assertTrue(c["bloqueada"])
                self.assertIn("estrato 1", c["bloqueo"])
        self.assertLessEqual(nuevo["valor_total"], base["valor_total"] + 1e-6)
        self.assertEqual(nuevo["regla"]["condicion"], "estrato es 1")

    def test_la_condicion_de_una_regla_se_lee_en_palabras(self):
        self.assertEqual(via.texto_condicion({"atributo": "calificacion_riesgo", "operador": "en", "valor": ["C", "P"]}),
                         "calificacion_riesgo está entre C, P")
        self.assertEqual(via.texto_condicion({"todas": [{"atributo": "a", "operador": "==", "valor": 1},
                                                        {"atributo": "b", "operador": ">=", "valor": 2}]}), "a es 1 y b es al menos 2")


class ComportamientoTest(unittest.TestCase):
    def test_el_sondeo_distingue_lo_que_cambia_con_el_estrato_y_no_lo_plano(self):
        r = sondeo(REGION)
        distinguen = {v["id"] for v in r["variables"] if v["distingue"]}
        self.assertTrue({"hogar", "netflix", "banca"} <= distinguen)
        self.assertFalse({"edad", "consumo", "quejas", "mora"} & distinguen)

    def test_las_medias_por_estrato_son_las_de_los_datos(self):
        v = next(x for x in sondeo(REGION)["variables"] if x["id"] == "hogar")
        for estrato, media in v["valores"].items():
            esperado = 100 * REGION.loc[REGION["estrato"].astype(int) == int(estrato), "tiene_hogar"].astype(float).mean()
            self.assertAlmostEqual(media, esperado, places=9)

    def test_los_clusters_de_comportamiento_no_usan_contrato_ni_gama(self):
        c = config_perfil(CONFIG, PERFILES)
        usadas = set(c["numericas"]) | set(c["binarias"]) | set(c["categoricas"])
        self.assertFalse({"tipo_linea", "gama_equipo", "arpu_movil", "arpu_hogar", "estrato"} & usadas)
        self.assertIn("usa_banca_digital", usadas)
        contrato = {**CONFIG, "sectores": {**CONFIG["sectores"], "perfil": "contrato"}}
        self.assertIs(config_perfil(contrato, PERFILES), PERFILES)


class ExportarAppTest(unittest.TestCase):
    def test_la_publicidad_por_cluster_reparte_nombra_la_principal_y_suma_los_contactos(self):
        _, primera = sim.evaluar(CONTACTOS, Z, CONFIG, 1)
        recs = sim.recomendaciones(CONTACTOS, TABLA, CONFIG, primera, NBA["campanas"], muestras=500)
        pub = publicidad_por_cluster(recs, CONFIG, TABLA, {c["id"]: c for c in NBA["campanas"]}, {})
        self.assertTrue(pub)
        for p in pub:
            self.assertAlmostEqual(sum(p["reparto"].values()), 1.0, places=2)
            self.assertIn(p["principal"], CONFIG["variantes"])
            self.assertEqual(p["principal"], max(p["reparto"], key=p["reparto"].get))
            self.assertTrue(p["texto"])
            self.assertEqual(p["contactos"], sum(x["contactos"] for x in p["por_estrato"]))
        self.assertFalse(any("otros" in str(x) for x in pub))


class PropuestasTest(unittest.TestCase):
    def test_texto_para_campana_con_plantilla_propia_y_para_una_nueva(self):
        propia = propuestas.redactar(CONFIG, {"id": "C-VCH", "nombre": "Venta cruzada Hogar"}, "ahorro", {"postpago": -1.4})
        self.assertIn("prepago", propia)
        nueva = propuestas.redactar(CONFIG, {"id": "C-NUEVA", "nombre": "Seguro de equipo"}, "familia", {})
        self.assertIn("Seguro de equipo", nueva)
        self.assertTrue(nueva[0].isupper())

    def test_el_gancho_cambia_con_el_sector(self):
        c = {"id": "C-TER", "nombre": "Renovacion"}
        a = propuestas.redactar(CONFIG, c, "novedad", {"hogar": 1.3})
        b = propuestas.redactar(CONFIG, c, "novedad", {"hogar": -1.3})
        self.assertNotEqual(a, b)

    def test_el_sms_respeta_el_limite(self):
        largo = deepcopy(CONFIG)
        largo["plantillas"]["C-TER"]["ahorro"] = "{gancho} " + "renueva tu celular " * 20
        self.assertLessEqual(len(propuestas.redactar(largo, {"id": "C-TER", "nombre": "x"}, "ahorro", {}, "sms")), propuestas.LIMITE_SMS)


class BandidoTest(unittest.TestCase):
    def test_prob_mejor_suma_uno_y_favorece_a_la_ganadora(self):
        forma = np.array([[10.0, 10.0, 60.0]])
        tasa = np.array([[10.0, 10.0, 10.0]])
        p = B.prob_mejor(forma, tasa, 2000, np.random.default_rng(0))
        self.assertAlmostEqual(float(p.sum()), 1.0)
        self.assertGreater(p[0, 2], 0.95)

    def test_el_reparto_nunca_abandona_una_propuesta(self):
        c = {"sector": np.zeros(50, int), "campana": np.zeros(50, int), "p0": np.full(50, 0.2), "n_sectores": 1, "n_campanas": 1}
        pol = B.BandidoSector(c, 4, CONFIG["experimento"])
        pol.compras[0] = [50, 0, 0, 0]
        pol.esperadas[0] = [10, 10, 10, 10]
        self.assertTrue((pol.probabilidades(np.random.default_rng(0)) >= CONFIG["experimento"]["piso_exploracion"] - 1e-12).all())


class SimuladorTest(unittest.TestCase):
    def test_los_contactos_salen_de_la_parrilla(self):
        g = PARRILLA.set_index("id_cliente").loc[REGION["id_cliente"].astype(str)]
        esperado = int(((g["estado"] == "asignado") & (g["campana_1"] != "")).sum() + ((g["estado"] == "asignado") & (g["campana_2"] != "")).sum())
        self.assertEqual(len(CONTACTOS["p0"]), esperado)
        self.assertTrue(((CONTACTOS["p0"] >= 0) & (CONTACTOS["p0"] <= 1)).all())

    def test_sin_efectos_todas_las_politicas_valen_lo_mismo(self):
        lift = np.ones((len(TABLA), CONTACTOS["n_campanas"], len(CONFIG["variantes"])))
        res, _ = sim.simular(CONTACTOS, lift, CONFIG, 1)
        valores = {p: res[p]["valor"] for p in sim.POLITICAS}
        for v in valores.values():
            self.assertAlmostEqual(v, valores["uniforme"], places=6)

    def test_el_oraculo_es_el_techo(self):
        lift = sim.lift_verdad(Z, CONFIG, CONTACTOS["n_campanas"], np.random.default_rng(3))
        res, _ = sim.simular(CONTACTOS, lift, CONFIG, 3)
        for p in sim.POLITICAS:
            self.assertLessEqual(res[p]["valor"], res["oraculo"]["valor"] + 1e-9)

    def test_el_bandido_por_sector_supera_al_reparto_uniforme_con_diferencias_fuertes(self):
        resumen, _ = sim.evaluar(CONTACTOS, Z, CONFIG, 6, {"amplitud_sector": 0.5, "ruido_sector": 0.05})
        self.assertGreater(resumen["politicas"]["bandido_sector"]["mejora_pct_media"], 0)

    def test_misma_semilla_mismo_resultado(self):
        a, _ = sim.evaluar(CONTACTOS, Z, CONFIG, 2)
        b, _ = sim.evaluar(CONTACTOS, Z, CONFIG, 2)
        self.assertEqual(a["politicas"], b["politicas"])

    def test_las_recomendaciones_traen_probabilidades_texto_e_intervalo(self):
        _, primera = sim.evaluar(CONTACTOS, Z, CONFIG, 1)
        recs = sim.recomendaciones(CONTACTOS, TABLA, CONFIG, primera, NBA["campanas"], muestras=500)
        self.assertTrue(recs)
        for r in recs:
            self.assertAlmostEqual(r["p_mejor"] + sum(a["p_mejor"] for a in r["alternativas"]), 1.0, places=6)
            self.assertTrue(r["texto"])
            self.assertLess(r["lift_ic90_pct"][0], r["lift_ic90_pct"][1])


if __name__ == "__main__":
    unittest.main()

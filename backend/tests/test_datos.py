"""Verifica la adaptación completa sin modificar la base oficial ni usar servicios externos."""
import asyncio
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import datos, servicio as svc
from backend.almacen import Almacen
from backend.main import app


CLIENTS = b"ID Cliente,contactos_semana_actual,score_hogar,score_canal_sms,autoriza_sms,edad_nueva\nA,0,0.9,0.8,1,18\nB,0,0.7,0.9,1,65\nC,2,0.8,0.6,1,35\n"


async def request(method, path, payload=None, raw=None):
    body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else b"")
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Future()

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
             "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": [(b"content-type", b"application/octet-stream" if raw is not None else b"application/json")],
             "server": ("test", 80), "client": ("test", 123)}
    await app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    content = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, content


class AdaptiveDataTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"VERCEL": "", "BLOB_READ_WRITE_TOKEN": "", "BLOB_STORE_ID": "", "NBA_STORAGE_DIR": self.directory.name})
        self.env.start()
        self.store = patch.object(svc, "STORE", Almacen(Path(self.directory.name)))
        self.store.start()
        svc.CACHE.clear()
        svc.GRID_CACHE.clear()

    def tearDown(self):
        self.store.stop()
        self.env.stop()
        self.directory.cleanup()
        svc.CACHE.clear()
        svc.GRID_CACHE.clear()

    async def json_request(self, method, path, payload=None, expected=200):
        status, content = await request(method, path, payload)
        result = json.loads(content)
        self.assertEqual(status, expected, result)
        return result

    async def upload(self, raw=CLIENTS, filename="clientes.csv"):
        load = await self.json_request("POST", "/api/datos/archivos", {"nombre": filename, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        for part, offset in enumerate(range(0, len(raw), load["tamano_parte"])):
            status, content = await request("PUT", f"/api/datos/archivos/{load['id']}/partes/{part}", raw=raw[offset:offset + load["tamano_parte"]])
            self.assertEqual(status, 200, content)
        result = await self.json_request("POST", f"/api/datos/archivos/{load['id']}/analizar", {})
        return load, result["tablas"]

    async def base(self):
        _, tables = await self.upload()
        return await self.json_request("POST", "/api/datos/preparar", {"principal": tables[0]["id"], "id_columna": "id_cliente"})

    async def test_new_column_changes_assignment_and_csv(self):
        original_hash = svc.DATA_HASH
        base = await self.base()
        self.assertEqual(base["clientes"], 3)
        self.assertIn("edad_nueva", [column["nombre"] for column in base["columnas"]])
        config = base["config"]
        config["parametros"]["politica_contacto"]["max_contactos_semana"] = 2
        config["reglas"].append({"id": "N-EDAD", "control": "N-EDAD", "nombre": "No contactar mayores", "tipo": "elegibilidad",
                                 "alcance": {"nivel": "global", "valores": []}, "condicion": {"atributo": "edad_nueva", "operador": ">=", "valor": 60}, "accion": "excluir", "activa": True})
        run = await self.json_request("POST", f"/api/datos/bases/{base['id']}/simular", {"config": config, "fecha": "2026-11-05"})
        self.assertIsNone(run["referencia"])
        self.assertIsNone(run["metodos"]["optimo"]["violaciones_reto"])
        self.assertEqual(run["metodos"]["optimo"]["violaciones"], 0)
        self.assertEqual(run["metodos"]["optimo"]["clientes"], 1)
        self.assertAlmostEqual(run["metodos"]["optimo"]["valor_esperado"], .72)
        self.assertEqual(run["base"]["id"], base["id"])
        status, csv = await request("GET", f"/api/parrilla/{run['id']}/csv")
        self.assertEqual(status, 200)
        self.assertEqual(len(csv.decode().strip().splitlines()), 4)
        changed = deepcopy(config)
        changed["reglas"][-1]["activa"] = False
        rerun = await self.json_request("POST", f"/api/datos/bases/{base['id']}/simular", {"config": changed, "fecha": "2026-11-05"})
        self.assertEqual(rerun["metodos"]["optimo"]["clientes"], 2)
        self.assertNotEqual(run["id"], rerun["id"])
        self.assertEqual(svc.DATA_HASH, original_hash)
        self.assertEqual(len(svc.DATA), 100_000)
        await self.json_request("GET", f"/api/clusters/{run['id']}", expected=400)

    async def test_join_is_real_and_persistent(self):
        _, clients = await self.upload()
        _, extra = await self.upload(b"customer_id,nuevo_ingreso\nA,100\nB,200\nC,300\n", "ingresos.csv")
        result = await self.json_request("POST", "/api/datos/preparar", {"principal": clients[0]["id"], "id_columna": "id_cliente",
                                              "uniones": [{"tabla": extra[0]["id"], "izquierda": "id_cliente", "derecha": "customer_id"}]})
        metadata, frame = datos.load_base(result["id"])
        self.assertEqual(frame.nuevo_ingreso.tolist(), ["100", "200", "300"])
        self.assertEqual(len(metadata["fuentes"]), 2)
        restored = await self.json_request("GET", f"/api/datos/bases/{result['id']}")
        self.assertEqual(restored["datos_sha256"], result["datos_sha256"])

    async def test_join_rejects_missing_and_duplicate_keys(self):
        _, clients = await self.upload()
        for raw in [b"id_cliente,valor\nA,1\nA,2\nC,3\n", b"id_cliente,valor\nA,1\nB,2\n"]:
            _, tables = await self.upload(raw, "extra.csv")
            await self.json_request("POST", "/api/datos/preparar", {"principal": clients[0]["id"], "id_columna": "id_cliente",
                                   "uniones": [{"tabla": tables[0]["id"], "izquierda": "id_cliente", "derecha": "id_cliente"}]}, expected=400)

    async def test_excel_detects_separate_sheets(self):
        from openpyxl import Workbook
        book = Workbook()
        book.active.title = "Clientes"
        book.active.append(["ID Cliente", "Edad"])
        book.active.append(["0001", 18])
        book.create_sheet("Scores").append(["id_cliente", "score_canal_push"])
        book["Scores"].append(["0001", .8])
        stream = io.BytesIO()
        book.save(stream)
        _, tables = await self.upload(stream.getvalue(), "base.xlsx")
        self.assertEqual([table["nombre"] for table in tables], ["Clientes", "Scores"])
        _, frame = datos.load_table(tables[0]["id"])
        self.assertEqual(frame.id_cliente.tolist(), ["0001"])

    async def test_upload_parts_integrity_and_cleanup(self):
        raw = b"id_cliente,descripcion\n" + b"".join(f"A{i},descripcion de cliente con datos nuevos\n".encode() for i in range(30_000))
        load, tables = await self.upload(raw)
        self.assertEqual(tables[0]["filas"], 30_000)
        self.assertIsNone(svc.STORE.read(f"cargas/{load['id']}/0.bin"))
        again = await self.json_request("POST", f"/api/datos/archivos/{load['id']}/analizar", {})
        self.assertEqual(again["tablas"][0]["id"], tables[0]["id"])

    async def test_incomplete_or_corrupt_upload_cannot_be_analyzed(self):
        load = await self.json_request("POST", "/api/datos/archivos", {"nombre": "base.csv", "bytes": len(CLIENTS), "sha256": "0" * 64})
        await self.json_request("POST", f"/api/datos/archivos/{load['id']}/analizar", {}, expected=400)
        status, _ = await request("PUT", f"/api/datos/archivos/{load['id']}/partes/0", raw=CLIENTS[:-1])
        self.assertEqual(status, 400)
        status, _ = await request("PUT", f"/api/datos/archivos/{load['id']}/partes/0", raw=CLIENTS)
        self.assertEqual(status, 200)
        failure = await self.json_request("POST", f"/api/datos/archivos/{load['id']}/analizar", {}, expected=400)
        self.assertIn("no coincide", failure["detail"])

    async def test_malformed_headers_and_scores_fail_clearly(self):
        for raw in [b"ID Cliente,id_cliente\nA,B\n", b"id_cliente,,valor\nA,x,1\n"]:
            with self.assertRaises(ValueError):
                datos.parse_file(raw, "base.csv")
        base = await self.base()
        config = base["config"]
        config["campanas"][0]["columna_score"] = "edad_nueva"
        failure = await self.json_request("POST", f"/api/datos/bases/{base['id']}/simular", {"config": config, "fecha": "2026-11-05"}, expected=400)
        self.assertIn("Score fuera", failure["detail"])

    async def test_json_and_semicolon_decimal_comma(self):
        raw = b'{"clientes":[{"id_cliente":"001","nuevo":12}],"scores":[{"id_cliente":"001","score_canal_sms":0.8}]}'
        _, tables = await self.upload(raw, "datos.json")
        self.assertEqual(len(tables), 2)
        _, tables = await self.upload(b"id_cliente;score_hogar;score_canal_sms\n001;0,8;0,9\n", "base.csv")
        _, frame = datos.load_table(tables[0]["id"])
        self.assertEqual(frame.score_hogar.tolist(), ["0.8"])
        self.assertEqual(frame.id_cliente.tolist(), ["001"])

    async def test_missing_weekly_data_is_not_fabricated(self):
        _, tables = await self.upload(b"id_cliente,score_nuevo,score_canal_sms\nA,0.8,0.9\n")
        base = await self.json_request("POST", "/api/datos/preparar", {"principal": tables[0]["id"], "id_columna": "id_cliente"})
        self.assertEqual(base["config"]["parametros"]["politica_contacto"]["columna_contactos_semana"], "")
        await self.json_request("POST", f"/api/datos/bases/{base['id']}/simular", {"config": base["config"], "fecha": "2026-11-05"}, expected=400)


if __name__ == "__main__":
    unittest.main()

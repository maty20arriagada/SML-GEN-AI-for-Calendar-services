# -*- coding: utf-8 -*-
"""
test_trazas.py - Tests unitarios para el sistema de trazas inter-agente y guardado JSONL.
7 tests que verifican registro de turnos, herramientas y persistencia.
"""

import json
import tempfile
import unittest
from pathlib import Path

from deliverable3.trazas import TrazaEjecucion


class TestTrazas(unittest.TestCase):

    def test_traza_inicializacion(self):
        traza = TrazaEjecucion("Texto de prueba")
        self.assertEqual(traza.frase, "Texto de prueba")
        self.assertEqual(len(traza.turnos), 0)

    def test_traza_registrar_agente(self):
        traza = TrazaEjecucion()
        traza.registrar_agente("A1_Triage", "Evaluación positiva", decision=True)
        self.assertEqual(len(traza.turnos), 1)
        self.assertEqual(traza.turnos[0]["tipo"], "agente")
        self.assertEqual(traza.turnos[0]["agente"], "A1_Triage")
        self.assertTrue(traza.turnos[0]["decision"])

    def test_traza_registrar_tool(self):
        traza = TrazaEjecucion()
        traza.registrar_tool("resolver_fecha", {"frase": "10/09"}, "2026-09-10")
        self.assertEqual(len(traza.turnos), 1)
        self.assertEqual(traza.turnos[0]["tipo"], "tool")
        self.assertEqual(traza.turnos[0]["tool"], "resolver_fecha")
        self.assertEqual(traza.turnos[0]["resultado"], "2026-09-10")

    def test_traza_registrar_evento(self):
        traza = TrazaEjecucion()
        evento = {"titulo": "Reunión", "fecha": "2026-09-10"}
        traza.registrar_evento("APROBADO", evento)
        self.assertEqual(len(traza.turnos), 1)
        self.assertEqual(traza.turnos[0]["tipo"], "evento")
        self.assertEqual(traza.turnos[0]["estado"], "APROBADO")

    def test_traza_guardar_jsonl(self):
        traza = TrazaEjecucion("Reunión mañana")
        traza.registrar_agente("A1", "ok")
        traza.registrar_tool("t1", {}, 123)
        traza.registrar_evento("FINAL", {"ok": True})

        with tempfile.TemporaryDirectory() as tmpdir:
            ruta = Path(tmpdir) / "sub" / "traza.jsonl"
            res = traza.guardar(ruta)
            self.assertTrue(ruta.exists())
            self.assertEqual(res, str(ruta))

            lineas = ruta.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lineas), 3)
            obj1 = json.loads(lineas[0])
            self.assertEqual(obj1["agente"], "A1")

    def test_traza_leer_jsonl(self):
        traza = TrazaEjecucion()
        traza.registrar_evento("APROBADO", {"fecha": "2026-09-10"})
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            ruta = f.name
        try:
            traza.guardar(ruta)
            with open(ruta, "r", encoding="utf-8") as f:
                d = json.loads(f.readline())
            self.assertEqual(d["estado"], "APROBADO")
        finally:
            Path(ruta).unlink(missing_ok=True)

    def test_traza_crear_directorios(self):
        traza = TrazaEjecucion()
        with tempfile.TemporaryDirectory() as tmpdir:
            ruta_profunda = Path(tmpdir) / "a" / "b" / "c" / "test.jsonl"
            traza.guardar(ruta_profunda)
            self.assertTrue(ruta_profunda.exists())


if __name__ == "__main__":
    unittest.main()

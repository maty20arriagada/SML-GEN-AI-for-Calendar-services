# -*- coding: utf-8 -*-
"""
test_grafo.py - Tests del punto de entrada grafo.ejecutar con el brazo E1 (solución D2) y del contrato de 9 campos.
Los tests de E4 están en test_agentes_v3.py.
"""

import json
import unittest

from deliverable3.agentes import BRAZOS
from deliverable3.grafo import CAMPOS_CONTRATO_9, ejecutar


class MockMotorExtractor:
    def generar(self, mensajes):
        return json.dumps({
            "titulo": "Reunión",
            "hora_inicio": "22:00",
            "duracion_minutos": None,
            "participantes": [],
            "ubicacion": None,
            "recordatorio_minutos": None
        })


class TestGrafo(unittest.TestCase):

    def setUp(self):
        self.motor = MockMotorExtractor()

    def test_ejecutar_baseline_e1(self):
        evento, traza = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E1"], motor=self.motor)
        self.assertEqual(evento.get("fecha"), "2026-09-10")
        self.assertTrue(any(t.get("estado") == "BASELINE_D2" for t in traza.turnos))

    def test_ejecutar_contrato_9_campos_presentes(self):
        evento, _ = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E1"], motor=self.motor)
        for campo in CAMPOS_CONTRATO_9:
            self.assertIn(campo, evento, f"Falta campo obligatorio {campo}")

    def test_ejecutar_e1_traza_turnos(self):
        _, traza = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E1"], motor=self.motor)
        tipos = [t["tipo"] for t in traza.turnos]
        self.assertIn("agente", tipos)
        self.assertIn("tool", tipos)
        self.assertIn("evento", tipos)

    def test_brazo_desconocido(self):
        with self.assertRaises(ValueError):
            ejecutar("Reunión el 10/09", cfg={"nombre": "x"}, motor=self.motor)


if __name__ == "__main__":
    unittest.main()

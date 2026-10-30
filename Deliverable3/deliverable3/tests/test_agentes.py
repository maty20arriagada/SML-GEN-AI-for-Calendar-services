# -*- coding: utf-8 -*-
"""
test_agentes.py - Tests del extractor del baseline D2 (E1) y de la base común de agentes. Sin GPU.
"""

import json
import unittest

from deliverable3.agentes import AgenteExtractor, _extraer_json
from deliverable3.trazas import TrazaEjecucion


class MockMotor:
    def __init__(self, respuesta: str):
        self.respuesta = respuesta

    def generar(self, mensajes):
        return self.respuesta


class TestAgentes(unittest.TestCase):

    def test_extractor_campos_semanticos(self):
        sem_esperado = {
            "titulo": "Reunión",
            "hora_inicio": "10:00",
            "duracion_minutos": 60,
            "participantes": ["Ana"],
            "ubicacion": "Sala 1",
            "recordatorio_minutos": 15,
        }
        motor = MockMotor(json.dumps(sem_esperado))
        agente = AgenteExtractor(motor)
        traza = TrazaEjecucion()
        res = agente.extraer("Reunión con Ana en Sala 1 a las 10:00", traza)
        self.assertEqual(res["titulo"], "Reunión")
        self.assertEqual(res["participantes"], ["Ana"])
        self.assertEqual(res["duracion_minutos"], 60)
        self.assertTrue(any(t["tipo"] == "agente" for t in traza.turnos))

    def test_extractor_manejo_json_invalido(self):
        motor = MockMotor("Texto no formateado sin JSON válido")
        agente = AgenteExtractor(motor)
        res = agente.extraer("Reunión mañana", TrazaEjecucion())
        self.assertIn("titulo", res)
        self.assertEqual(res["participantes"], [])

    def test_extraer_json_con_bloque_markdown(self):
        self.assertEqual(_extraer_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(_extraer_json("sin json"), {})


if __name__ == "__main__":
    unittest.main()

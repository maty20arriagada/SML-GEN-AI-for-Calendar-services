# -*- coding: utf-8 -*-
"""
test_agentes.py - Tests unitarios para los 4 agentes individuales (A1, A2, A3, A4).
10 tests ejecutables sin GPU usando GeneradorMock.
"""

import json
import unittest

from deliverable3.agentes import (
    AgenteExtractor,
    AgenteTemporal,
    AgenteTriage,
    AgenteVerificador,
)
from deliverable3.trazas import TrazaEjecucion


class MockMotor:
    def __init__(self, respuesta: str):
        self.respuesta = respuesta

    def generar(self, mensajes):
        return self.respuesta


class TestAgentes(unittest.TestCase):

    def test_triage_evento_valido(self):
        motor = MockMotor(json.dumps({"es_evento": True, "razon": "Reunión laboral", "idioma": "es"}))
        agente = AgenteTriage(motor)
        traza = TrazaEjecucion("Reunión con el equipo mañana")
        res = agente.evaluar("Reunión con el equipo mañana", traza)
        self.assertTrue(res["continuar"])
        self.assertEqual(res["idioma"], "es")
        self.assertTrue(any(t["tipo"] == "agente" for t in traza.turnos))

    def test_triage_rechazo_ruido(self):
        motor = MockMotor(json.dumps({"es_evento": False, "razon": "Saludo casual", "idioma": "es"}))
        agente = AgenteTriage(motor)
        traza = TrazaEjecucion("Hola, ¿cómo estás?")
        res = agente.evaluar("Hola, ¿cómo estás?", traza)
        self.assertFalse(res["continuar"])

    def test_triage_idioma_es(self):
        motor = MockMotor(json.dumps({"es_evento": True, "razon": "evento", "idioma": "es"}))
        agente = AgenteTriage(motor)
        res = agente.evaluar("Junta mañana a las 10", TrazaEjecucion())
        self.assertEqual(res["idioma"], "es")

    def test_triage_idioma_en(self):
        motor = MockMotor(json.dumps({"es_evento": True, "razon": "event", "idioma": "en"}))
        agente = AgenteTriage(motor)
        res = agente.evaluar("Team meeting tomorrow at 3pm", TrazaEjecucion())
        self.assertEqual(res["idioma"], "en")

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

    def test_extractor_manejo_json_invalido(self):
        motor = MockMotor("Texto no formateado sin JSON válido")
        agente = AgenteExtractor(motor)
        res = agente.extraer("Reunión mañana", TrazaEjecucion())
        self.assertIn("titulo", res)
        self.assertEqual(res["participantes"], [])

    def test_temporal_con_tools(self):
        motor = MockMotor("{}")
        agente = AgenteTemporal(motor, con_tools=True)
        traza = TrazaEjecucion()
        sem = {"titulo": "Reunión", "hora_inicio": "10:00", "participantes": []}
        res = agente.resolver("Reunión el 10/09 a las 10 pm", sem, "2026-09-01", traza)
        self.assertEqual(res["fecha"], "2026-09-10")
        self.assertEqual(res["hora_inicio"], "22:00")
        self.assertTrue(any(t["tipo"] == "tool" for t in traza.turnos))

    def test_temporal_sin_tools(self):
        motor = MockMotor("{}")
        agente = AgenteTemporal(motor, con_tools=False)
        traza = TrazaEjecucion()
        sem = {"titulo": "Reunión", "hora_inicio": "10:00"}
        res = agente.resolver("Reunión el 10/09", sem, "2026-09-01", traza)
        self.assertIsNone(res["fecha"])
        self.assertFalse(any(t["tipo"] == "tool" for t in traza.turnos))

    def test_verificador_aprobado(self):
        motor = MockMotor("{}")
        agente = AgenteVerificador(motor)
        traza = TrazaEjecucion()
        evento = {"fecha": "2026-09-10", "hora_inicio": "22:00", "participantes": ["Ana"]}
        _, estado = agente.auditar("Reunión con Ana el 10/09", evento, traza)
        self.assertEqual(estado, "APROBADO")

    def test_verificador_incompleto(self):
        motor = MockMotor("{}")
        agente = AgenteVerificador(motor)
        traza = TrazaEjecucion()
        evento = {"fecha": None, "hora_inicio": None}
        _, estado = agente.auditar("Reunión", evento, traza)
        self.assertEqual(estado, "INCOMPLETO")


if __name__ == "__main__":
    unittest.main()

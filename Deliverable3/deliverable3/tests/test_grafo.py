# -*- coding: utf-8 -*-
"""
test_grafo.py - Tests unitarios para el motor de ejecución del grafo multi-agente.
10 tests que verifican smoke tests, fallas de D2 corregidas, y el contrato de 9 campos.
"""

import json
import unittest

from deliverable3.agentes import BRAZOS
from deliverable3.grafo import CAMPOS_CONTRATO_9, ejecutar


class MockMotorGrafo:
    def generar(self, mensajes):
        ultimo = ""
        for m in reversed(mensajes):
            if m.get("role") == "user":
                ultimo = m.get("content", "")
                break
        
        # Simulación de A1 Triage
        if "Evalúa esta frase" in ultimo:
            if "Hola qué tal" in ultimo:
                return json.dumps({"es_evento": False, "razon": "Saludo sin evento"})
            return json.dumps({"es_evento": True, "razon": "Evento agendable", "idioma": "es"})

        # Simulación de A2 Extractor LoRA
        if "10 pm" in ultimo:
            return json.dumps({
                "titulo": "Reunión",
                "hora_inicio": "10:00",  # Sesgo de D2 a corregir por A3/A4
                "duracion_minutos": None,
                "participantes": [],
                "ubicacion": None,
                "recordatorio_minutos": None
            })
        if "Ensayo de la banda" in ultimo:
            return json.dumps({
                "titulo": "Ensayo de la banda",
                "hora_inicio": "18:00",
                "duracion_minutos": None,
                "participantes": ["banda"],  # Error de D2 a corregir por A4
                "ubicacion": None,
                "recordatorio_minutos": None
            })
        if "Vacuna del perro" in ultimo:
            return json.dumps({
                "titulo": "Vacuna del perro",
                "hora_inicio": "11:00",
                "duracion_minutos": None,
                "participantes": ["perro"],  # Error de D2 a corregir por A4
                "ubicacion": None,
                "recordatorio_minutos": None
            })
        if "Sync with team" in ultimo:
            return json.dumps({
                "titulo": "Sync",
                "hora_inicio": "15:00",
                "duracion_minutos": 30,
                "participantes": ["team"],
                "ubicacion": "virtual",
                "recordatorio_minutos": None
            })

        return json.dumps({
            "titulo": "Evento genérico",
            "hora_inicio": "12:00",
            "duracion_minutos": 60,
            "participantes": [],
            "ubicacion": None,
            "recordatorio_minutos": None
        })


class TestGrafo(unittest.TestCase):

    def setUp(self):
        self.motor = MockMotorGrafo()

    def test_ejecutar_smoke_10pm(self):
        # Smoke test idéntico a la celda 6 del notebook de Colab
        evento, traza = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertEqual(evento.get("fecha"), "2026-09-10")
        self.assertEqual(evento.get("hora_inicio"), "22:00")
        self.assertTrue(len(traza.turnos) >= 3)

    def test_ejecutar_contrato_9_campos_presentes(self):
        evento, _ = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E2"], motor=self.motor)
        for campo in CAMPOS_CONTRATO_9:
            self.assertIn(campo, evento, f"Falta campo obligatorio {campo}")

    def test_ejecutar_participantes_ensayo_banda(self):
        # Caso de demo del video (Frase 2 benchmark_ft)
        evento, traza = ejecutar("Ensayo de la banda el 19/09 a las 18:00", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertEqual(evento.get("participantes"), [])
        self.assertEqual(evento.get("fecha"), "2026-09-19")
        self.assertEqual(evento.get("hora_inicio"), "18:00")

    def test_ejecutar_participantes_vacuna_perro(self):
        evento, _ = ejecutar("Vacuna del perro el 15/09 a las 11:00", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertEqual(evento.get("participantes"), [])

    def test_ejecutar_rechazo_triage(self):
        evento, traza = ejecutar("Hola qué tal", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertIsNone(evento.get("fecha"))
        self.assertTrue(any(t.get("estado") == "RECHAZADO" for t in traza.turnos))

    def test_ejecutar_traza_turnos(self):
        _, traza = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E2"], motor=self.motor)
        tipos = [t["tipo"] for t in traza.turnos]
        self.assertIn("agente", tipos)
        self.assertIn("tool", tipos)
        self.assertIn("evento", tipos)

    def test_ejecutar_baseline_e1(self):
        evento, traza = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E1"], motor=self.motor)
        self.assertEqual(evento.get("fecha"), "2026-09-10")
        self.assertTrue(any(t.get("estado") == "BASELINE_D2" for t in traza.turnos))

    def test_ejecutar_multilingue_en(self):
        evento, _ = ejecutar("Sync with team tomorrow at 3pm", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertEqual(evento.get("hora_inicio"), "15:00")
        self.assertEqual(evento.get("participantes"), ["team"])

    def test_ejecutar_duracion_default_null(self):
        evento, _ = ejecutar("Reunión el 10/09 a las 10 pm", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertIsNone(evento.get("duracion_minutos"))

    def test_ejecutar_recurrencia_semanal(self):
        evento, _ = ejecutar("Reunión semanal los lunes a las 10", cfg=BRAZOS["E2"], motor=self.motor)
        self.assertEqual(evento.get("recurrence"), "RRULE:FREQ=WEEKLY")


if __name__ == "__main__":
    unittest.main()

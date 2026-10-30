# -*- coding: utf-8 -*-
"""
test_agentes_v2.py - Tests de A3' / A4' y de los brazos E3* (etapa 2, intento2). Sin GPU.
"""

import json
import unittest

from deliverable3.agentes import BRAZOS
from deliverable3.agentes_v2 import AgenteTemporalV2, AgenteVerificadorV2
from deliverable3.grafo import ejecutar
from deliverable3.trazas import TrazaEjecucion


class MotorFijo:
    """Devuelve siempre la misma respuesta y cuenta las llamadas."""

    def __init__(self, respuesta="{}"):
        self.respuesta = respuesta
        self.llamadas = 0

    def generar(self, mensajes):
        self.llamadas += 1
        return self.respuesta


class MotorGrafo:
    """A1 -> es evento; A2 -> extracción por frase; A4 (reparación) -> descarta los dudosos."""

    def __init__(self, a2):
        self.a2 = a2
        self.reparaciones = 0

    def generar(self, mensajes):
        u = [m for m in mensajes if m["role"] == "user"][-1]["content"]
        if u.startswith("Evalúa"):
            return json.dumps({"es_evento": True})
        if "Participantes propuestos" in u:
            self.reparaciones += 1
            return json.dumps({"participantes": []})
        for clave, salida in self.a2.items():
            if clave in u:
                return json.dumps(salida)
        return json.dumps({})


A2_BASE = {"titulo": "x", "hora_inicio": None, "duracion_minutos": None,
           "participantes": [], "ubicacion": None, "recordatorio_minutos": None}


class TestAgenteTemporalV2(unittest.TestCase):

    def test_recordatorio_no_pisa_la_duracion_de_a2(self):
        frase = "puedes agendar la reunión el 10 a las 14? avísame 15 min antes"
        sem = dict(A2_BASE, hora_inicio="14:00", recordatorio_minutos=15)
        traza = TrazaEjecucion(frase)
        ev = AgenteTemporalV2(None).resolver(frase, sem, "2026-09-01", traza)
        self.assertIsNone(ev["duracion_minutos"])
        self.assertEqual(ev["recordatorio_minutos"], 15)
        self.assertEqual(ev["fecha"], "2026-09-10")

    def test_duracion_de_a2_se_conserva_si_la_tool_no_ve_nada(self):
        frase = "hackathon el sábado de 10 a 18"
        sem = dict(A2_BASE, hora_inicio="10:00", duracion_minutos=480)
        ev = AgenteTemporalV2(None).resolver(frase, sem, "2026-09-01", TrazaEjecucion(frase))
        self.assertEqual(ev["duracion_minutos"], 480)

    def test_traza_registra_procedencia_por_campo(self):
        frase = "Entrevista con la candidata a diseñadora el 1 de octubre a las 11, media hora"
        sem = dict(A2_BASE, hora_inicio="11:00", participantes=["candidata"])
        traza = TrazaEjecucion(frase)
        ev = AgenteTemporalV2(None).resolver(frase, sem, "2026-09-01", traza)
        self.assertEqual(ev["participantes"], ["candidata a diseñadora"])
        turno = [t for t in traza.turnos if t["tipo"] == "agente"][-1]
        self.assertEqual(turno["procedencia"]["participantes"], "tool")
        self.assertEqual(turno["procedencia"]["duracion_minutos"], "tool")
        self.assertEqual(turno["procedencia"]["fecha"], "tool")


class TestAgenteVerificadorV2(unittest.TestCase):
    BASE = {"titulo": "Ensayo de la orquesta", "fecha": "2026-09-26", "hora_inicio": "18:00",
            "duracion_minutos": None, "participantes": ["orquesta"], "ubicacion": None,
            "recordatorio_minutos": None, "zona_horaria": "America/Santiago", "recurrence": None}
    FRASE = "Ensayo de la orquesta el 26 de septiembre a las 18:00"

    def test_descarta_participante_dudoso_si_el_modelo_lo_pide(self):
        motor = MotorFijo(json.dumps({"razonamiento": "tema del ensayo", "participantes": []}))
        ev, estado = AgenteVerificadorV2(motor).auditar(self.FRASE, dict(self.BASE), TrazaEjecucion())
        self.assertEqual(ev["participantes"], [])
        self.assertEqual(estado, "CORREGIDO")
        self.assertEqual(motor.llamadas, 1)

    def test_conserva_al_participante_si_el_modelo_lo_confirma(self):
        motor = MotorFijo(json.dumps({"participantes": ["orquesta"]}))
        ev, _ = AgenteVerificadorV2(motor).auditar(self.FRASE, dict(self.BASE), TrazaEjecucion())
        self.assertEqual(ev["participantes"], ["orquesta"])

    def test_respuesta_inutilizable_reintenta_una_vez_y_conserva(self):
        motor = MotorFijo("no es json")
        ev, _ = AgenteVerificadorV2(motor).auditar(self.FRASE, dict(self.BASE), TrazaEjecucion())
        self.assertEqual(ev["participantes"], ["orquesta"])
        self.assertEqual(motor.llamadas, 2)

    def test_el_modelo_no_puede_inventar_participantes(self):
        motor = MotorFijo(json.dumps({"participantes": ["fantasma"]}))
        ev, _ = AgenteVerificadorV2(motor).auditar(self.FRASE, dict(self.BASE), TrazaEjecucion())
        self.assertEqual(ev["participantes"], ["orquesta"])
        self.assertEqual(motor.llamadas, 2)

    def test_sin_dudosos_no_llama_al_modelo(self):
        motor = MotorFijo()
        ev = dict(self.BASE, participantes=["Camila"])
        out, estado = AgenteVerificadorV2(motor).auditar("Cena con Camila el 26 de septiembre a las 18:00", ev, TrazaEjecucion())
        self.assertEqual(motor.llamadas, 0)
        self.assertEqual(out["participantes"], ["Camila"])
        self.assertEqual(estado, "APROBADO")

    def test_duracion_igual_al_recordatorio_se_anula(self):
        frase = "mañana a las 8 tengo control con el dentista, recuérdame media hora antes"
        ev = dict(self.BASE, fecha="2026-09-02", hora_inicio="08:00", participantes=["dentista"],
                  duracion_minutos=30, recordatorio_minutos=30)
        out, estado = AgenteVerificadorV2(MotorFijo()).auditar(frase, ev, TrazaEjecucion())
        self.assertIsNone(out["duracion_minutos"])
        self.assertEqual(estado, "CORREGIDO")

    def test_duracion_valida_que_coincide_con_el_recordatorio_se_conserva(self):
        frase = "Reunión el 26 de septiembre a las 18:00 por 30 minutos, avísame 30 minutos antes"
        ev = dict(self.BASE, participantes=[], duracion_minutos=30, recordatorio_minutos=30)
        out, _ = AgenteVerificadorV2(MotorFijo()).auditar(frase, ev, TrazaEjecucion())
        self.assertEqual(out["duracion_minutos"], 30)

    def test_fecha_inexistente_y_hora_fuera_de_rango(self):
        ev = dict(self.BASE, participantes=[], fecha="2026-10-31", hora_inicio="25:00")
        out, estado = AgenteVerificadorV2(MotorFijo()).auditar("Reunión el 31/09 a las 25:00", ev, TrazaEjecucion())
        self.assertIsNone(out["fecha"])
        self.assertIsNone(out["hora_inicio"])
        self.assertEqual(estado, "INCOMPLETO")

    def test_marca_ampm_manda_sobre_la_hora_extraida(self):
        ev = dict(self.BASE, participantes=[], hora_inicio="09:00")
        out, estado = AgenteVerificadorV2(MotorFijo()).auditar("Cena el 26 de septiembre a las 9 pm", ev, TrazaEjecucion())
        self.assertEqual(out["hora_inicio"], "21:00")
        self.assertEqual(estado, "CORREGIDO")


class TestBrazosE3(unittest.TestCase):
    A2 = {
        "Ensayo de la orquesta": dict(A2_BASE, titulo="Ensayo de la orquesta", hora_inicio="18:00", participantes=["orquesta"]),
        "avísame 15 min antes": dict(A2_BASE, titulo="reunión de sincronización", hora_inicio="14:00", recordatorio_minutos=15),
        "viernes 18": dict(A2_BASE, titulo="Reunión de pauta", hora_inicio="10:00"),
        "candidata a diseñadora": dict(A2_BASE, titulo="Entrevista", hora_inicio="11:00", participantes=["candidata"]),
    }

    def correr(self, brazo, frase):
        motor = MotorGrafo(self.A2)
        ev, traza = ejecutar(frase, cfg=BRAZOS[brazo], motor=motor, fecha_ref="2026-09-01")
        return ev, traza, motor

    def test_e3_complemento_del_titulo(self):
        ev, traza, motor = self.correr("E3", "Ensayo de la orquesta el 26 de septiembre a las 18:00")
        self.assertEqual(ev["participantes"], [])
        self.assertEqual(motor.reparaciones, 1)
        self.assertEqual(traza.turnos[-1]["estado"], "CORREGIDO")

    def test_e3_recordatorio_no_es_duracion(self):
        ev, _, _ = self.correr("E3", "puedes agendar la reunión de sincronización el 10 a las 14? avísame 15 min antes")
        self.assertIsNone(ev["duracion_minutos"])
        self.assertEqual(ev["recordatorio_minutos"], 15)

    def test_e2_conserva_la_falla_que_e3_corrige(self):
        ev, _, _ = self.correr("E2", "puedes agendar la reunión de sincronización el 10 a las 14? avísame 15 min antes")
        self.assertEqual(ev["duracion_minutos"], 15)  # comportamiento del intento1, no se toca

    def test_e3_viernes_18(self):
        ev, _, _ = self.correr("E3", "Reunión de pauta el viernes 18 a las 10")
        self.assertEqual(ev["fecha"], "2026-09-18")

    def test_e3_rol_compuesto(self):
        ev, _, _ = self.correr("E3", "Entrevista con la candidata a diseñadora el 1 de octubre a las 11")
        self.assertEqual(ev["participantes"], ["candidata a diseñadora"])

    def test_e3a_no_llama_al_verificador_v2(self):
        _, _, motor = self.correr("E3a", "Ensayo de la orquesta el 26 de septiembre a las 18:00")
        self.assertEqual(motor.reparaciones, 0)

    def test_e3b_corrige_duracion_con_a4_v2(self):
        ev, _, _ = self.correr("E3b", "puedes agendar la reunión de sincronización el 10 a las 14? avísame 15 min antes")
        self.assertIsNone(ev["duracion_minutos"])  # A3 v1 la pisa; el validador V2 de A4 la deshace

    def test_e3c_usa_el_prompt_basico(self):
        self.assertEqual(BRAZOS["E3c"]["a4_prompt"], "a4_reparador_basico.txt")
        self.assertEqual(BRAZOS["E3"]["a4_prompt"], "a4_reparador_v2.txt")


class TestPromptsV2(unittest.TestCase):

    def test_prompts_existen_y_piden_json(self):
        from deliverable3.agentes import _cargar_prompt
        for nombre in ("a4_reparador_v2.txt", "a4_reparador_basico.txt"):
            texto = _cargar_prompt(nombre)
            self.assertIn('"participantes"', texto, nombre)
        self.assertIn("razonamiento", _cargar_prompt("a4_reparador_v2.txt"))
        self.assertNotIn("razonamiento", _cargar_prompt("a4_reparador_basico.txt"))


if __name__ == "__main__":
    unittest.main()

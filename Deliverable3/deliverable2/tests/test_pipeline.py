# -*- coding: utf-8 -*-
"""
test_pipeline.py -- Tests del pipeline (normalizacion, brazos, API de calendario)
usando GeneradorMock: no requiere GPU.

Ejecucion:  python -m unittest tests.test_pipeline -v
"""

import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from calendario.calendar_api import ErrorDeContrato, LocalCalendarAPI  # noqa: E402
from pipeline.modelo import GeneradorMock  # noqa: E402
from pipeline.normalizacion import (  # noqa: E402
    CAMPOS_CONTRATO,
    ensamblar_evento,
    extraer_json,
    normalizar_entero,
    normalizar_hora,
    normalizar_participantes,
    objetivo_nulo,
)
from pipeline.pipeline import BRAZOS, CalendarPipeline  # noqa: E402

RUTA_TMP = os.path.join(os.environ.get("TEMP", RAIZ), "calendario_test.json")

MODELO_SIN_FECHA = json.dumps({
    "titulo": "reunion",
    "hora_inicio": "10:00",
    "duracion_minutos": None,
    "participantes": [],
    "ubicacion": None,
    "recordatorio_minutos": None,
    "zona_horaria": "America/Santiago",
    "recurrence": None,
}, ensure_ascii=False)

MODELO_FECHA_MALA = json.dumps({
    "titulo": "reunion",
    "fecha": "2026-01-15",
    "hora_inicio": "10:00",
    "duracion_minutos": None,
    "participantes": [],
    "ubicacion": None,
    "recordatorio_minutos": None,
    "zona_horaria": "America/Santiago",
}, ensure_ascii=False)

FRASE = "agenda reunion manana 10am porfa"   # fecha correcta: 2026-09-02


class TestExtraerJson(unittest.TestCase):
    def test_json_puro(self):
        self.assertEqual(extraer_json('{"a": 1}'), {"a": 1})

    def test_json_entre_texto(self):
        r = extraer_json('Claro! aqui esta:\n{"titulo": "X"}\nSaludos')
        self.assertEqual(r["titulo"], "X")

    def test_dict_pasa_directo(self):
        self.assertEqual(extraer_json({"a": 2}), {"a": 2})

    def test_prosa_sin_json(self):
        r = extraer_json("Lo siento, no puedo ayudarte con eso.")
        self.assertIn("error", r)


class TestNormalizadores(unittest.TestCase):
    def test_participantes(self):
        self.assertEqual(normalizar_participantes(["Ana", " ", 3, "<x>", "Pedro"]), ["Ana", "Pedro"])
        self.assertEqual(normalizar_participantes(None), [])

    def test_enteros(self):
        self.assertEqual(normalizar_entero("30 min"), 30)
        self.assertEqual(normalizar_entero(45), 45)
        self.assertIsNone(normalizar_entero(True))
        self.assertIsNone(normalizar_entero(None))

    def test_hora(self):
        self.assertEqual(normalizar_hora("4"), "16:00")
        self.assertEqual(normalizar_hora("10am"), "10:00")
        self.assertEqual(normalizar_hora("15:30"), "15:30")
        self.assertIsNone(normalizar_hora(None))


class TestEnsamblar(unittest.TestCase):
    def test_contrato_de_nueve_campos(self):
        e = ensamblar_evento({"titulo": "X"}, "Junta de emergencia", fecha_desde_tool=True)
        self.assertEqual(sorted(e.keys()), sorted(CAMPOS_CONTRATO))
        self.assertEqual(len(CAMPOS_CONTRATO), 9)
        self.assertIsNone(e["fecha"])
        self.assertIsNone(e["hora_inicio"])
        self.assertEqual(e["participantes"], [])
        self.assertEqual(e["zona_horaria"], "America/Santiago")

    def test_tool_pisa_la_fecha_del_modelo(self):
        obj = {"titulo": "reunion", "fecha": "2026-01-15"}
        e = ensamblar_evento(obj, FRASE, fecha_desde_tool=True)
        self.assertEqual(e["fecha"], "2026-09-02")   # manana desde 2026-09-01

    def test_sin_tool_se_conserva_la_fecha_del_modelo(self):
        obj = {"titulo": "reunion", "fecha": "2026-01-15"}
        e = ensamblar_evento(obj, FRASE, fecha_desde_tool=False)
        self.assertEqual(e["fecha"], "2026-01-15")

    def test_nunca_inventa(self):
        e = ensamblar_evento({}, "hello", fecha_desde_tool=True)
        for campo, valor in e.items():
            if campo == "zona_horaria":
                continue
            self.assertIn(valor, (None, [], ""), campo)


class TestBrazos(unittest.TestCase):
    def setUp(self):
        self.tuberia = CalendarPipeline(GeneradorMock(respuestas={"*": MODELO_SIN_FECHA}))

    def test_brazo_d_resuelve_fecha_sin_ayuda_del_modelo(self):
        e = self.tuberia.solucion(FRASE)
        self.assertEqual(e["fecha"], "2026-09-02")

    def test_brazo_a_sin_tool_no_resuelve(self):
        e = self.tuberia.baseline(FRASE)
        self.assertIsNone(e["fecha"])   # el mock no dio fecha y no hay herramienta

    def test_brazo_c_pisa_fecha_inventada(self):
        tuberia = CalendarPipeline(GeneradorMock(respuestas={"*": MODELO_FECHA_MALA}))
        self.assertEqual(tuberia.estructurado(FRASE)["fecha"], "2026-01-15")
        self.assertEqual(tuberia.estructurado_tool(FRASE)["fecha"], "2026-09-02")

    def test_los_cuatro_brazos_estan_definidos(self):
        self.assertEqual(sorted(BRAZOS), ["A", "B", "C", "D"])

    def test_error_de_modelo_no_rompe_el_sistema(self):
        tuberia = CalendarPipeline(GeneradorMock(por_defecto="no puedo"))
        e = tuberia.solucion(FRASE)
        self.assertEqual(sorted(e.keys()), sorted(CAMPOS_CONTRATO + ["_error_modelo"]))
        self.assertEqual(e["fecha"], "2026-09-02")   # la herramienta igual aporta la fecha

    def test_solo_contrato_filtra_internas(self):
        e = self.tuberia.solucion(FRASE)
        self.assertEqual(sorted(CalendarPipeline.solo_contrato(e).keys()), sorted(CAMPOS_CONTRATO))


class TestCalendarAPI(unittest.TestCase):
    def setUp(self):
        if os.path.exists(RUTA_TMP):
            os.remove(RUTA_TMP)
        self.api = LocalCalendarAPI(RUTA_TMP)

    def tearDown(self):
        if os.path.exists(RUTA_TMP):
            os.remove(RUTA_TMP)

    def test_create_and_list(self):
        evento = objetivo_nulo()
        evento.update({"titulo": "Junta", "fecha": "2026-09-02", "hora_inicio": "10:00"})
        registro = self.api.create_event(evento)
        self.assertEqual(registro["id"], "evt-0001")
        self.assertEqual(len(self.api.list_events()), 1)

    def test_rechaza_contrato_incompleto(self):
        with self.assertRaises(ErrorDeContrato):
            self.api.create_event({"titulo": "x"})

    def test_rechaza_fecha_invalida(self):
        evento = objetivo_nulo()
        evento["fecha"] = "ayer"
        with self.assertRaises(ErrorDeContrato):
            self.api.create_event(evento)

    def test_export_ics(self):
        evento = objetivo_nulo()
        evento.update({"titulo": "Junta", "fecha": "2026-09-02", "hora_inicio": "10:00",
                       "duracion_minutos": 60})
        self.api.create_event(evento)
        ruta = self.api.exportar_ics(RUTA_TMP.replace(".json", ".ics"))
        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn("BEGIN:VEVENT", contenido)
        self.assertIn("DTSTART:20260902T100000", contenido)
        self.assertIn("SUMMARY:Junta", contenido)
        os.remove(ruta)


if __name__ == "__main__":
    unittest.main(verbosity=2)

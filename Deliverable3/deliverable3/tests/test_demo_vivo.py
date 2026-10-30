# -*- coding: utf-8 -*-
"""
test_demo_vivo.py - Demo en vivo (demo_vivo/demo_calendar.py): E4 + conversión al calendario. Sin GPU ni red.
"""

import unittest
from unittest import mock

from deliverable3.tests.test_agentes_v3 import A1_OK, A2_BASE, A3_TERMINAR, A4_APROBAR, MotorGuion, a3_llamar
from deliverable3.trazas import TrazaEjecucion
from demo_vivo import calendario, demo_calendar as dc

REF = "2026-09-01"
FRASE = "Café con Ana el 10 de septiembre a las 11:00"
A2 = dict(A2_BASE, titulo="Café con Ana", hora_inicio="11:00", participantes=["Ana"])


def motor_ok():
    return MotorGuion(A1=[A1_OK], A2=[A2], A3=[a3_llamar("resolver_fecha", "normalizar_hora"), A3_TERMINAR] * 2,
                      A4=[A4_APROBAR])


def traza_con(estado):
    t = TrazaEjecucion("x")
    t.registrar_evento(estado, {})
    return t


class TestCrearEvento(unittest.TestCase):
    EVENTO = {"titulo": "Café", "fecha": "2026-09-10", "hora_inicio": "11:00", "duracion_minutos": None,
              "participantes": ["Ana"], "ubicacion": None, "recordatorio_minutos": 15,
              "zona_horaria": "America/Santiago", "recurrence": None}

    def test_rechazado_no_se_envia(self):
        with mock.patch.object(calendario, "crear_en_google") as api:
            r = dc.crear_evento({}, traza_con("RECHAZADO"))
        api.assert_not_called()
        self.assertFalse(r["creado"])
        self.assertIn("A1", r["motivo"])

    def test_incompleto_no_se_envia(self):
        with mock.patch.object(calendario, "crear_en_google") as api:
            r = dc.crear_evento(dict(self.EVENTO, fecha=None), traza_con("INCOMPLETO"))
        api.assert_not_called()
        self.assertFalse(r["creado"])

    def test_aprobado_llama_a_google_con_enviar(self):
        respuesta = {"id": "abc", "htmlLink": "https://calendar.google.com/x", "payload": {}}
        with mock.patch.object(calendario, "crear_en_google", return_value=respuesta) as api:
            r = dc.crear_evento(self.EVENTO, traza_con("APROBADO"), enviar=True)
        self.assertEqual(api.call_args.kwargs["enviar"], True)
        self.assertTrue(r["creado"])
        self.assertEqual(r["link"], "https://calendar.google.com/x")

    def test_simulacro_no_crea(self):
        r = dc.crear_evento(self.EVENTO, traza_con("APROBADO"), enviar=False)   # solo imprime el payload
        self.assertFalse(r["creado"])
        self.assertTrue(r["simulacro"])

    def test_payload_google_hora_zona_y_recordatorio(self):
        p = calendario.a_evento_google(self.EVENTO)
        self.assertEqual(p["start"], {"dateTime": "2026-09-10T11:00:00", "timeZone": "America/Santiago"})
        self.assertEqual(p["end"]["dateTime"], "2026-09-10T11:30:00")   # duración nula -> DURACION_DEFECTO
        self.assertEqual(p["reminders"]["overrides"], [{"method": "popup", "minutes": 15}])
        self.assertEqual(p["description"], "Participantes: Ana")

    def test_describir_avisa_duracion_por_defecto(self):
        self.assertTrue(any("por defecto" in l for l in dc.describir(self.EVENTO)))
        self.assertFalse(any("por defecto" in l for l in dc.describir(dict(self.EVENTO, duracion_minutos=45))))


class TestProcesar(unittest.TestCase):
    def correr(self, motor, **kw):
        salida = []
        r = dc.procesar(FRASE, motor, fecha_ref=REF, salida=salida.append, **kw)
        return r, "\n".join(salida)

    def test_flujo_e4_simulacro(self):
        r, texto = self.correr(motor_ok(), enviar=False)
        self.assertEqual(r["evento"]["fecha"], "2026-09-10")
        self.assertEqual(r["evento"]["hora_inicio"], "11:00")
        self.assertEqual(r["estado"], "APROBADO")
        self.assertIn("A4_Verificador: aprobar", texto)
        self.assertFalse(r["creado"])

    def test_rechazo_de_a1_no_pide_confirmacion(self):
        m = MotorGuion(A1=[{"accion": "rechazar", "razon": "saludo"}])
        pregunto = []
        r, texto = self.correr(m, enviar=True, confirmar=lambda: pregunto.append(1) or True)
        self.assertEqual(r["estado"], "RECHAZADO")
        self.assertEqual(pregunto, [])
        self.assertFalse(r["creado"])
        self.assertNotIn("Evento:", texto)

    def test_sin_confirmacion_no_se_crea(self):
        with mock.patch.object(calendario, "crear_en_google") as api:
            r, _ = self.correr(motor_ok(), enviar=True, confirmar=lambda: False)
        api.assert_not_called()
        self.assertEqual(r["motivo"], "no confirmado por la persona")

    def test_confirmado_crea_en_google(self):
        respuesta = {"id": "abc", "htmlLink": "https://calendar.google.com/x"}
        with mock.patch.object(calendario, "crear_en_google", return_value=respuesta) as api:
            r, texto = self.correr(motor_ok(), enviar=True, confirmar=lambda: True)
        api.assert_called_once()
        self.assertTrue(r["creado"])
        self.assertIn("https://calendar.google.com/x", texto)

    def test_hoy_santiago_formato(self):
        self.assertRegex(dc.hoy_santiago(), r"^\d{4}-\d{2}-\d{2}$")


class TestRecurrencia(unittest.TestCase):
    def test_rrule_texto_a_dict(self):
        self.assertEqual(dc.rrule_a_dict("RRULE:FREQ=WEEKLY"), {"frecuencia": "weekly"})
        self.assertEqual(dc.rrule_a_dict("RRULE:FREQ=DAILY;INTERVAL=2;COUNT=5"),
                         {"frecuencia": "daily", "intervalo": 2, "veces": 5})
        self.assertIsNone(dc.rrule_a_dict(None))

    def test_evento_semanal_de_e4_llega_a_google(self):
        # E4 entrega recurrence como texto; calendario.py espera un dict (antes fallaba con AttributeError)
        ev = {"titulo": "Reunión", "fecha": "2026-09-07", "hora_inicio": "10:00", "duracion_minutos": 60,
              "participantes": [], "ubicacion": None, "recordatorio_minutos": None,
              "zona_horaria": "America/Santiago", "recurrence": "RRULE:FREQ=WEEKLY"}
        p = calendario.a_evento_google(dc.para_calendario(ev))
        self.assertEqual(p["recurrence"], ["RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO"])
        self.assertIn("Se repite cada semana", dc.resumen(ev))


class TestChat(unittest.TestCase):
    def chat(self, motor, **kw):
        return dc.Chat(motor, enviar=False, mostrar_baseline=False, **kw)

    def test_completo_se_entrega_en_simulacro(self):
        c = self.chat(motor_ok())
        r = c.mensaje(FRASE, fecha_ref=REF, mostrar=False)
        self.assertTrue(r["entregado"])
        self.assertIsNone(c.pendiente)
        self.assertIn("simulacro", c.html())

    def test_rechazo_no_deja_pendiente(self):
        c = self.chat(MotorGuion(A1=[{"accion": "rechazar", "razon": "saludo"}]))
        r = c.mensaje("Hola, ¿qué tal?", fecha_ref=REF, mostrar=False)
        self.assertFalse(r["entregado"])
        self.assertIsNone(c.pendiente)
        self.assertIn("no parece un evento", c.html())

    def test_falta_fecha_pregunta_y_el_siguiente_mensaje_completa(self):
        sin_hora = dict(A2_BASE, titulo="Reunión con Ana", participantes=["Ana"])
        m = MotorGuion(A1=[A1_OK], A2=[sin_hora, dict(A2_BASE, titulo="x", hora_inicio="16:00")],
                       A3=[a3_llamar("resolver_fecha", "normalizar_hora"), A3_TERMINAR] * 4, A4=[A4_APROBAR])
        c = self.chat(m)
        r1 = c.mensaje("Agéndame una reunión con Ana", fecha_ref=REF, mostrar=False)
        self.assertFalse(r1["entregado"])
        self.assertIsNotNone(c.pendiente)
        self.assertIn("me falta saber", c.html())
        r2 = c.mensaje("el viernes 11 a las 4", fecha_ref=REF, mostrar=False)
        self.assertEqual(m.llamadas["A1"], 1)             # la vuelta de completar corre sin A1
        self.assertTrue(r2["entregado"])
        self.assertEqual(r2["evento"]["titulo"], "Reunión con Ana")
        self.assertEqual(r2["evento"]["participantes"], ["Ana"])
        self.assertEqual((r2["evento"]["fecha"], r2["evento"]["hora_inicio"]), ("2026-09-11", "16:00"))

    def test_baseline_d2_en_la_misma_frase(self):
        c = dc.Chat(motor_ok(), enviar=False, mostrar_baseline=True)
        c.mensaje(FRASE, fecha_ref=REF, mostrar=False)
        self.assertIn("baseline", [q for q, _ in c.historial])

    def test_ics_se_escribe_y_se_descarga(self):
        import os, tempfile
        bajadas = []
        antes = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                c = dc.Chat(motor_ok(), destino="ics", mostrar_baseline=False, descargar=bajadas.append)
                c.mensaje(FRASE, fecha_ref=REF, mostrar=False)
                self.assertEqual(len(bajadas), 1)
                self.assertIn("BEGIN:VEVENT", open(bajadas[0], encoding="utf-8").read())
            finally:
                os.chdir(antes)


if __name__ == "__main__":
    unittest.main()

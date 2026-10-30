# -*- coding: utf-8 -*-
"""
test_tools_v2.py - Tests de las herramientas de la etapa 2 (intento2): las fallas medidas en el
intento1 (duración vs recordatorio, "viernes 18", fechas inexistentes, "tomorrow", rol compuesto)
y una regresión contra el ground truth de fechas de los tres benchmarks.
"""

import json
import unittest
from pathlib import Path

from deliverable3.tools_v2 import (
    calcular_duracion_v2,
    expandir_participante,
    extraer_recordatorio,
    fecha_explicita_invalida,
    hora_ampm_explicita,
    participante_dudoso,
    resolver_fecha_v2,
)

RAIZ = Path(__file__).resolve().parents[2]


class TestDuracionVsRecordatorio(unittest.TestCase):

    def test_recordatorio_no_es_duracion(self):
        for frase, rec in [
            ("puedes agendar la reunión el 10 a las 14? avísame 15 min antes", 15),
            ("mañana a las 8 tengo control con el dentista, recuérdame media hora antes", 30),
            ("la junta de vecinos es el domingo a las 11 en la sede, avisa 1 hora antes xfa", 60),
            ("Clase el 20 de septiembre a las 18:00, recordatorio 15 minutos antes", 15),
        ]:
            self.assertIsNone(calcular_duracion_v2(frase), frase)
            self.assertEqual(extraer_recordatorio(frase), rec, frase)

    def test_duracion_y_recordatorio_en_la_misma_frase(self):
        f = "Defensa el miércoles 16 de septiembre a las 15:00 por 40 minutos, avísame 20 minutos antes"
        self.assertEqual(calcular_duracion_v2(f), 40)
        self.assertEqual(extraer_recordatorio(f), 20)
        f_en = "Sprint planning at 9am for 90 minutes, remind me 15 minutes before"
        self.assertEqual(calcular_duracion_v2(f_en), 90)
        self.assertEqual(extraer_recordatorio(f_en), 15)

    def test_duraciones_comunes(self):
        self.assertEqual(calcular_duracion_v2("2 horas y media"), 150)
        self.assertEqual(calcular_duracion_v2("dura 3 horas y media"), 210)
        self.assertEqual(calcular_duracion_v2("media hora"), 30)
        self.assertEqual(calcular_duracion_v2("por una hora"), 60)
        self.assertEqual(calcular_duracion_v2("dura 45 min"), 45)
        self.assertIsNone(calcular_duracion_v2("Reunión mañana a las 10"))

    def test_en_n_horas_es_inicio_relativo_no_duracion(self):
        self.assertIsNone(calcular_duracion_v2("Reunión en 2 horas"))


class TestFechasV2(unittest.TestCase):
    REF = "2026-09-01"

    def test_dia_de_semana_con_numero(self):
        self.assertEqual(resolver_fecha_v2("Reunión de pauta el viernes 18 a las 10", self.REF), "2026-09-18")
        self.assertEqual(resolver_fecha_v2("Cobertura el miércoles 7 a las 14:00", self.REF), "2026-10-07")

    def test_dia_de_semana_con_mes_sigue_igual(self):
        self.assertEqual(resolver_fecha_v2("Defensa el miércoles 16 de septiembre a las 15:00", self.REF), "2026-09-16")

    def test_hora_despues_del_dia_no_es_fecha(self):
        self.assertEqual(resolver_fecha_v2("Sync el jueves 2pm", self.REF), "2026-09-03")
        self.assertEqual(resolver_fecha_v2("Clase el lunes 14:30", self.REF), "2026-09-07")

    def test_fecha_inexistente_da_none(self):
        for f in ["Reunión el 31/09 a las 10", "Cierre el 30/02 a las 15:00", "Almuerzo el 31 de noviembre a las 13:00"]:
            self.assertTrue(fecha_explicita_invalida(f, self.REF), f)
            self.assertIsNone(resolver_fecha_v2(f, self.REF), f)
        self.assertFalse(fecha_explicita_invalida("Examen el 29/09 a las 9:30", self.REF))

    def test_rango_de_horas_con_guion_no_se_toma_como_fecha(self):
        self.assertFalse(fecha_explicita_invalida("Taller de 14-17 el 5 de octubre", self.REF))

    def test_ingles_relativo(self):
        self.assertEqual(resolver_fecha_v2("Doctor's appointment tomorrow at 7:30am", self.REF), "2026-09-02")
        self.assertEqual(resolver_fecha_v2("Review the day after tomorrow at 10am", self.REF), "2026-09-03")
        self.assertEqual(resolver_fecha_v2("Gym today at 7pm", self.REF), "2026-09-01")

    def test_regresion_fechas_en_los_tres_benchmarks(self):
        """resolver_fecha_v2 acierta la fecha de TODAS las frases de frases.json, benchmark_ft.json y benchmark_heldout.json."""
        total = 0
        for nombre in ("frases.json", "benchmark_ft.json", "benchmark_heldout.json"):
            ruta = RAIZ / nombre
            if not ruta.exists():
                continue
            data = json.loads(ruta.read_text(encoding="utf-8"))
            ref = data["metadata"]["fecha_referencia"]
            for f in data["frases"]:
                total += 1
                self.assertEqual(resolver_fecha_v2(f["texto"], ref), f["ground_truth"]["fecha"], f"{nombre} #{f['id']}: {f['texto']}")
        self.assertGreater(total, 0)


class TestHoraAmPm(unittest.TestCase):

    def test_ampm_generico(self):
        for frase, esperada in [
            ("Reunión el 10/09 a las 10 pm", "22:00"),
            ("Llamada a las 8 pm hora de Madrid", "20:00"),
            ("Webinar at 4pm", "16:00"),
            ("Pilates a las 7:15 am", "07:15"),
            ("Misa a las 7 pm", "19:00"),
            ("Vuelo a las 5 de la mañana", "05:00"),
        ]:
            self.assertEqual(hora_ampm_explicita(frase), esperada, frase)

    def test_sin_marca_devuelve_none(self):
        self.assertIsNone(hora_ampm_explicita("Reunión a las 10"))


class TestParticipantes(unittest.TestCase):

    def test_expande_rol_compuesto(self):
        f = "Entrevista con la candidata a diseñadora el 1 de octubre a las 11"
        self.assertEqual(expandir_participante(f, "candidata"), "candidata a diseñadora")
        self.assertEqual(expandir_participante("Café con el jefe de ventas el lunes", "jefe"), "jefe de ventas")

    def test_no_expande_nombres_propios_ni_horas_ni_nombres_completos(self):
        self.assertEqual(expandir_participante("Reunión con Valentina a las 5", "Valentina"), "Valentina")
        self.assertEqual(expandir_participante("Reunión con el cliente a las 5", "cliente"), "cliente")
        self.assertEqual(expandir_participante("Visita del cliente a domicilio el lunes", "cliente"), "cliente")
        self.assertEqual(expandir_participante("Tutoría con el tutor de práctica el viernes", "tutor de práctica"), "tutor de práctica")

    def test_participante_dudoso(self):
        self.assertTrue(participante_dudoso("Ensayo de la banda el 19/09", "banda"))
        self.assertTrue(participante_dudoso("Vacuna del perro el 25 de septiembre", "perro"))
        self.assertTrue(participante_dudoso("algo sin relación", "banda"))  # no aparece en la frase

    def test_participante_confiable(self):
        self.assertFalse(participante_dudoso("Reunión con Sofía y Martín el 16", "Martín"))
        self.assertFalse(participante_dudoso("Almuerzo con el cliente el lunes", "cliente"))
        self.assertFalse(participante_dudoso("Llamar a la abuela el domingo", "abuela"))
        self.assertFalse(participante_dudoso("Call with Priya and Tom on Wednesday", "Tom"))


if __name__ == "__main__":
    unittest.main()

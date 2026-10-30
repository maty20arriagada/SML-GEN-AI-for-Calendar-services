# -*- coding: utf-8 -*-
"""
test_tools.py - Tests unitarios para las herramientas deterministas de A3.
10 tests que verifican fechas, horas, duraciones y zonas horarias.
"""

import unittest

from deliverable3.tools import (
    calcular_duracion,
    extraer_recurrencia,
    extraer_zona_horaria,
    normalizar_hora,
    resolver_fecha,
)


class TestTools(unittest.TestCase):

    def test_resolver_fecha_formato_dmy(self):
        f = resolver_fecha("Reunión el 10/09 a las 10:00", "2026-09-01")
        self.assertEqual(f, "2026-09-10")

    def test_resolver_fecha_relativa(self):
        f = resolver_fecha("Junta mañana a las 5", "2026-09-01")
        self.assertEqual(f, "2026-09-02")

    def test_normalizar_hora_pm_explicito(self):
        # Soluciona la falla de la Frase 35 de D2
        h = normalizar_hora("10:00", "Reunión el 10/09 a las 10 pm")
        self.assertEqual(h, "22:00")

    def test_normalizar_hora_8pm(self):
        h = normalizar_hora("08:00", "Call a las 8 pm hora de Madrid")
        self.assertEqual(h, "20:00")

    def test_normalizar_hora_am(self):
        h = normalizar_hora(None, "Reunión a las 10 am")
        self.assertEqual(h, "10:00")

    def test_normalizar_hora_formato_24h(self):
        h = normalizar_hora(None, "Ensayo a las 18:00")
        self.assertEqual(h, "18:00")

    def test_normalizar_hora_a_las_tarde(self):
        h = normalizar_hora(None, "Junta a las 4")
        self.assertEqual(h, "16:00")

    def test_calcular_duracion_2_horas_media(self):
        # Corrige el error de D2 (que daba 90)
        d = calcular_duracion("Taller de 2 horas y media")
        self.assertEqual(d, 150)

    def test_calcular_duracion_1_hora(self):
        d = calcular_duracion("Reunión de 1 hora")
        self.assertEqual(d, 60)

    def test_extraer_zona_horaria_madrid(self):
        tz_madrid = extraer_zona_horaria("Llamada a las 8 pm hora de Madrid")
        self.assertEqual(tz_madrid, "Europe/Madrid")
        tz_chile = extraer_zona_horaria("Reunión en Santiago")
        self.assertEqual(tz_chile, "America/Santiago")


if __name__ == "__main__":
    unittest.main()

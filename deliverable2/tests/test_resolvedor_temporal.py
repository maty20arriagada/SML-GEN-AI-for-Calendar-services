# -*- coding: utf-8 -*-
"""
test_resolvedor_temporal.py -- Valida la herramienta determinista contra
Benchmark2 (45 frases con ground truth de D1).

Si estos tests pasan, la herramienta resuelve el 100% de las expresiones
temporales del benchmark y el campo 'fecha' del pipeline deja de depender
del modelo de lenguaje.

Ejecucion:  python -m unittest tests.test_resolvedor_temporal -v
"""

import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from pipeline.resolvedor_temporal import (  # noqa: E402
    FECHA_REF,
    analizar_temporal,
    resolver_fecha,
    resolver_hora_expr,
)

RUTA_BENCHMARK = os.path.join(RAIZ, "benchmark", "benchmark2.json")


def cargar():
    with open(RUTA_BENCHMARK, encoding="utf-8") as f:
        return json.load(f)["frases"]


class TestResolvedorTemporal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frases = cargar()

    def test_benchmark_completo(self):
        self.assertEqual(len(self.frases), 45)

    def test_fecha_contra_ground_truth(self):
        fallos = []
        for fr in self.frases:
            esperado = fr["ground_truth"].get("fecha")
            obtenido = resolver_fecha(fr["texto"], FECHA_REF)
            if obtenido != esperado:
                fallos.append("id=%s %r esperado=%s obtenido=%s"
                              % (fr["id"], fr["texto"], esperado, obtenido))
        self.assertEqual(fallos, [], "Fechas incorrectas:\n" + "\n".join(fallos))

    def test_hora_contra_ground_truth(self):
        fallos = []
        for fr in self.frases:
            esperado = fr["ground_truth"].get("hora_inicio")
            obtenido = analizar_temporal(fr["texto"], FECHA_REF)["hora_inicio"]
            if obtenido != esperado:
                fallos.append("id=%s %r esperado=%s obtenido=%s"
                              % (fr["id"], fr["texto"], esperado, obtenido))
        self.assertEqual(fallos, [], "Horas incorrectas:\n" + "\n".join(fallos))

    def test_expresiones_fuera_de_gramatica_devuelven_none(self):
        """La herramienta nunca inventa: fuera de gramatica => None."""
        casos = [
            "Reunión el próximo puente",
            "Nos vemos la semana pasada",
            "Junta de emergencia",
            "Llamada cuando puedas",
            "Reunión en el primer día hábil del mes",
        ]
        for texto in casos:
            self.assertIsNone(resolver_fecha(texto, FECHA_REF), texto)

    def test_no_confunde_numeros_de_otras_cosas(self):
        """'avísame 15 min antes', 'los 5 directores', 'salón 201' no son fechas/horas."""
        r = analizar_temporal("Junta el 8 de septiembre con los 5 directores", FECHA_REF)
        self.assertEqual(r["fecha"], "2026-09-08")
        self.assertIsNone(r["hora_inicio"])

        r = analizar_temporal("Llamada a las 14:30, avísame 15 min antes", FECHA_REF)
        self.assertEqual(r["hora_inicio"], "14:30")
        self.assertIsNone(r["fecha"])

        r = analizar_temporal("Workshop de 9 a 12 en el salón 201", FECHA_REF)
        self.assertEqual(r["hora_inicio"], "09:00")
        self.assertIsNone(r["fecha"])

    def test_hora_expr_aislada(self):
        self.assertEqual(resolver_hora_expr("a las 4"), "16:00")
        self.assertEqual(resolver_hora_expr("10am"), "10:00")
        self.assertEqual(resolver_hora_expr("3pm"), "15:00")
        self.assertEqual(resolver_hora_expr("a las 3 de la tarde"), "15:00")
        self.assertEqual(resolver_hora_expr("8 de la mañana"), "08:00")
        self.assertEqual(resolver_hora_expr("15:30"), "15:30")
        self.assertIsNone(resolver_hora_expr(""))

    def test_referencia_alternativa(self):
        """El resolvedor es una funcion pura de la fecha de referencia."""
        self.assertEqual(resolver_fecha("mañana", "2026-09-01"), "2026-09-02")
        self.assertEqual(resolver_fecha("mañana", "2026-09-30"), "2026-10-01")
        self.assertEqual(resolver_fecha("el lunes", "2026-09-02"), "2026-09-07")
        self.assertEqual(resolver_fecha("pasado mañana", "2026-09-01"), "2026-09-03")


if __name__ == "__main__":
    unittest.main(verbosity=2)

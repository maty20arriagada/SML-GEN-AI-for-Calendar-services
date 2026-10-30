# -*- coding: utf-8 -*-
"""
test_motor_cache.py - El caché evita repetir llamadas idénticas y no mezcla prompts distintos.
"""

import json
import tempfile
import unittest
from pathlib import Path

from deliverable3.agentes import BRAZOS
from deliverable3.grafo import ejecutar
from deliverable3.motor_cache import MotorConCache


class MotorContador:
    modelo = "atributo-del-motor-real"

    def __init__(self):
        self.n = 0

    def generar(self, mensajes, **kw):
        self.n += 1
        u = [m for m in mensajes if m["role"] == "user"][-1]["content"]
        if u.startswith("Evalúa"):
            return json.dumps({"es_evento": True})
        return json.dumps({"titulo": "x", "hora_inicio": "10:00", "duracion_minutos": None,
                           "participantes": [], "ubicacion": None, "recordatorio_minutos": None})


class TestMotorConCache(unittest.TestCase):

    def test_misma_llamada_se_sirve_del_cache(self):
        base = MotorContador()
        m = MotorConCache(base)
        msg = [{"role": "user", "content": "hola"}]
        a, b = m.generar(msg), m.generar(msg)
        self.assertEqual(a, b)
        self.assertEqual((base.n, m.llamadas, m.aciertos), (1, 1, 1))

    def test_prompts_distintos_no_se_mezclan(self):
        base = MotorContador()
        m = MotorConCache(base)
        m.generar([{"role": "user", "content": "uno"}])
        m.generar([{"role": "user", "content": "dos"}])
        self.assertEqual(base.n, 2)

    def test_pasa_atributos_del_motor_real(self):
        self.assertEqual(MotorConCache(MotorContador()).modelo, "atributo-del-motor-real")

    def test_brazos_comparten_a1_y_a2(self):
        base = MotorContador()
        m = MotorConCache(base)
        frase = "Reunión con Ana el 10/09 a las 10:00"
        r2, _ = ejecutar(frase, cfg=BRAZOS["E2"], motor=m, fecha_ref="2026-09-01")
        llamadas_e2 = base.n
        r3, _ = ejecutar(frase, cfg=BRAZOS["E3a"], motor=m, fecha_ref="2026-09-01")
        self.assertEqual(llamadas_e2, 2)      # A1 + A2
        self.assertEqual(base.n, 2)           # E3a no volvió a llamar al modelo
        self.assertEqual(r2["fecha"], r3["fecha"])

    def test_persistencia_en_disco(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "cache.json"
            m1 = MotorConCache(MotorContador(), ruta)
            m1.generar([{"role": "user", "content": "persistir"}])
            m1.guardar()
            base2 = MotorContador()
            m2 = MotorConCache(base2, ruta)
            m2.generar([{"role": "user", "content": "persistir"}])
            self.assertEqual(base2.n, 0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
test_ablaciones.py - Configuración de los brazos experimentales:
E0 (prompt directo), E1 (solución D2), E4 (sistema completo) y E4T1..E4T5 (quitando una técnica a la vez).
Sin GPU.
"""

import unittest

from deliverable3.agentes import BRAZOS


class TestAblaciones(unittest.TestCase):

    def test_brazo_e0_directo(self):
        self.assertEqual(BRAZOS["E0"]["version"], "v0")

    def test_brazo_e1_config(self):
        self.assertEqual(BRAZOS["E1"]["modo"], "baseline")

    def test_brazo_e4_completo(self):
        e4 = BRAZOS["E4"]
        self.assertEqual(e4["version"], "v4")
        self.assertTrue(e4["a1"])
        self.assertTrue(e4["a4"])
        self.assertEqual(e4["a3"], "react")
        self.assertEqual(e4["a4_prompt"], "a4_agente_v1.txt")

    def test_cada_ablacion_quita_una_tecnica(self):
        e4 = BRAZOS["E4"]
        cambios = {
            "E4T1": {"a3": "sin_tools"},
            "E4T2": {"a4_prompt": "a4_sin_fewshot_v1.txt"},
            "E4T3": {"a4_prompt": "a4_sin_cot_v1.txt"},
            "E4T4": {"a4": False},
            "E4T5": {"a1": False},
        }
        for brazo, cambio in cambios.items():
            cfg = BRAZOS[brazo]
            for clave in ("version", "a1", "a3", "a4"):
                esperado = cambio.get(clave, e4[clave])
                self.assertEqual(cfg[clave], esperado, f"{brazo}.{clave}")
            if cfg["a4"]:
                self.assertEqual(cfg["a4_prompt"], cambio.get("a4_prompt", e4["a4_prompt"]), brazo)

    def test_lista_brazos_completa(self):
        esperados = {"E0", "E1", "E4", "E4T1", "E4T2", "E4T3", "E4T4", "E4T5"}
        self.assertEqual(set(BRAZOS.keys()), esperados)


if __name__ == "__main__":
    unittest.main()

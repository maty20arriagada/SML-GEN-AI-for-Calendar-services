# -*- coding: utf-8 -*-
"""
test_ablaciones.py - Tests unitarios para las configuraciones de los 7 brazos experimentales:
E1 (baseline), E2 (sistema completo), E2T1..E2T4 (ablaciones de técnicas) y E2W (gramática).
8 tests sin GPU.
"""

import unittest

from deliverable3.agentes import BRAZOS


class TestAblaciones(unittest.TestCase):

    def test_brazo_e1_config(self):
        self.assertIn("E1", BRAZOS)
        self.assertEqual(BRAZOS["E1"]["modo"], "baseline")

    def test_brazo_e2_completo(self):
        e2 = BRAZOS["E2"]
        self.assertTrue(e2["a1"])
        self.assertTrue(e2["a2"])
        self.assertTrue(e2["a3"])
        self.assertTrue(e2["a4"])
        self.assertTrue(e2["t1_tools"])
        self.assertTrue(e2["t2_fewshot"])
        self.assertTrue(e2["t3_cot"])
        self.assertTrue(e2["t4_roles"])
        self.assertEqual(e2["gramatica"], "v2")

    def test_brazo_e2t1_sin_tools(self):
        # T1: Dynamic tool calling desactivado
        e2t1 = BRAZOS["E2T1"]
        self.assertFalse(e2t1["t1_tools"])
        self.assertTrue(e2t1["t2_fewshot"])
        self.assertTrue(e2t1["t3_cot"])

    def test_brazo_e2t2_sin_fewshot(self):
        # T2: Few-shot contrastivo desactivado
        e2t2 = BRAZOS["E2T2"]
        self.assertTrue(e2t2["t1_tools"])
        self.assertFalse(e2t2["t2_fewshot"])
        self.assertTrue(e2t2["t3_cot"])

    def test_brazo_e2t3_sin_cot(self):
        # T3: Chain-of-Thought / rúbrica desactivado
        e2t3 = BRAZOS["E2T3"]
        self.assertTrue(e2t3["t1_tools"])
        self.assertTrue(e2t3["t2_fewshot"])
        self.assertFalse(e2t3["t3_cot"])

    def test_brazo_e2t4_sin_roles(self):
        # T4: Descomposición modular / bypass de A4
        e2t4 = BRAZOS["E2T4"]
        self.assertFalse(e2t4["a4"])
        self.assertFalse(e2t4["t4_roles"])

    def test_brazo_e2w_gramatica_v1(self):
        # Aporte de la gramática v2 vs v1 congelada
        e2w = BRAZOS["E2W"]
        self.assertEqual(e2w["gramatica"], "v1")

    def test_lista_brazos_completa(self):
        esperados = {"E1", "E2", "E2W", "E2T1", "E2T2", "E2T3", "E2T4", "E3", "E3a", "E3b", "E3c",
                     "E0", "E4", "E4T1", "E4T2", "E4T3", "E4T4", "E4T5"}
        self.assertEqual(set(BRAZOS.keys()), esperados)


if __name__ == "__main__":
    unittest.main()

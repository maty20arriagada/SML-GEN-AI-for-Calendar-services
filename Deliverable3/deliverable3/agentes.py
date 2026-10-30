# -*- coding: utf-8 -*-
"""
agentes.py - Base común de los agentes, extractor del baseline D2 (E1) y configuración de brazos experimentales.

Los agentes del sistema (A1 Triage, A2 Extractor, A3 Temporal, A4 Verificador) están en agentes_v3.py;
el orquestador, en grafo_v4.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from deliverable3.trazas import TrazaEjecucion

DIR_PROMPTS = Path(__file__).resolve().parent / "prompts"


def _cargar_prompt(nombre: str) -> str:
    p = DIR_PROMPTS / nombre
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _extraer_json(texto: str) -> dict:
    if not texto:
        return {}
    t = texto.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


class AgenteBase:
    """Clase base para todos los agentes del sistema."""

    def __init__(self, nombre: str, prompt_file: str, motor: Any):
        self.nombre = nombre
        self.prompt_file = prompt_file
        self.motor = motor
        self.prompt = _cargar_prompt(prompt_file)

    def invocar_modelo(self, user_content: str) -> str:
        mensajes = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": user_content},
        ]
        if hasattr(self.motor, "generar"):
            return self.motor.generar(mensajes)
        return "{}"


class AgenteExtractor(AgenteBase):
    """Extractor semántico de la solución D2 (LoRA, 6 campos semánticos). Lo usa el brazo E1."""

    def __init__(self, motor: Any, prompt_file: str = "a2_extractor_v1.txt"):
        super().__init__("A2_Extractor", prompt_file, motor)

    def extraer(self, frase: str, traza: TrazaEjecucion) -> Dict[str, Any]:
        resp = self.invocar_modelo(f'Frase: "{frase}"')
        data = _extraer_json(resp)
        if not data:
            data = {
                "titulo": frase,
                "hora_inicio": None,
                "duracion_minutos": None,
                "participantes": [],
                "ubicacion": None,
                "recordatorio_minutos": None,
            }
        salida_log = json.dumps(data, ensure_ascii=False)
        traza.registrar_agente(self.nombre, salida_log)
        return data


BRAZOS = {
    "E0": {"nombre": "directo_modelo_base", "version": "v0"},
    "E1": {
        "nombre": "baseline_d2",
        "modo": "baseline",
    },
    "E4": {
        "nombre": "agentes_completo",
        "version": "v4", "a1": True, "a3": "react", "a4": True, "a4_prompt": "a4_agente_v1.txt",
    },
    "E4T1": {   # sin T1: A3 sin herramientas
        "nombre": "sin_t1_herramientas",
        "version": "v4", "a1": True, "a3": "sin_tools", "a4": True, "a4_prompt": "a4_agente_v1.txt",
    },
    "E4T2": {   # sin T2: A4 sin ejemplos contrastivos
        "nombre": "sin_t2_fewshot",
        "version": "v4", "a1": True, "a3": "react", "a4": True, "a4_prompt": "a4_sin_fewshot_v1.txt",
    },
    "E4T3": {   # sin T3: A4 sin rúbrica / razonamiento
        "nombre": "sin_t3_cot",
        "version": "v4", "a1": True, "a3": "react", "a4": True, "a4_prompt": "a4_sin_cot_v1.txt",
    },
    "E4T4": {   # sin T4: sin verificador ni bucle A4->A3
        "nombre": "sin_t4_verificador",
        "version": "v4", "a1": True, "a3": "react", "a4": False,
    },
    "E4T5": {   # sin T5: sin compuerta de triage
        "nombre": "sin_t5_triage",
        "version": "v4", "a1": False, "a3": "react", "a4": True, "a4_prompt": "a4_agente_v1.txt",
    },
}

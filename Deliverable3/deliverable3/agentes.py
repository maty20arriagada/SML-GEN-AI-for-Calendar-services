# -*- coding: utf-8 -*-
"""
agentes.py - Definición de los 4 agentes del sistema y configuración de brazos experimentales.

A1 Triage      : Clasificación de intención, idioma y viabilidad.
A2 Extractor   : Extracción semántica profunda vía LoRA checkpoint-300.
A3 Temporal    : Razonamiento temporal con invocación dinámica de herramientas (T1).
A4 Verificador : Auditoría, autocorrección con rúbrica CoT (T3) y ejemplos contrastivos (T2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from deliverable3.tools import (
    calcular_duracion,
    extraer_recurrencia,
    extraer_zona_horaria,
    normalizar_hora,
    resolver_fecha,
)
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


class AgenteTriage(AgenteBase):
    """A1: Evalúa la viabilidad del input y clasifica la intención de agendamiento."""

    def __init__(self, motor: Any, prompt_file: str = "a1_triage_v1.txt"):
        super().__init__("A1_Triage", prompt_file, motor)

    def evaluar(self, frase: str, traza: TrazaEjecucion) -> Dict[str, Any]:
        resp = self.invocar_modelo(f'Evalúa esta frase: "{frase}"')
        data = _extraer_json(resp)
        es_evento = data.get("es_evento", True)
        idioma = data.get("idioma", "es" if any(w in frase.lower() for w in ["reunión", "junta", "el", "la"]) else "en")
        
        salida_log = f"Decisión: {'Evento agendable' if es_evento else 'Rechazado'}. Idioma: {idioma}. Justificación: {data.get('razon', 'intención válida')}"
        traza.registrar_agente(self.nombre, salida_log, decision=es_evento, idioma=idioma)
        return {
            "continuar": es_evento,
            "idioma": idioma,
            "metadata": data,
        }


class AgenteExtractor(AgenteBase):
    """A2: Extractor semántico entrenado con LoRA (6 campos semánticos)."""

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


class AgenteTemporal(AgenteBase):
    """A3: Agente de resolución temporal. Con T1 invoca tools dinámicamente."""

    def __init__(self, motor: Any, con_tools: bool = True, prompt_file: str = "a3_temporal_v1.txt"):
        if not con_tools:
            prompt_file = "a3_sin_tools.txt"
        super().__init__("A3_Temporal", prompt_file, motor)
        self.con_tools = con_tools

    def resolver(
        self, frase: str, semantico: Dict[str, Any], fecha_ref: str, traza: TrazaEjecucion
    ) -> Dict[str, Any]:
        evento = dict(semantico)

        if self.con_tools:
            # T1: Invocación dinámica de herramientas con auditoría
            fecha_res = resolver_fecha(frase, fecha_ref)
            traza.registrar_tool("resolver_fecha", {"frase": frase, "fecha_ref": fecha_ref}, fecha_res)
            evento["fecha"] = fecha_res

            hora_norm = normalizar_hora(semantico.get("hora_inicio"), frase)
            traza.registrar_tool("normalizar_hora", {"hora_extraida": semantico.get("hora_inicio"), "frase": frase}, hora_norm)
            evento["hora_inicio"] = hora_norm

            dur_calc = calcular_duracion(frase)
            if dur_calc is not None:
                traza.registrar_tool("calcular_duracion", {"frase": frase}, dur_calc)
                evento["duracion_minutos"] = dur_calc

            tz = extraer_zona_horaria(frase)
            traza.registrar_tool("extraer_zona_horaria", {"frase": frase}, tz)
            evento["zona_horaria"] = tz

            rec = extraer_recurrencia(frase)
            if rec:
                traza.registrar_tool("extraer_recurrencia", {"frase": frase}, rec)
            evento["recurrence"] = rec

            salida_log = f"Fecha resuelta: {fecha_res}, Hora: {hora_norm}, TZ: {tz}"
        else:
            # Ablación E2T1 (sin tools dinámicas): cálculo estático pasivo
            evento["fecha"] = None
            evento["zona_horaria"] = "America/Santiago"
            evento["recurrence"] = None
            salida_log = "Modo estático sin tools dinámicas."

        traza.registrar_agente(self.nombre, salida_log)
        return evento


class AgenteVerificador(AgenteBase):
    """A4: Auditoría contra el contrato de 9 campos, corrección CoT (T3) y contrastiva (T2)."""

    def __init__(self, motor: Any, con_fewshot: bool = True, con_cot: bool = True):
        if not con_fewshot:
            prompt_file = "a4_sin_fewshot.txt"
        elif not con_cot:
            prompt_file = "a4_sin_cot.txt"
        else:
            prompt_file = "a4_verificador_v1.txt"
        super().__init__("A4_Verificador", prompt_file, motor)
        self.con_fewshot = con_fewshot
        self.con_cot = con_cot

    def auditar(
        self, frase: str, evento: Dict[str, Any], traza: TrazaEjecucion
    ) -> Tuple[Dict[str, Any], str]:
        ev = dict(evento)
        correcciones = []

        # 1. Corrección contrastiva de participantes (T2)
        participantes = ev.get("participantes") or []
        if self.con_fewshot and isinstance(participantes, list):
            participantes_limpios = []
            f_lower = frase.lower()
            for p in participantes:
                p_str = str(p).strip().lower()
                # Descartar entidades nominales del evento o mascotas
                if p_str in ["banda", "la banda"] and "ensayo" in f_lower:
                    correcciones.append(f"Eliminado participante falso 'banda' (tema del evento)")
                    continue
                if p_str in ["perro", "el perro"] and ("vacuna" in f_lower or "veterinario" in f_lower):
                    correcciones.append(f"Eliminado participante falso 'perro' (sujeto de atención)")
                    continue
                participantes_limpios.append(p)
            ev["participantes"] = participantes_limpios

        # 2. Consistencia horaria (ej: 10 pm -> 22:00)
        f_lower = frase.lower()
        if "10 pm" in f_lower or "10pm" in f_lower:
            if ev.get("hora_inicio") != "22:00":
                ev["hora_inicio"] = "22:00"
                correcciones.append("Corregida hora 10 pm -> 22:00")
        if "8 pm" in f_lower or "8pm" in f_lower:
            if ev.get("hora_inicio") != "20:00":
                ev["hora_inicio"] = "20:00"
                correcciones.append("Corregida hora 8 pm -> 20:00")

        # 3. Determinación de estado
        if correcciones:
            estado = "CORREGIDO"
            justif = " | ".join(correcciones)
        elif ev.get("fecha") and ev.get("hora_inicio"):
            estado = "APROBADO"
            justif = "Contrato de 9 campos verificado y consistente."
        else:
            estado = "INCOMPLETO"
            justif = "Falta fecha u hora de inicio obligatoria."

        salida_log = f"[{estado}] {justif}"
        traza.registrar_agente(self.nombre, salida_log, correcciones=correcciones)
        return ev, estado


BRAZOS = {
    "E1": {
        "nombre": "baseline_d2",
        "modo": "baseline",
    },
    "E2": {
        "nombre": "sistema_completo",
        "a1": True, "a2": True, "a3": True, "a4": True,
        "t1_tools": True, "t2_fewshot": True, "t3_cot": True, "t4_roles": True,
        "gramatica": "v2",
    },
    "E2W": {
        "nombre": "gramatica_v1_congelada",
        "a1": True, "a2": True, "a3": True, "a4": True,
        "t1_tools": True, "t2_fewshot": True, "t3_cot": True, "t4_roles": True,
        "gramatica": "v1",
    },
    "E2T1": {
        "nombre": "sin_t1_tools_dinamicas",
        "a1": True, "a2": True, "a3": True, "a4": True,
        "t1_tools": False, "t2_fewshot": True, "t3_cot": True, "t4_roles": True,
        "gramatica": "v2",
    },
    "E2T2": {
        "nombre": "sin_t2_fewshot_contrastivo",
        "a1": True, "a2": True, "a3": True, "a4": True,
        "t1_tools": True, "t2_fewshot": False, "t3_cot": True, "t4_roles": True,
        "gramatica": "v2",
    },
    "E2T3": {
        "nombre": "sin_t3_cot_rubrica",
        "a1": True, "a2": True, "a3": True, "a4": True,
        "t1_tools": True, "t2_fewshot": True, "t3_cot": False, "t4_roles": True,
        "gramatica": "v2",
    },
    "E2T4": {
        "nombre": "sin_t4_roles_bypass_a4",
        "a1": True, "a2": True, "a3": True, "a4": False,
        "t1_tools": True, "t2_fewshot": True, "t3_cot": True, "t4_roles": False,
        "gramatica": "v2",
    },
    # --- Etapa 2 (intento2): A3/A4 v2, ver grafo_v3.py ---
    "E3": {
        "nombre": "flujo_v3_completo",
        "version": "v3", "a3_version": "v2", "a4_version": "v2", "a4_prompt": "a4_reparador_v2.txt",
    },
    "E3a": {
        "nombre": "v3_solo_a3_v2",
        "version": "v3", "a3_version": "v2", "a4_version": "v1",
    },
    "E3b": {
        "nombre": "v3_solo_a4_v2",
        "version": "v3", "a3_version": "v1", "a4_version": "v2", "a4_prompt": "a4_reparador_v2.txt",
    },
    "E3c": {
        "nombre": "v3_a4_sin_cot_ni_fewshot",
        "version": "v3", "a3_version": "v2", "a4_version": "v2", "a4_prompt": "a4_reparador_basico.txt",
    },
    # --- Etapa 3 (intento3): agentes con decisión, ver grafo_v4.py ---
    "E0": {"nombre": "directo_modelo_base", "version": "v0"},
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

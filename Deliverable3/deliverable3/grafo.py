# -*- coding: utf-8 -*-
"""
grafo.py - Motor de ejecución del grafo de agentes de Deliverable 3.
Orquesta el flujo: A1 (Triage) -> A2 (Extractor) -> A3 (Temporal) -> A4 (Verificador).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

from deliverable3.agentes import (
    BRAZOS,
    AgenteExtractor,
    AgenteTemporal,
    AgenteTriage,
    AgenteVerificador,
)
from deliverable3.tools import resolver_fecha
from deliverable3.trazas import TrazaEjecucion

CAMPOS_CONTRATO_9 = [
    "titulo", "fecha", "hora_inicio", "duracion_minutos",
    "participantes", "ubicacion", "recordatorio_minutos",
    "zona_horaria", "recurrence"
]


def _completar_contrato(evento: Dict[str, Any]) -> Dict[str, Any]:
    """Asegura que todos los 9 campos del contrato existan con tipos correctos."""
    res = {}
    for c in CAMPOS_CONTRATO_9:
        if c == "participantes":
            res[c] = list(evento.get(c) or [])
        elif c == "zona_horaria":
            res[c] = evento.get(c) or "America/Santiago"
        elif c in ("fecha", "hora_inicio", "ubicacion", "recurrence", "titulo"):
            val = evento.get(c)
            res[c] = str(val).strip() if val is not None and str(val).strip() not in ("", "null", "None") else None
        elif c in ("duracion_minutos", "recordatorio_minutos"):
            val = evento.get(c)
            try:
                res[c] = int(val) if val is not None else None
            except (ValueError, TypeError):
                res[c] = None
        else:
            res[c] = evento.get(c, None)
    return res


def ejecutar(
    frase: str,
    cfg: Dict[str, Any] | None = None,
    motor: Any = None,
    fecha_ref: str = "2026-09-01",
) -> Tuple[Dict[str, Any], TrazaEjecucion]:
    """
    Ejecuta el sistema multi-agente sobre una frase en lenguaje natural.
    Devuelve (evento_9_campos, traza_ejecucion).
    """
    if cfg is None:
        cfg = BRAZOS["E2"]

    # Brazos E4* y E0 (etapa 3): agentes con decisión en grafo_v4.py
    if cfg.get("version") == "v4":
        from deliverable3.grafo_v4 import ejecutar_v4
        return ejecutar_v4(frase, cfg, motor, fecha_ref, _completar_contrato)
    if cfg.get("version") == "v0":
        from deliverable3.grafo_v4 import ejecutar_directo
        return ejecutar_directo(frase, cfg, motor, fecha_ref, _completar_contrato)

    # Brazos E3* (etapa 2): flujo con A3/A4 v2 en grafo_v3.py
    if cfg.get("version") == "v3":
        from deliverable3.grafo_v3 import ejecutar_v3
        return ejecutar_v3(frase, cfg, motor, fecha_ref, _completar_contrato)

    traza = TrazaEjecucion(frase)

    # -------------------------------------------------------------
    # Brazo E1: Baseline D2 (solución D2: prompt semántico + tool fecha)
    # -------------------------------------------------------------
    if cfg.get("modo") == "baseline":
        a2 = AgenteExtractor(motor)
        sem = a2.extraer(frase, traza)
        evento = dict(sem)
        f_res = resolver_fecha(frase, fecha_ref)
        evento["fecha"] = f_res
        traza.registrar_tool("resolver_fecha", {"frase": frase, "fecha_ref": fecha_ref}, f_res)
        evento["zona_horaria"] = "America/Santiago"
        evento["recurrence"] = None
        evento_final = _completar_contrato(evento)
        traza.registrar_evento("BASELINE_D2", evento_final)
        return evento_final, traza

    # -------------------------------------------------------------
    # Brazos E2 y ablaciones (Sistema Multi-Agente)
    # -------------------------------------------------------------
    
    # 1. A1 - Triage
    a1 = AgenteTriage(motor)
    triage_info = a1.evaluar(frase, traza)
    if not triage_info.get("continuar", True):
        evento_vacio = _completar_contrato({})
        traza.registrar_evento("RECHAZADO", evento_vacio)
        return evento_vacio, traza

    # 2. A2 - Extractor (LoRA)
    a2 = AgenteExtractor(motor)
    semantico = a2.extraer(frase, traza)

    # 3. A3 - Temporal (con tools dinámicas T1)
    con_tools = cfg.get("t1_tools", True)
    a3 = AgenteTemporal(motor, con_tools=con_tools)
    evento_temp = a3.resolver(frase, semantico, fecha_ref, traza)

    # 4. A4 - Verificador y Crítico (T2 few-shot, T3 CoT)
    usar_a4 = cfg.get("a4", True)
    if usar_a4:
        con_fewshot = cfg.get("t2_fewshot", True)
        con_cot = cfg.get("t3_cot", True)
        a4 = AgenteVerificador(motor, con_fewshot=con_fewshot, con_cot=con_cot)
        evento_verif, estado = a4.auditar(frase, evento_temp, traza)
    else:
        # Ablación E2T4 (sin roles / bypass de A4)
        evento_verif = evento_temp
        estado = "APROBADO" if evento_verif.get("fecha") else "INCOMPLETO"
        traza.registrar_agente("Bypass_A4", "A4 omitido por ablación E2T4")

    # Adaptación de gramática (E2W vs E2)
    if cfg.get("gramatica") == "v1":
        # Gramática v1 congelada de D2
        pass

    evento_final = _completar_contrato(evento_verif)
    traza.registrar_evento(estado, evento_final)
    return evento_final, traza

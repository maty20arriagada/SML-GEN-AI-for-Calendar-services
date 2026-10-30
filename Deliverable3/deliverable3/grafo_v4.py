# -*- coding: utf-8 -*-
"""
grafo_v4.py - Sistema de agentes de la etapa 3 (brazos E4*). grafo.py delega aquí si cfg["version"] == "v4".
Además contiene el brazo E0 (prompt directo, sin agentes) para medir todo sobre los mismos inputs.

Grafo (las flechas llevan lo que se pasa; ver el README):
  Entrada -> A1 --continuar--> A2 -> A3 <-> herramientas -> A4 --aprobar/corregir--> SALIDA
                |                          ^                 |
             rechazar -> FIN               +--devolver_a_A3--+   (máx. 1 vuelta)

cfg: a1 (bool), a3 ("react" | "sin_tools"), a4 (bool), a4_prompt (archivo de prompts/).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from deliverable3.agentes_v3 import (
    AgenteExtractorV3,
    AgenteTemporalReAct,
    AgenteTemporalSinTools,
    AgenteTriageV3,
    AgenteVerificadorAgente,
)
from deliverable3.trazas import TrazaEjecucion

MAX_VUELTAS_A4 = 2   # 1 devolución a A3 como máximo


def ejecutar_v4(frase: str, cfg: Dict[str, Any], motor: Any, fecha_ref: str, completar_contrato) -> Tuple[Dict[str, Any], TrazaEjecucion]:
    traza = TrazaEjecucion(frase)

    # A1 -- compuerta de triage (T5)
    if cfg.get("a1", True):
        if not AgenteTriageV3(motor).evaluar(frase, traza, fecha_ref)["continuar"]:
            vacio = completar_contrato({})
            traza.registrar_evento("RECHAZADO", vacio)
            return vacio, traza
    else:
        traza.registrar_mensaje("Entrada", "A2", frase)

    # A2 -- extracción semántica (LoRA)
    borrador = AgenteExtractorV3(motor).extraer(frase, traza)

    # A3 -- agente temporal con herramientas (T1) o sin ellas (ablación)
    if cfg.get("a3", "react") == "react":
        a3 = AgenteTemporalReAct(motor)
    else:
        a3 = AgenteTemporalSinTools(motor)
    evento = a3.resolver(frase, borrador, fecha_ref, traza)

    # A4 -- verificador con bucle hacia A3 (T2, T3, T4)
    estado = "SIN_A4"
    if cfg.get("a4", True):
        a4 = AgenteVerificadorAgente(motor, prompt_file=cfg.get("a4_prompt", "a4_agente_v1.txt"))
        for vuelta in range(1, MAX_VUELTAS_A4 + 1):
            evento, accion, motivo = a4.revisar(frase, evento, fecha_ref, traza, vuelta=vuelta)
            if accion == "devolver_a_A3" and vuelta < MAX_VUELTAS_A4:
                evento = a3.resolver(frase, borrador, fecha_ref, traza, objecion=motivo)
                continue
            estado = {"aprobar": "APROBADO", "corregir": "CORREGIDO"}.get(accion, "APROBADO")
            break
        if not (evento.get("fecha") and evento.get("hora_inicio")):
            estado = "INCOMPLETO"

    final = completar_contrato(evento)
    traza.registrar_evento(estado, final)
    return final, traza


def ejecutar_directo(frase: str, cfg: Dict[str, Any], motor: Any, fecha_ref: str, completar_contrato) -> Tuple[Dict[str, Any], TrazaEjecucion]:
    """E0: prompt directo del D1/D2 (brazo A de D2), una sola llamada al modelo base, sin herramientas ni agentes."""
    from pipeline.pipeline import CalendarPipeline   # deliverable2/ está en sys.path (ver tools.py)

    traza = TrazaEjecucion(frase)
    traza.registrar_mensaje("Entrada", "modelo_base", frase)
    evento = CalendarPipeline(motor, fecha_ref).baseline(frase)
    final = completar_contrato(CalendarPipeline.solo_contrato(evento))
    traza.registrar_mensaje("modelo_base", "SALIDA", final, error_modelo=evento.get("_error_modelo"))
    traza.registrar_evento("DIRECTO", final)
    return final, traza

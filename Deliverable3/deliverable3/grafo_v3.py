# -*- coding: utf-8 -*-
"""
grafo_v3.py - Flujo de la etapa 2 (brazos E3*). grafo.py delega aquí cuando cfg["version"] == "v3".

A1 Triage -> A2 Extractor (igual que E2) -> A3 (v1 o v2) -> A4 (v1 o v2) -> contrato de 9 campos.
`a3_version` y `a4_version` eligen la variante de cada agente; así E3a/E3b aíslan el aporte de cada uno.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from deliverable3.agentes import (
    AgenteExtractor,
    AgenteTemporal,
    AgenteTriage,
    AgenteVerificador,
)
from deliverable3.agentes_v2 import AgenteTemporalV2, AgenteVerificadorV2
from deliverable3.trazas import TrazaEjecucion


def ejecutar_v3(
    frase: str, cfg: Dict[str, Any], motor: Any, fecha_ref: str, completar_contrato
) -> Tuple[Dict[str, Any], TrazaEjecucion]:
    traza = TrazaEjecucion(frase)

    triage = AgenteTriage(motor).evaluar(frase, traza)
    if not triage.get("continuar", True):
        vacio = completar_contrato({})
        traza.registrar_evento("RECHAZADO", vacio)
        return vacio, traza

    semantico = AgenteExtractor(motor).extraer(frase, traza)

    if cfg.get("a3_version") == "v2":
        a3 = AgenteTemporalV2(motor)
    else:
        a3 = AgenteTemporal(motor, con_tools=True)
    evento = a3.resolver(frase, semantico, fecha_ref, traza)

    if cfg.get("a4_version") == "v2":
        a4 = AgenteVerificadorV2(motor, prompt_file=cfg.get("a4_prompt", "a4_reparador_v2.txt"))
        evento, estado = a4.auditar(frase, evento, traza, fecha_ref)
    else:
        evento, estado = AgenteVerificador(motor, con_fewshot=True, con_cot=True).auditar(frase, evento, traza)

    final = completar_contrato(evento)
    traza.registrar_evento(estado, final)
    return final, traza

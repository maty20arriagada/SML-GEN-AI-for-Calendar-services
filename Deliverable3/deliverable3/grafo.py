# -*- coding: utf-8 -*-
"""
grafo.py - Punto de entrada del sistema de Deliverable 3.
Según cfg["version"]: "v4" -> sistema de agentes (grafo_v4.ejecutar_v4), "v0" -> prompt directo E0;
cfg["modo"] == "baseline" -> solución D2 (E1).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from deliverable3.agentes import BRAZOS, AgenteExtractor
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
    Ejecuta un brazo sobre una frase en lenguaje natural.
    Devuelve (evento_9_campos, traza_ejecucion).
    """
    if cfg is None:
        cfg = BRAZOS["E4"]

    # Brazos E4* y E0: agentes con decisión en grafo_v4.py
    if cfg.get("version") == "v4":
        from deliverable3.grafo_v4 import ejecutar_v4
        return ejecutar_v4(frase, cfg, motor, fecha_ref, _completar_contrato)
    if cfg.get("version") == "v0":
        from deliverable3.grafo_v4 import ejecutar_directo
        return ejecutar_directo(frase, cfg, motor, fecha_ref, _completar_contrato)

    if cfg.get("modo") != "baseline":
        raise ValueError(f"brazo desconocido: {cfg}")

    # -------------------------------------------------------------
    # Brazo E1: Baseline D2 (solución D2: prompt semántico + tool fecha)
    # -------------------------------------------------------------
    traza = TrazaEjecucion(frase)
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

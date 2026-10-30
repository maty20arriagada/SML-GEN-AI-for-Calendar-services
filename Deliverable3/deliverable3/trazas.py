# -*- coding: utf-8 -*-
"""
trazas.py - Estructura de trazas de ejecución inter-agente para Deliverable 3.
Permite auditar mensajes entre agentes, llamadas a tools y eventos finales en JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class TrazaEjecucion:
    """Registra los turnos de agentes, invocaciones a tools y estados del evento."""

    def __init__(self, frase: str = ""):
        self.frase = frase
        self.turnos: List[Dict[str, Any]] = []

    def registrar_agente(self, agente: str, salida: str, **kwargs) -> None:
        turno = {
            "tipo": "agente",
            "agente": agente,
            "salida": salida,
        }
        if kwargs:
            turno.update(kwargs)
        self.turnos.append(turno)

    def registrar_tool(self, tool: str, args: Any, resultado: Any) -> None:
        self.turnos.append({
            "tipo": "tool",
            "tool": tool,
            "args": args,
            "resultado": resultado,
        })

    def registrar_mensaje(self, de: str, a: str, contenido: Any, **kwargs) -> None:
        """Mensaje que viaja entre dos nodos del grafo (agente -> agente, agente <-> herramienta)."""
        turno = {"tipo": "mensaje", "de": de, "a": a, "contenido": contenido}
        if kwargs:
            turno.update(kwargs)
        self.turnos.append(turno)

    def a_dict(self) -> Dict[str, Any]:
        return {"frase": self.frase, "turnos": self.turnos}

    def registrar_evento(self, estado: str, evento: Dict[str, Any]) -> None:
        self.turnos.append({
            "tipo": "evento",
            "estado": estado,
            "evento": evento,
        })

    def guardar(self, ruta: str | Path) -> str:
        """Guarda los turnos en formato JSON Lines (JSONL). Crea directorios si no existen."""
        p = Path(ruta)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for turno in self.turnos:
                f.write(json.dumps(turno, ensure_ascii=False) + "\n")
        return str(p)

    def __repr__(self) -> str:
        return f"<TrazaEjecucion turnos={len(self.turnos)} frase={self.frase[:30]!r}>"

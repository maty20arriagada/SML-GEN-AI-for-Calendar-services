# -*- coding: utf-8 -*-
"""
pipeline.py -- Sistema de agendamiento desde lenguaje natural.

Brazos del sistema (misma tarea, misma definicion de correccion):

  A  baseline        prompt directo          -> fecha del modelo   (baseline D1)
  B  estructurado    prompt estructurado     -> fecha del modelo   (mejora D1)
  C  estruct_tool    prompt estructurado     -> fecha de la tool   (ablation)
  D  solucion        fine-tune + tool        -> fecha de la tool   (solucion final)

El vinculo con el diagnostico de D1 es explicito:
  * fallo de formato/inversion ("conversa en vez de emitir datos") lo ataca
    la instruccion estructurada y, en el brazo D, el fine-tuning;
  * el piso de error en fechas relativas lo ataca resolvedor_temporal
    (el modelo nunca calcula fechas en C y D).
"""

from __future__ import annotations

from pipeline import prompts as P
from pipeline.normalizacion import (
    CAMPOS_CONTRATO,
    ensamblar_evento,
    extraer_json,
    objetivo_nulo,
)
from pipeline.resolvedor_temporal import FECHA_REF, resolver_fecha

BRAZOS = {
    "A": {"nombre": "baseline", "prompt": "directo", "usar_tool": False},
    "B": {"nombre": "estructurado", "prompt": "estructurado", "usar_tool": False},
    "C": {"nombre": "estruct_tool", "prompt": "estructurado", "usar_tool": True},
    "D": {"nombre": "solucion", "prompt": "semantico", "usar_tool": True},
}


class CalendarPipeline:
    """Orquesta: mensaje -> modelo -> (tool) -> contrato de 9 campos."""

    def __init__(self, generador, fecha_ref: str = FECHA_REF):
        self.generador = generador
        self.fecha_ref = fecha_ref

    # -- primitiva --------------------------------------------------------

    def _correr(self, texto: str, modo: str, usar_tool: bool) -> dict:
        if modo == "directo":
            mensajes = P.mensajes_directo(texto)
        elif modo == "estructurado":
            mensajes = P.mensajes_estructurado(texto, self.fecha_ref)
        elif modo == "semantico":
            mensajes = P.mensajes_semantico(texto)
        else:
            raise ValueError("modo desconocido: %r" % modo)

        respuesta = self.generador.generar(mensajes)
        obj = extraer_json(respuesta)
        if "error" in obj:
            evento = objetivo_nulo()
            # incluso sin JSON, la herramienta puede aportar la fecha
            if usar_tool:
                evento["fecha"] = resolver_fecha(texto, self.fecha_ref)
            evento["_error_modelo"] = obj.get("error")
            return evento

        evento = ensamblar_evento(obj, texto, fecha_desde_tool=usar_tool)
        evento["_crudo"] = obj
        return evento

    # -- brazos -----------------------------------------------------------

    def baseline(self, texto: str) -> dict:
        """Brazo A: prompting directo (configuracion de D1)."""
        return self._correr(texto, "directo", usar_tool=False)

    def estructurado(self, texto: str) -> dict:
        """Brazo B: instruccion estructurada + few-shot (mejora medida en D1)."""
        return self._correr(texto, "estructurado", usar_tool=False)

    def estructurado_tool(self, texto: str) -> dict:
        """Brazo C: prompt estructurado + fecha resuelta por la herramienta."""
        return self._correr(texto, "estructurado", usar_tool=True)

    def solucion(self, texto: str) -> dict:
        """Brazo D: extractor semantico fine-tuneado + herramienta de fechas."""
        return self._correr(texto, "semantico", usar_tool=True)

    def correr_brazo(self, brazo: str, texto: str) -> dict:
        cfg = BRAZOS[brazo]
        return self._correr(texto, cfg["prompt"], cfg["usar_tool"])

    # -- utilidades -------------------------------------------------------

    @staticmethod
    def solo_contrato(evento: dict) -> dict:
        """Filtra las claves internas (_crudo, _error_modelo) para la API."""
        return {c: evento.get(c) for c in CAMPOS_CONTRATO}

# -*- coding: utf-8 -*-
"""
normalizacion.py -- Extraccion de JSON, validacion de esquema y ensamblado
del contrato de 9 campos del evento de calendario.

El contrato (especificacion de la tarea) es:
    titulo, fecha (YYYY-MM-DD), hora_inicio (HH:MM), duracion_minutos,
    participantes, ubicacion, recordatorio_minutos, zona_horaria, recurrence

La exactitud se mide sobre los 8 campos que tienen ground truth en
Benchmark2 (evaluar.py de D1); 'recurrence' se emite con semantica null
salvo indicios de repeticion.

Regla de oro: un campo no mencionado es null (o [] para participantes).
Nunca se inventa un valor.
"""

from __future__ import annotations

import json
import re

from pipeline.resolvedor_temporal import resolver_fecha, resolver_hora_expr

CAMPOS_CONTRATO = [
    "titulo", "fecha", "hora_inicio", "duracion_minutos", "participantes",
    "ubicacion", "recordatorio_minutos", "zona_horaria", "recurrence",
]

ZONA_DEFAULT = "America/Santiago"
_ZONAS_CONOCIDAS = {
    "madrid": "Europe/Madrid",
    "argentina": "America/Argentina/Buenos_Aires",
    "santiago": "America/Santiago",
}


def objetivo_nulo() -> dict:
    """Contrato completo con semantica de ausencia."""
    return {
        "titulo": None,
        "fecha": None,
        "hora_inicio": None,
        "duracion_minutos": None,
        "participantes": [],
        "ubicacion": None,
        "recordatorio_minutos": None,
        "zona_horaria": ZONA_DEFAULT,
        "recurrence": None,
    }


# ---------------------------------------------------------------------------
# extraccion del JSON que devuelve el modelo
# ---------------------------------------------------------------------------

def extraer_json(respuesta) -> dict:
    """Primer objeto JSON valido dentro de la respuesta; si no hay, {"error": ...}."""
    if isinstance(respuesta, dict):
        return respuesta
    if not isinstance(respuesta, str):
        return {"error": "No JSON detected"}
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", respuesta):
        try:
            objeto, _ = decoder.raw_decode(respuesta[match.start():])
            if isinstance(objeto, dict):
                return objeto
        except json.JSONDecodeError:
            continue
    return {"error": "No JSON detected", "raw": respuesta[:200]}


# ---------------------------------------------------------------------------
# normalizacion campo por campo
# ---------------------------------------------------------------------------

def normalizar_fecha(valor) -> str | None:
    if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        return None
    try:
        from datetime import datetime
        datetime.strptime(valor, "%Y-%m-%d")
        return valor
    except ValueError:
        return None


def normalizar_hora(valor, texto: str = "") -> str | None:
    """HH:MM 24h. Admite '4', '10am', '3 pm', '15:30' y la convencion de D1."""
    if valor is None:
        return None
    if isinstance(valor, str):
        hora = resolver_hora_expr(valor)
        if hora:
            return hora
        if re.fullmatch(r"\d{2}:\d{2}", valor.strip()):
            return valor.strip()
        return None
    return None


def normalizar_entero(valor) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor)
    if isinstance(valor, str):
        m = re.search(r"\d+", valor)
        return int(m.group(0)) if m else None
    return None


def normalizar_participantes(valor) -> list:
    if not isinstance(valor, list):
        return []
    salida = []
    for x in valor:
        if isinstance(x, str):
            x = x.strip()
            if x and not x.startswith("<") and not x.isdigit():
                salida.append(x)
    return salida


def normalizar_zona(valor, texto: str = "") -> str:
    if isinstance(valor, str) and valor.strip() and "/" in valor:
        return valor.strip()
    t = (texto or "").lower()
    for clave, zona in _ZONAS_CONOCIDAS.items():
        if clave in t:
            return zona
    return ZONA_DEFAULT


def normalizar_ubicacion(valor, texto: str = "") -> str | None:
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    t = (texto or "").lower()
    for etiqueta in ["virtual", "videollamada", "google meet", "zoom", "teams"]:
        if etiqueta in t:
            return etiqueta
    return None


def normalizar_recurrence(valor, texto: str = "") -> str | None:
    if isinstance(valor, str) and valor.strip():
        v = valor.strip()
        return v if v.upper().startswith("FREQ=") else None
    t = (texto or "").lower()
    if any(w in t for w in ("cada semana", "semanal", "todos los lunes", "every week")):
        return "FREQ=WEEKLY"
    if any(w in t for w in ("a diario", "todos los días", "todos los dias", "every day")):
        return "FREQ=DAILY"
    if any(w in t for w in ("cada mes", "mensual", "every month")):
        return "FREQ=MONTHLY"
    return None


# ---------------------------------------------------------------------------
# ensamblado del contrato
# ---------------------------------------------------------------------------

def campos_semanticos_desde(obj: dict, texto: str) -> dict:
    """Normaliza los 8 campos semanticos (sin 'fecha') del objeto del modelo."""
    return {
        "titulo": (obj.get("titulo") or None),
        "hora_inicio": normalizar_hora(obj.get("hora_inicio"), texto),
        "duracion_minutos": normalizar_entero(obj.get("duracion_minutos")),
        "participantes": normalizar_participantes(obj.get("participantes")),
        "ubicacion": normalizar_ubicacion(obj.get("ubicacion"), texto),
        "recordatorio_minutos": normalizar_entero(obj.get("recordatorio_minutos")),
        "zona_horaria": normalizar_zona(obj.get("zona_horaria"), texto),
        "recurrence": normalizar_recurrence(obj.get("recurrence"), texto),
    }


def ensamblar_evento(obj: dict, texto: str, fecha_desde_tool: bool = True) -> dict:
    """
    Construye el contrato de 9 campos.

    fecha_desde_tool=True  -> la fecha la resuelve resolvedor_temporal
                              (brazos C y D: el modelo nunca calcula fechas)
    fecha_desde_tool=False -> la fecha viene del modelo y solo se valida
                              (brazos A y B: baseline / prompt estructurado)
    """
    evento = objetivo_nulo()
    evento.update(campos_semanticos_desde(obj, texto))

    if fecha_desde_tool:
        evento["fecha"] = resolver_fecha(texto)
    else:
        evento["fecha"] = normalizar_fecha(obj.get("fecha"))

    return evento

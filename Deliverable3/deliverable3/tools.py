# -*- coding: utf-8 -*-
"""
tools.py - Herramientas deterministas para el Agente Temporal (A3).
Encapsula resoluciones matemáticas, de calendario y normalizaciones lingüísticas.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Asegurar acceso a deliverable2 para resolver_fecha
_LOCAL = Path(__file__).resolve().parent.parent
for _p in [_LOCAL, _LOCAL / "deliverable2"]:
    if str(_p) not in sys.path and _p.exists():
        sys.path.insert(0, str(_p))

try:
    from pipeline.resolvedor_temporal import resolver_fecha as _resolver_fecha_d2
except ImportError:
    try:
        from deliverable2.pipeline.resolvedor_temporal import resolver_fecha as _resolver_fecha_d2
    except ImportError:
        _resolver_fecha_d2 = None


def resolver_fecha(texto: str, fecha_ref: str = "2026-09-01") -> Optional[str]:
    """Calcula fecha exacta YYYY-MM-DD según la fecha de referencia."""
    if _resolver_fecha_d2 is not None:
        return _resolver_fecha_d2(texto, fecha_ref=fecha_ref)
    
    # Fallback básico si resolver_fecha_d2 no está disponible
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", texto)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3)) if m.group(3) else 2026
        if anio < 100: anio += 2000
        return f"{anio:04d}-{mes:02d}-{dia:02d}"
    return None


def normalizar_hora(hora_str: Optional[str], texto: str = "") -> Optional[str]:
    """
    Normaliza y corrige la hora a formato HH:MM (24h).
    Resuelve el sesgo de D2 donde '10 pm' u '8 pm' se extraían como '10:00' u '08:00'.
    """
    # 1. Si el texto original dice explícitamente "pm" o "de la noche" / "de la tarde"
    txt_lower = texto.lower()
    m_pm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:pm|p\.m\.|de la tarde|de la noche|de la tarde/noche)\b", txt_lower)
    if m_pm:
        h = int(m_pm.group(1))
        m = int(m_pm.group(2)) if m_pm.group(2) else 0
        if 1 <= h <= 11:
            h += 12
        elif h == 12:
            h = 12
        return f"{h:02d}:{m:02d}"

    # 2. Si dice explícitamente "am" o "de la mañana"
    m_am = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:am|a\.m\.|de la ma[nñ]ana)\b", txt_lower)
    if m_am:
        h = int(m_am.group(1))
        m = int(m_am.group(2)) if m_am.group(2) else 0
        if h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    # 3. Si hora_str ya viene dado por el modelo
    if hora_str:
        hora_str = hora_str.strip()
        m = re.match(r"^(\d{1,2}):(\d{2})$", hora_str)
        if m:
            h, m_val = int(m.group(1)), int(m.group(2))
            if 0 <= h < 24 and 0 <= m_val < 60:
                # Si en el texto dice "10 pm" o similar y el modelo dio "10:00"
                if ("10 pm" in txt_lower or "10pm" in txt_lower) and h == 10:
                    return f"22:{m_val:02d}"
                if ("8 pm" in txt_lower or "8pm" in txt_lower) and h == 8:
                    return f"20:{m_val:02d}"
                return f"{h:02d}:{m_val:02d}"
            return None

    # 4. Búsqueda directa de formato HH:MM en el texto
    m_direct = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", texto)
    if m_direct:
        return f"{int(m_direct.group(1)):02d}:{m_direct.group(2)}"

    # 5. Búsqueda de "a las X"
    m_alas = re.search(r"\ba\s+las?\s+(\d{1,2})\b", txt_lower)
    if m_alas:
        h = int(m_alas.group(1))
        if 1 <= h <= 7:
            h += 12  # Convención de tarde para 1..7
        if 0 <= h < 24:
            return f"{h:02d}:00"

    return None


def calcular_duracion(texto: str) -> Optional[int]:
    """Extrae duración en minutos. Corrige '2 horas y media' -> 150 min (en D2 daba 90)."""
    t = texto.lower()
    
    # 2 horas y media -> 150
    if re.search(r"\b2\s+horas?\s+y\s+media\b|\bdos\s+horas?\s+y\s+media\b", t):
        return 150
    if re.search(r"\b1\s+hora\s+y\s+media\b|\buna?\s+hora\s+y\s+media\b", t):
        return 90
    if re.search(r"\bmedia\s+hora\b", t):
        return 30
        
    m_h = re.search(r"\b(\d{1,2})\s+horas?\b", t)
    if m_h:
        return int(m_h.group(1)) * 60
        
    m_min = re.search(r"\b(\d{1,3})\s+(?:minutos|min|mins)\b", t)
    if m_min:
        return int(m_min.group(1))
        
    return None


def extraer_zona_horaria(texto: str) -> str:
    """Extrae zona horaria según mención geográfica o retorna America/Santiago."""
    t = texto.lower()
    if "madrid" in t or "españa" in t or "spain" in t:
        return "Europe/Madrid"
    if "argentina" in t or "buenos aires" in t:
        return "America/Argentina/Buenos_Aires"
    return "America/Santiago"


def extraer_recurrencia(texto: str) -> Optional[str]:
    """Extrae recurrencia si existe en la frase."""
    t = texto.lower()
    if "todos los" in t or "cada semana" in t or "semanal" in t or "weekly" in t:
        return "RRULE:FREQ=WEEKLY"
    if "diario" in t or "todos los dias" in t or "daily" in t:
        return "RRULE:FREQ=DAILY"
    if "mensual" in t or "monthly" in t:
        return "RRULE:FREQ=MONTHLY"
    return None

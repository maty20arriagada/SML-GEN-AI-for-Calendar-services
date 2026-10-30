# -*- coding: utf-8 -*-
"""
resolvedor_temporal.py -- Herramienta determinista de resolucion temporal.

Vinculo con el diagnostico de Deliverable 1: el piso de error del modelo
(Qwen3-4B-Instruct-2507) esta concentrado en la resolucion de fechas
relativas; por eso el calculo temporal NO lo hace el modelo de lenguaje,
sino esta herramienta, con reglas auditables y reproducibles.

La regla de oro es: si la expresion no entra en la gramatica, se devuelve
None. Nunca se inventa un valor.

Referencia temporal del proyecto: 2026-09-01 (martes).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

FECHA_REF = "2026-09-01"
DIA_REF = "martes"

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MESES_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# nombre normalizado -> isoweekday (1=lunes .. 7=domingo)
_DIAS = {
    "lunes": 1, "martes": 2, "miercoles": 3, "jueves": 4, "viernes": 5,
    "sabado": 6, "domingo": 7,
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5,
    "saturday": 6, "sunday": 7,
}

_NUMEROS = {
    "una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_MESES_ALT = "|".join(sorted(_MESES, key=len, reverse=True))
_MESES_EN_ALT = "|".join(sorted(_MESES_EN, key=len, reverse=True))
_DIAS_ALT = "|".join(sorted(_DIAS, key=len, reverse=True))
_NUMS_ALT = "|".join(sorted(_NUMEROS, key=len, reverse=True))

_RE_DDM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})\b")
_RE_DIA_DE_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + _MESES_ALT + r")\b")
_RE_MES_DIA_EN = re.compile(r"\b(" + _MESES_EN_ALT + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_RE_DIA_DE_MES_EN = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(" + _MESES_EN_ALT + r")\b")
_RE_PASADO_MANANA = re.compile(r"\bpasado\s+manana\b")
_RE_MANANA = re.compile(r"\bmanana\b")
_RE_EN_N = re.compile(r"\b(?:en|in)\s+(" + _NUMS_ALT + r"|\d+)\s+(dia|dias|day|days|semana|semanas|week|weeks)\b")
_RE_SEMANA_PROX = re.compile(r"\b(" + _DIAS_ALT + r")\s+(?:de\s+la\s+|of\s+the\s+)(?:proxima|next)\s+semana\b")
_RE_WEEKDAY = re.compile(r"\b(?:el\s+|la\s+|on\s+|this\s+|next\s+|este\s+|esta\s+|proximo\s+|proxima\s+)*(" + _DIAS_ALT + r")\b")
_RE_DIA_SOLO = re.compile(r"\bel\s+(?:dia\s+)?(\d{1,2})\b")

# Contextos que anulan una expresion (no son fechas del evento).
_EXCL_MANANA = ("de la ", "por la ", "en la ", "esta ", "la ", "the ", "this ")
_EXCL_WEEKDAY = ("los ", "las ", "cada ", "every ", "each ")

_RE_HORA_A_LAS = re.compile(
    r"\ba\s+las\s+(\d{1,2})(?::(\d{2}))?\s*"
    r"(am|pm|de\s+la\s+manana|de\s+la\s+tarde|de\s+la\s+noche)?"
)
_RE_HORA_AT = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?")
_RE_HORA_24H = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?")
_RE_HORA_MER = re.compile(r"\b(\d{1,2})\s*(am|pm)\b")
_RE_HORA_FRANJA = re.compile(r"\b(\d{1,2})\s*de\s+la\s+(manana|tarde|noche)\b")
_RE_RANGO = re.compile(r"\bde\s+(\d{1,2})\s+a\s+(\d{1,2})\b")


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------

def _norm(texto: str) -> str:
    """Minusculas + sin tildes. Conserva la longitud (los spans siguen valiendo)."""
    s = texto.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


def _iso(d: date) -> str:
    return d.isoformat()


def _a_date(iso: str) -> date:
    return datetime.strptime(iso, "%Y-%m-%d").date()


def _con_anio(dia: int, mes: int, ref: date) -> str | None:
    """Fecha valida en el anio de ref; si ya paso, anio siguiente."""
    for anio in (ref.year, ref.year + 1):
        try:
            return _iso(date(anio, mes, dia))
        except ValueError:
            continue
    return None


def _proximo_weekday(ref: date, objetivo: int) -> date:
    """Siguiente ocurrencia estrictamente posterior a ref."""
    delta = (objetivo - ref.isoweekday()) % 7
    if delta == 0:
        delta = 7
    return ref + timedelta(days=delta)


def _weekday_semana_proxima(ref: date, objetivo: int) -> date:
    lunes_prox = ref - timedelta(days=ref.isoweekday() - 1) + timedelta(days=7)
    return lunes_prox + timedelta(days=objetivo - 1)


def _previo(t: str, inicio: int, contextos: tuple) -> bool:
    antes = t[max(0, inicio - 10):inicio]
    return any(antes.endswith(c) for c in contextos)


def _a_entero(valor: str) -> int | None:
    if valor.isdigit():
        return int(valor)
    return _NUMEROS.get(valor)


# ---------------------------------------------------------------------------
# busqueda de la expresion temporal de FECHA
# ---------------------------------------------------------------------------

def _buscar_fecha(t: str, ref: date) -> tuple[str | None, tuple[int, int] | None]:
    """Devuelve (fecha_iso, span) sobre el texto normalizado `t`."""

    # 1. formato dd/mm o dd-mm  (convencion del benchmark: dia/mes)
    for m in _RE_DDM.finditer(t):
        dia, mes = int(m.group(1)), int(m.group(2))
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            f = _con_anio(dia, mes, ref)
            if f:
                return f, m.span()

    # 2. "15 de septiembre" / "september 8th" / "8th of september"
    for m in _RE_DIA_DE_MES.finditer(t):
        f = _con_anio(int(m.group(1)), _MESES[m.group(2)], ref)
        if f:
            return f, m.span()
    for m in _RE_MES_DIA_EN.finditer(t):
        f = _con_anio(int(m.group(2)), _MESES_EN[m.group(1)], ref)
        if f:
            return f, m.span()
    for m in _RE_DIA_DE_MES_EN.finditer(t):
        f = _con_anio(int(m.group(1)), _MESES_EN[m.group(2)], ref)
        if f:
            return f, m.span()

    # 3. "pasado manana"  (antes que "manana", si no daria +1)
    m = _RE_PASADO_MANANA.search(t)
    if m:
        return _iso(ref + timedelta(days=2)), m.span()

    # 4. "manana" (no "de la manana", "esta manana", ...)
    for m in _RE_MANANA.finditer(t):
        if _previo(t, m.start(), _EXCL_MANANA):
            continue
        return _iso(ref + timedelta(days=1)), m.span()

    # 5. "en dos semanas" / "in two weeks"
    m = _RE_EN_N.search(t)
    if m:
        n = _a_entero(m.group(1))
        if n:
            semanas = m.group(2).startswith(("semana", "week"))
            return _iso(ref + timedelta(days=7 * n if semanas else n)), m.span()

    # 6. "miercoles de la proxima semana"
    m = _RE_SEMANA_PROX.search(t)
    if m:
        return _iso(_weekday_semana_proxima(ref, _DIAS[m.group(1)])), m.span()

    # 7. "el lunes" / "proximo martes" / "on monday"
    for m in _RE_WEEKDAY.finditer(t):
        if _previo(t, m.start(), _EXCL_WEEKDAY):
            continue
        return _iso(_proximo_weekday(ref, _DIAS[m.group(1)])), m.span()

    # 8. "el 10" (solo dia; mes corriente si queda futuro)
    for m in _RE_DIA_SOLO.finditer(t):
        dia = int(m.group(1))
        if not 1 <= dia <= 31:
            continue
        mes, anio = ref.month, ref.year
        if dia < ref.day:
            mes += 1
            if mes == 13:
                mes, anio = 1, anio + 1
        try:
            return _iso(date(anio, mes, dia)), m.span()
        except ValueError:
            # dia invalido para el mes (p.ej. 31 de febrero) -> mes siguiente
            try:
                mes2 = mes + 1 if mes < 12 else 1
                anio2 = anio if mes < 12 else anio + 1
                return _iso(date(anio2, mes2, dia)), m.span()
            except ValueError:
                continue

    return None, None


# ---------------------------------------------------------------------------
# busqueda de la expresion temporal de HORA
# ---------------------------------------------------------------------------

def _aplicar_hora(h: int, m: int, sufijo: str | None) -> str | None:
    suf = (sufijo or "").replace("  ", " ").strip()
    suf = re.sub(r"\s+", " ", suf)
    if suf in ("pm", "de la tarde", "de la noche"):
        if h < 12:
            h += 12
    elif suf in ("am", "de la manana"):
        if h == 12:
            h = 0
    else:
        # convencion del benchmark: hora en blanco 1..7 = tarde
        if 1 <= h <= 7:
            h += 12
    if h > 23 or m > 59:
        return None
    return "%02d:%02d" % (h, m)


def _buscar_hora(t: str, spans: list[tuple[int, int]]) -> tuple[str | None, tuple[int, int] | None]:
    """Primera expresion horaria del texto, ignorando los spans de fecha."""
    candidatos = []

    for m in _RE_HORA_A_LAS.finditer(t):
        candidatos.append((m, m.group(1), m.group(2) or "0", m.group(3)))
    for m in _RE_HORA_AT.finditer(t):
        candidatos.append((m, m.group(1), m.group(2) or "0", m.group(3)))
    for m in _RE_HORA_24H.finditer(t):
        candidatos.append((m, m.group(1), m.group(2), m.group(3)))
    for m in _RE_HORA_MER.finditer(t):
        candidatos.append((m, m.group(1), "0", m.group(2)))
    for m in _RE_HORA_FRANJA.finditer(t):
        suf = "de la " + m.group(2)
        candidatos.append((m, m.group(1), "0", suf))
    for m in _RE_RANGO.finditer(t):
        candidatos.append((m, m.group(1), "0", None))

    def sin_solape(span):
        a, b = span
        return not any(a < fb and b > fa for fa, fb in spans)

    candidatos = [c for c in candidatos if sin_solape(c[0].span())]
    if not candidatos:
        return None, None

    m, hs, ms, sufijo = min(candidatos, key=lambda c: (c[0].start(), -c[0].end()))
    try:
        h, mm = int(hs), int(ms)
    except ValueError:
        return None, None
    hora = _aplicar_hora(h, mm, sufijo)
    return hora, m.span()


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def analizar_temporal(texto: str, fecha_ref: str = FECHA_REF) -> dict:
    """
    Resuelve la parte temporal de un mensaje.

    Devuelve:
        fecha        -> 'YYYY-MM-DD' o None
        hora_inicio  -> 'HH:MM' o None
        fecha_expr   -> expresion literal encontrada (para trazabilidad)
        hora_expr    -> expresion literal encontrada (para trazabilidad)
    """
    ref = _a_date(fecha_ref)
    t = _norm(texto)

    fecha, span_fecha = _buscar_fecha(t, ref)
    spans = [span_fecha] if span_fecha else []
    hora, span_hora = _buscar_hora(t, spans)

    def superficie(span):
        if not span:
            return None
        return texto[span[0]:span[1]].strip()

    return {
        "fecha": fecha,
        "hora_inicio": hora,
        "fecha_expr": superficie(span_fecha),
        "hora_expr": superficie(span_hora),
    }


def resolver_fecha(texto: str, fecha_ref: str = FECHA_REF) -> str | None:
    """Solo la fecha. None si la expresion no entra en la gramatica."""
    return analizar_temporal(texto, fecha_ref)["fecha"]


def resolver_hora_expr(expr: str) -> str | None:
    """Resuelve una expresion horaria aislada ('a las 4', '10am', '15:30')."""
    if not expr:
        return None
    hora, _ = _buscar_hora(_norm(expr), [])
    if hora:
        return hora
    return resolver_hora_valor(expr)


def resolver_hora_valor(valor) -> str | None:
    """Valor suelto que viene del modelo: '4', '09:30', '10 pm'."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        return None
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*", valor, re.I)
    if not m:
        return None
    return _aplicar_hora(int(m.group(1)), int(m.group(2) or 0), m.group(3))


def resolver_hora(texto: str, fecha_ref: str = FECHA_REF) -> str | None:
    """Solo la hora, ignorando los numeros que forman parte de la fecha."""
    return analizar_temporal(texto, fecha_ref)["hora_inicio"]


if __name__ == "__main__":
    pruebas = [
        "Reunion el lunes a las 3pm",
        "agenda reunion manana 10am porfa",
        "Oye, agendame una junta con la Dani pasado manana a las 4 en la sala B-11",
        "Reunion el miércoles de la próxima semana a las 11",
        "Cita en dos semanas a las 12:00",
        "Llamada a las 14:30",
        "Junta de emergencia",
        "Call with the client on Monday at 5pm",
        "Reunión el 10/09 a las 10 pm",
        "Reunión el lunes 7 de septiembre sin hora definida",
    ]
    for p in pruebas:
        print("%-70s -> %s" % (p, analizar_temporal(p)))

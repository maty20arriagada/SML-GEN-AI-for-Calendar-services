# -*- coding: utf-8 -*-
"""
tools_v2.py - Herramientas deterministas de la etapa 2 (intento2).
No modifica tools.py: corrige las fallas medidas en la corrida del intento1.

  calcular_duracion_v2     : distingue duración de recordatorio ("15 min antes" ya no es duración).
  extraer_recordatorio     : minutos de recordatorio explícitos en la frase.
  resolver_fecha_v2        : envuelve el resolvedor de D2 con 3 pre-pasos ("viernes 18",
                             fechas dd/mm inválidas, "tomorrow").
  expandir_participante    : completa roles compuestos ("candidata" -> "candidata a diseñadora").
  fecha_explicita_invalida : True si la frase trae una fecha dd/mm o "d de mes" que no existe.
  hora_ampm_explicita      : hora 24h implícita en un "8 pm" / "7:15 am" / "de la tarde".
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from deliverable3.tools import resolver_fecha


def _norm(texto: str) -> str:
    """Minúsculas y sin tildes, conservando el largo (los índices valen para el texto original)."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto.lower())


# ---------------------------------------------------------------------------
# Duración vs recordatorio
# ---------------------------------------------------------------------------

_PALABRAS_NUM = {
    "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}
_NUM = r"(\d{1,3}|" + "|".join(_PALABRAS_NUM) + r")"
_HORA_U = r"(?:horas?|hours?)"
_MIN_U = r"(?:minutos?|minutes?|mins?)"

# (regex, minutos en función del grupo 1). El orden resuelve solapes: "2 horas y media" gana a "2 horas".
_PATRONES_DUR = [
    (re.compile(rf"\b{_NUM}\s+{_HORA_U}\s+y\s+media\b"), lambda n: n * 60 + 30),
    (re.compile(r"\bmedia\s+hora\b|\bhalf\s+an?\s+hour\b"), lambda n: 30),
    (re.compile(rf"\b{_NUM}\s+{_HORA_U}\b"), lambda n: n * 60),
    (re.compile(rf"\b{_NUM}\s+{_MIN_U}\b"), lambda n: n),
]
_RE_ANTES = re.compile(r"\s*(?:de\s+)?(?:antes|before|prior)\b")
_RE_CLAVE_RECORDATORIO = re.compile(
    r"(?:recordatorio|recuerdame|recuerda|avisame|avisa|aviso|notificame|remind me|reminder|alert)"
    r"\s+(?:de\s+|con\s+|a\s+los\s+)?$"
)
_RE_RELATIVO = re.compile(r"\b(?:en|in)\s+$")


def _num(token: str) -> int:
    return int(token) if token.isdigit() else _PALABRAS_NUM[token]


def _candidatos_duracion(texto: str) -> List[Dict[str, Any]]:
    """Cantidades de tiempo de la frase, clasificadas como 'duracion' o 'recordatorio', por posición."""
    t = _norm(texto)
    tomados: List[tuple] = []
    out: List[Dict[str, Any]] = []
    for patron, a_minutos in _PATRONES_DUR:
        for m in patron.finditer(t):
            if any(m.start() < e and s < m.end() for s, e in tomados):
                continue
            tomados.append(m.span())
            n = _num(m.group(1)) if m.lastindex else 0
            antes = t[max(0, m.start() - 30):m.start()]
            if _RE_RELATIVO.search(antes):
                continue  # "en 2 horas" = cuándo empieza, no cuánto dura
            es_rec = bool(_RE_ANTES.match(t[m.end():m.end() + 14]) or _RE_CLAVE_RECORDATORIO.search(antes))
            out.append({"minutos": a_minutos(n), "tipo": "recordatorio" if es_rec else "duracion",
                        "inicio": m.start()})
    return sorted(out, key=lambda c: c["inicio"])


def calcular_duracion_v2(texto: str) -> Optional[int]:
    """Duración en minutos; ignora las cantidades que son recordatorio ("avísame 15 min antes")."""
    for c in _candidatos_duracion(texto):
        if c["tipo"] == "duracion":
            return c["minutos"]
    return None


def extraer_recordatorio(texto: str) -> Optional[int]:
    """Minutos de recordatorio explícitos ("media hora antes", "recordatorio 5 minutos")."""
    for c in _candidatos_duracion(texto):
        if c["tipo"] == "recordatorio":
            return c["minutos"]
    return None


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

_DIAS_SEM = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_RE_DDM_BARRA = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/])")
_RE_DIA_DE_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\b")
_RE_SEM_NUM = re.compile(r"\b(" + "|".join(_DIAS_SEM) + r")\s+(\d{1,2})\b(?!\s*(?::|de\b|al\b|a\s+\d|am\b|pm\b|h\b|hrs?\b|horas?\b))")


def _existe(dia: int, mes: int, anio: int) -> bool:
    try:
        date(anio, mes, dia)
        return True
    except ValueError:
        return False


def fecha_explicita_invalida(texto: str, fecha_ref: str = "2026-09-01") -> bool:
    """True si la frase trae una fecha explícita (dd/mm o "d de mes") que no existe en el calendario."""
    ref = date.fromisoformat(fecha_ref)
    t = _norm(texto)
    for m in _RE_DDM_BARRA.finditer(t):
        dia, mes = int(m.group(1)), int(m.group(2))
        anios = [int(m.group(3)) + (2000 if int(m.group(3)) < 100 else 0)] if m.group(3) else [ref.year, ref.year + 1]
        if not (1 <= mes <= 12 and 1 <= dia <= 31 and any(_existe(dia, mes, a) for a in anios)):
            return True
    for m in _RE_DIA_DE_MES.finditer(t):
        dia, mes = int(m.group(1)), _MESES[m.group(2)]
        if not any(_existe(dia, mes, a) for a in (ref.year, ref.year + 1)):
            return True
    return False


def _weekday_con_numero(texto: str, ref: date) -> Optional[str]:
    """"viernes 18": la próxima fecha con día 18 que cae en viernes."""
    for m in _RE_SEM_NUM.finditer(_norm(texto)):
        objetivo, dia = _DIAS_SEM[m.group(1)], int(m.group(2))
        if not 1 <= dia <= 31:
            continue
        anio, mes = ref.year, ref.month
        for _ in range(24):
            if _existe(dia, mes, anio):
                d = date(anio, mes, dia)
                if d > ref and d.weekday() == objetivo:
                    return d.isoformat()
            mes += 1
            if mes == 13:
                mes, anio = 1, anio + 1
    return None


def resolver_fecha_v2(texto: str, fecha_ref: str = "2026-09-01") -> Optional[str]:
    """Resolvedor de D2 + pre-pasos que corrigen sus tres fallas medidas."""
    ref = date.fromisoformat(fecha_ref)
    if fecha_explicita_invalida(texto, fecha_ref):
        return None
    f = _weekday_con_numero(texto, ref)
    if f:
        return f
    f = resolver_fecha(texto, fecha_ref)
    if f:
        return f
    t = _norm(texto)
    if re.search(r"\bday after tomorrow\b", t):
        return (ref + timedelta(days=2)).isoformat()
    if re.search(r"\btomorrow\b", t):
        return (ref + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", t):
        return ref.isoformat()
    return None


# ---------------------------------------------------------------------------
# Hora am/pm explícita
# ---------------------------------------------------------------------------

_RE_AMPM = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(pm|p\.m\.|de la tarde|de la noche|am|a\.m\.|de la manana)(?![a-z])"
)


def hora_ampm_explicita(texto: str) -> Optional[str]:
    """HH:MM (24h) de la primera hora con marca am/pm/de la tarde; None si la frase no la trae."""
    m = _RE_AMPM.search(_norm(texto))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if not (1 <= h <= 12 and mi < 60):
        return None
    es_pm = m.group(3) in ("pm", "p.m.", "de la tarde", "de la noche")
    if es_pm and h < 12:
        h += 12
    elif not es_pm and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


# ---------------------------------------------------------------------------
# Participantes
# ---------------------------------------------------------------------------

_NO_EXPANDIR = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu", "su", "sus",
    "casa", "domicilio", "distancia", "tiempo", "hoy", "manana", "ayer", "noche", "tarde",
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
}.union(_MESES)


def expandir_participante(frase: str, nombre: str) -> str:
    """Completa un rol truncado: "candidata" + "a diseñadora" / "jefe" + "de ventas".
    Solo toca sustantivos en minúscula; los nombres propios y los nombres ya completos quedan igual."""
    if not nombre or nombre[:1].isupper():
        return nombre
    m = re.search(r"(?i:\b" + re.escape(nombre) + r")\s+(a|de)\s+([^\W\d_]+)", frase)
    if not m or not m.group(2)[:1].islower() or _norm(m.group(2)) in _NO_EXPANDIR:
        return nombre
    return f"{nombre} {m.group(1)} {m.group(2)}"


def participante_dudoso(frase: str, participante: str) -> bool:
    """Un participante es confiable si es nombre propio o va introducido por con/y/with/a.
    El resto ("ensayo de la banda", "vacuna del perro") puede ser un complemento del título."""
    f, q = _norm(frase), _norm(participante)
    i = f.find(q)
    if i < 0:
        return True
    if frase[i:i + 1].isupper():
        return False
    antes = f[max(0, i - 40):i]
    return not re.search(
        r"\b(?:con|y|e|a|al|with|and|w/|junto a|junto con)\s+(?:(?:el|la|los|las|mi|mis|un|una|the|my)\s+)*$", antes
    )


# ---------------------------------------------------------------------------
# Herramientas de la etapa 3 (intento3): señal temporal, validador y participantes
# ---------------------------------------------------------------------------

_RE_HORA_EXPLICITA = re.compile(r"\b\d{1,2}:\d{2}\b|\ba\s+las?\s+\d{1,2}\b|\bat\s+\d{1,2}\b|\b\d{1,2}\s*(?:am|pm)\b|\bde la (?:manana|tarde|noche)\b")


def detectar_expresion_temporal(texto: str, fecha_ref: str = "2026-09-01") -> Dict[str, Any]:
    """Señal para A1: ¿la frase trae una fecha o una hora reconocibles? (no decide nada)."""
    fecha = resolver_fecha_v2(texto, fecha_ref)
    hora = bool(_RE_HORA_EXPLICITA.search(_norm(texto)))
    return {"fecha": fecha, "hora_explicita": hora, "fecha_invalida": fecha_explicita_invalida(texto, fecha_ref),
            "tiene_senal": bool(fecha or hora)}


def expandir_participantes(frase: str, participantes: List[str]) -> List[str]:
    return [expandir_participante(frase, str(p)) for p in participantes or []]


_RE_HORA_24 = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validar_contrato(frase: str, evento: Dict[str, Any], fecha_ref: str = "2026-09-01") -> List[Dict[str, Any]]:
    """Lista de violaciones del evento frente a la frase (no modifica nada).
    Cada violación: {codigo, campo, detalle, sugerencia}. V4 trae además `dudosos`."""
    v: List[Dict[str, Any]] = []
    f = evento.get("fecha")
    if f:
        try:
            date.fromisoformat(str(f))
            if fecha_explicita_invalida(frase, fecha_ref):
                v.append({"codigo": "V1", "campo": "fecha", "detalle": "la frase trae una fecha que no existe", "sugerencia": None})
        except ValueError:
            v.append({"codigo": "V1", "campo": "fecha", "detalle": f"fecha mal formada {f!r}", "sugerencia": None})
    h = evento.get("hora_inicio")
    if h is not None and not _RE_HORA_24.match(str(h)):
        v.append({"codigo": "V1", "campo": "hora_inicio", "detalle": f"hora fuera de rango {h!r}", "sugerencia": None})
    dur, rec = evento.get("duracion_minutos"), evento.get("recordatorio_minutos")
    if dur is not None and dur in (rec, extraer_recordatorio(frase)) and calcular_duracion_v2(frase) != dur:
        v.append({"codigo": "V2", "campo": "duracion_minutos",
                  "detalle": f"la duración {dur} coincide con el recordatorio de la frase", "sugerencia": None})
    esperada = hora_ampm_explicita(frase)
    if esperada and h != esperada:
        v.append({"codigo": "V3", "campo": "hora_inicio",
                  "detalle": f"la frase marca am/pm: se esperaba {esperada}, el evento trae {h!r}", "sugerencia": esperada})
    dudosos = [str(p) for p in (evento.get("participantes") or []) if participante_dudoso(frase, str(p))]
    if dudosos:
        v.append({"codigo": "V4", "campo": "participantes", "detalle": "participantes que podrían ser complemento del título",
                  "sugerencia": None, "dudosos": dudosos})
    return v

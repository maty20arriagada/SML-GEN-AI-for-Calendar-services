# -*- coding: utf-8 -*-
"""
generar_dataset.py v2 -- Dataset sintetico ESPECIALIZADO para el fine-tuning del
extractor semantico de Qwen3-4B-Instruct-2507.

Cambios frente a v1 (plan "modelo bestial"):
  * El target del modelo son SOLO 6 campos: titulo, hora_inicio, duracion_minutos,
    participantes, ubicacion, recordatorio_minutos.
    fecha (herramienta), zona_horaria (regla) y recurrence (regla) los resuelve el
    ensamblador: el modelo deja de producir lo que el codigo calcula mejor.
  * Perfil dirigido a los fallos reales del brazo D:
      - convencion de ARTICULOS en participantes (con sus excepciones reales)
      - titulos DERIVADOS del verbo ("quedamos..." -> "Quedada")
  * Sale ademas hard_dev.jsonl (solo patrones dificiles) para early stopping.

Reglas metodologicas (entregable 2):
  * Benchmark2 (45 frases) es SOLO test: nunca se entrena con el.
  * El ground truth se calcula por construccion; fechas/horas se resuelven con
    pipeline.resolvedor_temporal (la herramienta del pipeline).
  * Ninguna muestra se etiqueta con un valor que no sea derivable de la frase.

Uso:
  python datos/generar_dataset.py --n 3200 --dev 200 --hard-dev 150 --seed 42
  python datos/generar_dataset.py --perfil fallos --n 800    # solo patrones dificiles
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from pipeline.resolvedor_temporal import FECHA_REF, analizar_temporal  # noqa: E402
from pipeline import prompts as P  # noqa: E402

RUTA_BENCHMARK = os.path.join(RAIZ, "benchmark", "benchmark2.json")
RUTA_SALIDA = os.path.join(RAIZ, "datos")

# El modelo SOLO produce estos 6 campos.
CAMPOS_MODELO = [
    "titulo", "hora_inicio", "duracion_minutos",
    "participantes", "ubicacion", "recordatorio_minutos",
]

ZONA_DEFAULT = "America/Santiago"

# ---------------------------------------------------------------------------
# eventos y titulos
# ---------------------------------------------------------------------------

EVENTOS = [
    ("Reunión", "reunion", "es"),
    ("Reunión de planificación", "reunion de planificacion", "es"),
    ("Cita médica", "cita medica", "es"),
    ("Cita", "cita", "es"),
    ("Junta", "junta", "es"),
    ("Junta de sincronización", "junta de sincronizacion", "es"),
    ("Junta de directorio", "junta de directorio", "es"),
    ("Llamada", "llamada", "es"),
    ("Clase", "clase", "es"),
    ("Taller", "taller", "es"),
    ("Entrevista", "entrevista", "es"),
    ("Entrevista técnica", "entrevista tecnica", "es"),
    ("Presentación", "presentacion", "es"),
    ("Presentación de tesis", "presentacion de tesis", "es"),
    ("Almuerzo", "almuerzo", "es"),
    ("Almuerzo de trabajo", "almuerzo de trabajo", "es"),
    ("Café", "cafe", "es"),
    ("Workshop de IA", "workshop de IA", "es"),
    ("Review", "review", "es"),
    ("Sesión de fotos", "sesion de fotos", "es"),
    ("Meeting", "meeting", "en"),
    ("Call", "call", "en"),
    ("Review", "review", "en"),
    ("Workshop", "workshop", "en"),
    ("Interview", "interview", "en"),
    ("Presentation", "presentation", "en"),
    ("Class", "class", "en"),
    ("Lunch", "lunch", "en"),
]

# Frase en clave de verbo + etiqueta nominal del evento (el titulo NO aparece en el texto).
# Enseñan a derivar la etiqueta, que es lo que falla hoy ("quedamos" -> "Quedada").
VERBOS_ETIQUETA = [
    ("quedamos", "Quedada"),
    ("nos vemos", "Encuentro"),
    ("presentamos", "Presentación"),
    ("revisamos", "Revisión"),
    ("comemos", "Almuerzo"),
    ("desayunamos", "Desayuno"),
    ("capacitamos", "Capacitación"),
    ("evaluamos", "Evaluación"),
]

# ---------------------------------------------------------------------------
# fechas y horas (el GT temporal lo calcula la herramienta del pipeline)
# ---------------------------------------------------------------------------

FECHAS_ES = [
    "mañana", "pasado mañana",
    "el lunes", "el martes", "el miércoles", "el jueves", "el viernes", "el sábado",
    "el próximo lunes", "el próximo martes", "el próximo viernes",
    "el miércoles de la próxima semana", "el jueves de la próxima semana",
    "en dos semanas", "en una semana", "en tres días", "en cinco días",
    "el 2 de septiembre", "el 4 de septiembre", "el 7 de septiembre",
    "el 10 de septiembre", "el 15 de septiembre", "el 21 de septiembre",
    "el 3 de octubre", "el 12 de octubre", "el 5 de noviembre",
    "el 8/09", "el 12/09", "el 20/10", "el 3/11",
    "el 10", "el 22",
]
FECHAS_RELATIVAS_ES = set(FECHAS_ES[:17])
FECHAS_EN = [
    "tomorrow", "the day after tomorrow",
    "on Monday", "on Friday", "on Tuesday", "on Thursday",
    "next Monday", "next Tuesday",
    "in two weeks", "in one week", "in three days",
    "on September 8th", "on September 15th", "on October 3rd", "on November 5th",
    "on 8/09", "on 12/09",
]

HORAS_ES = [
    "a las 9", "a las 10", "a las 11", "a las 12:00", "a las 15:30", "a las 16:00",
    "a las 4", "a las 5", "a las 6", "a las 7", "a las 8:30", "a las 9:30",
    "a las 3 de la tarde", "8 de la mañana", "9 de la mañana",
    "10am", "3pm", "11:15", "14:30", "10:30",
]
HORAS_EN = ["at 2pm", "at 10am", "at 5pm", "at 9:30", "at 11", "at 3pm", "at 8:30"]

RANGOS = [
    ("de 9 a 12", "09:00", 180),
    ("de 10 a 12", "10:00", 120),
    ("de 15 a 17", "15:00", 120),
    ("de 16 a 18", "16:00", 120),
]

# ---------------------------------------------------------------------------
# participantes: la convencion de articulos del ground truth
#   quita    -> se elimina el articulo inicial singular (el/la/the)
#   conserva -> el articulo forma parte de la referencia y se conserva
#   nombre   -> nombre propio sin articulo en la frase
# ---------------------------------------------------------------------------

PARTICIPANTES_ES = [
    (None, [], "ninguno"),
    (None, [], "ninguno"),
    ("con Ana y Pedro", ["Ana", "Pedro"], "nombre"),
    ("con María", ["María"], "nombre"),
    ("con Juan y Carla", ["Juan", "Carla"], "nombre"),
    ("con Camila y Tomás", ["Camila", "Tomás"], "nombre"),
    ("con Pedro", ["Pedro"], "nombre"),
    # quita articulo singular
    ("con el equipo de ventas", ["equipo de ventas"], "quita"),
    ("con el equipo de marketing", ["equipo de marketing"], "quita"),
    ("con el equipo de RRHH", ["equipo de RRHH"], "quita"),
    ("con el cliente", ["cliente"], "quita"),
    ("con la clienta", ["clienta"], "quita"),
    ("con el proveedor", ["proveedor"], "quita"),
    ("con el gerente", ["gerente"], "quita"),
    ("con el comité evaluador", ["comité evaluador"], "quita"),
    ("con el jurado", ["jurado"], "quita"),
    ("con la Dani", ["Dani"], "quita"),
    ("con la Camila", ["Camila"], "quita"),
    ("con el Nico", ["Nico"], "quita"),
    ("con el asesor", ["asesor"], "quita"),
    # conserva el articulo (excepciones reales del ground truth)
    ("con el profe", ["el profe"], "conserva"),
    ("con Dani y el profe", ["Dani", "el profe"], "conserva"),
    ("con los clientes", ["los clientes"], "conserva"),
    ("con los desarrolladores", ["los desarrolladores"], "conserva"),
    ("con los 5 directores", ["los 5 directores"], "conserva"),
    ("con los 3 socios", ["los 3 socios"], "conserva"),
    ("con todo el equipo", ["todo el equipo"], "conserva"),
    ("con todo el comité", ["todo el comité"], "conserva"),
    ("con los 4 amigos", ["los 4 amigos"], "conserva"),
]

PARTICIPANTES_EN = [
    (None, [], "ninguno"),
    (None, [], "ninguno"),
    ("with the client", ["client"], "quita"),
    ("with the team", ["team"], "quita"),
    ("with the manager", ["manager"], "quita"),
    ("with the dev team", ["dev team"], "quita"),
    ("with the committee", ["committee"], "quita"),
    ("with the supplier", ["supplier"], "quita"),
    ("with Ana", ["Ana"], "nombre"),
    ("with Ana and Pedro", ["Ana", "Pedro"], "nombre"),
    ("with the whole team", ["the whole team"], "conserva"),
    ("with the 5 directors", ["the 5 directors"], "conserva"),
]

UBICACIONES_ES = [
    (None, None),
    ("en la sala B-11", "sala B-11"),
    ("en el auditorio", "auditorio"),
    ("por videollamada", "videollamada"),
    ("por Zoom", "Zoom"),
    ("en lo de siempre", "lo de siempre"),
    ("en el salón 201", "salón 201"),
    ("en la oficina central", "oficina central"),
    ("en el restaurante La Tabla", "restaurante La Tabla"),
    ("en la sala de conferencias", "sala de conferencias"),
    ("en la sala 201", "sala 201"),
]
UBICACIONES_EN = [
    (None, None),
    ("in room B-11", "room B-11"),
    ("on Zoom", "Zoom"),
    ("in the auditorium", "auditorium"),
    ("in the main office", "main office"),
]

DURACIONES_ES = [
    (None, None), ("por 1 hora", 60), ("por 2 horas", 120), ("2 horas", 120),
    ("45 minutos", 45), ("30 minutos", 30), ("1 hora y media", 90),
]
DURACIONES_EN = [(None, None), ("for 1 hour", 60), ("for 2 hours", 120), ("for 45 minutes", 45)]

RECORDATORIOS_ES = [
    (None, None), ("avísame 15 min antes", 15), ("avísame 30 min antes", 30),
    ("recordatorio 10 minutos antes", 10), ("recuérdame 1 hora antes", 60),
]
RECORDATORIOS_EN = [(None, None), ("remind me 15 min before", 15), ("remind me 30 min before", 30)]

# zona y recurrencia van en la FRASE (el ensamblador las resuelve por reglas),
# pero NO forman parte del target del modelo.
ZONAS_ES = [
    (None, "America/Santiago"), (None, "America/Santiago"),
    ("en horario de Madrid", "Europe/Madrid"),
    ("en horario de Argentina", "America/Argentina/Buenos_Aires"),
]
ZONAS_EN = [(None, ZONA_DEFAULT), ("Madrid time", "Europe/Madrid")]
RECURRENCIAS_ES = [
    (None, None), (None, None), (None, None),
    ("cada semana", "FREQ=WEEKLY"), ("todos los lunes", "FREQ=WEEKLY"),
    ("a diario", "FREQ=DAILY"), ("cada mes", "FREQ=MONTHLY"),
]
RECURRENCIAS_EN = [(None, None), (None, None), ("every week", "FREQ=WEEKLY"), ("every day", "FREQ=DAILY")]

# ---------------------------------------------------------------------------
# plantillas
# ---------------------------------------------------------------------------

PREFIJOS_CHAT = ["", "oye, ", "hola, ", "q onda, ", "porfa: ", "ayuda: ", "apa "]
SUFIJOS_CHAT = ["", " porfa", " pls", " gracias", " xfis"]
SUFIJOS_CHAT_EN = ["", " thanks", " pls"]

# plantillas con nombre de evento (el titulo esta en la frase)
PLANTILLAS_CHAT_ES = [
    ("{pref}agéndame una {titulo}{part}{fecha}{hora}{ub}{dur}{record}{suf}", {"part", "ub", "dur", "record"}),
    ("{pref}agenda {titulo}{fecha}{hora}{ub}{part}{dur}{suf}", {"part", "ub", "dur"}),
    ("{pref}recuérdame la {titulo}{fecha}{hora}{part}{record}{suf}", {"part", "record"}),
    ("{pref}hay que agendar {titulo}{fecha}{hora}{part}{ub}{recurr}{suf}", {"part", "ub", "recurr"}),
    ("{pref}apúntame {titulo}{fecha}{hora}{ub}{part}{dur}{suf}", {"part", "ub", "dur"}),
    ("{pref}me agendan {titulo}{fecha}{hora}{part}{ub}{record}{recurr}{suf}", {"part", "ub", "record", "recurr"}),
    ("{pref}tenemos {titulo}{fecha}{hora}{part}{ub}{dur}{suf}", {"part", "ub", "dur"}),
]
PLANTILLAS_VERBO_ES = [
    ("{pref}{verbo}{fecha}{hora}{ub}{part}{dur}{suf}", {"part", "ub", "dur"}),
    ("{pref}{verbo}{fecha}{hora}{part}{ub}{record}{suf}", {"part", "ub", "record"}),
    ("{pref}{verbo}{fecha}{hora}{part}{suf}", {"part"}),
]
PLANTILLAS_CHAT_EN = [
    ("hey schedule {art} {titulo}{fecha}{hora}{part}{suf}", {"part"}),
    ("can you set up {art} {titulo}{fecha}{hora}{part}{ub}{suf}", {"part", "ub"}),
    ("pls add {art} {titulo}{fecha}{hora}{part}{ub}{dur}{suf}", {"part", "ub", "dur"}),
    ("need {art} {titulo}{fecha}{hora}{part}{record}{suf}", {"part", "record"}),
    ("reminder: {titulo}{fecha}{hora}{part}{recurr}{suf}", {"part", "recurr"}),
]

NULOS = {"part": [], "ub": None, "dur": None, "record": None, "recurr": None, "zona": ZONA_DEFAULT}


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------

def _norm_plano(s: str) -> str:
    s = s.lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _ngramas(s: str, n: int = 3) -> set:
    t = re.sub(r"[^a-z0-9 ]", " ", _norm_plano(s))
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < n:
        return {t}
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _unir(partes) -> str:
    return re.sub(r"\s+", " ", " ".join(p for p in partes if p)).strip()


def _esp(frag) -> str:
    return (" " + frag) if frag else ""


def _rellenar(plantilla: str, valores: dict) -> str:
    relleno = {k: _esp(v) for k, v in valores.items()}
    relleno["titulo"] = valores.get("titulo", "")
    relleno["pref"] = valores.get("pref", "")
    relleno["suf"] = valores.get("suf", "")
    relleno["verbo"] = valores.get("verbo", "")
    return re.sub(r"\s+", " ", plantilla.format(**relleno)).strip()


def _elegir(rng, catalogo, dirigido, patrones_dirigidos):
    """Con perfil dirigido, solo entra en juego la convencion de articulos."""
    if dirigido:
        pool = [c for c in catalogo if c[2] in patrones_dirigidos]
        return rng.choice(pool or catalogo)
    return rng.choice(catalogo)


# ---------------------------------------------------------------------------
# composicion de una muestra
# ---------------------------------------------------------------------------

def _muestra(rng: random.Random, idx: int, dirigido: bool = False) -> dict | None:
    es_dirigido_verbos = dirigido and rng.random() < 0.35

    estilo = rng.choices(
        ["formal_es", "chat_es", "formal_en", "chat_en"],
        weights=([0.15, 0.55, 0.10, 0.20] if dirigido else [0.32, 0.33, 0.20, 0.15]),
    )[0]
    es = estilo.endswith("es")
    chat = estilo.startswith("chat")

    catalogo = [e for e in EVENTOS if e[2] == ("es" if es else "en")]
    titulo_formal, titulo_chat, _ = rng.choice(catalogo)

    # --- slots ----------------------------------------------------------
    frag_fecha = None if rng.random() < 0.10 else rng.choice(FECHAS_ES if es else FECHAS_EN)
    frag_recurr, _gt_recurr = rng.choice(RECURRENCIAS_ES if es else RECURRENCIAS_EN)
    if frag_recurr and rng.random() < 0.7:
        frag_fecha = None

    usar_rango = es and rng.random() < 0.07   # los rangos "de 9 a 12" son en español
    hora_gt_rango, dur_rango = None, None
    if usar_rango:
        frag_hora, hora_gt_rango, dur_rango = rng.choice(RANGOS)
        frag_dur, gt_dur = None, dur_rango
    else:
        frag_hora = None if rng.random() < 0.14 else rng.choice(HORAS_ES if es else HORAS_EN)
        frag_dur, gt_dur = rng.choice(DURACIONES_ES if es else DURACIONES_EN)

    pats = ("quita", "conserva") if dirigido else ("quita", "conserva", "nombre", "ninguno")
    frag_part, gt_part, patron_part = _elegir(
        rng, PARTICIPANTES_ES if es else PARTICIPANTES_EN, dirigido, pats)

    frag_ub, gt_ub = rng.choice(UBICACIONES_ES if es else UBICACIONES_EN)
    frag_record, gt_record = rng.choice(RECORDATORIOS_ES if es else RECORDATORIOS_EN)
    frag_zona, _gt_zona = rng.choice(ZONAS_ES if es else ZONAS_EN)

    # --- titulo derivado del verbo (solo chat) --------------------------
    gt_titulo = titulo_formal
    verbo, etiqueta = "", ""
    if es_dirigido_verbos and chat and es:
        verbo, etiqueta = rng.choice(VERBOS_ETIQUETA)

    # 'virtual' solo se usa si la palabra aparece en la frase (viaja en el titulo)
    virtual = (frag_ub is None) and (not verbo) and (rng.random() < 0.10)
    if virtual:
        gt_ub = "virtual"

    valores = {
        "fecha": frag_fecha, "hora": frag_hora, "part": frag_part, "ub": frag_ub,
        "dur": frag_dur, "record": frag_record, "zona": frag_zona, "recurr": frag_recurr,
    }

    # --- montaje --------------------------------------------------------
    if verbo:
        plantilla, usados = rng.choice(PLANTILLAS_VERBO_ES)
        valores["pref"] = rng.choice(PREFIJOS_CHAT)
        valores["suf"] = rng.choice(SUFIJOS_CHAT)
        valores["verbo"] = verbo
        texto = _rellenar(plantilla, valores)
        gt_titulo = etiqueta              # etiqueta derivada: siempre capitalizada
        titulo_en_frase = False
    elif chat:
        titulo = titulo_chat
        if es:
            plantilla, usados = rng.choice(PLANTILLAS_CHAT_ES)
            valores["pref"] = rng.choice(PREFIJOS_CHAT)
            valores["suf"] = rng.choice(SUFIJOS_CHAT)
        else:
            plantilla, usados = rng.choice(PLANTILLAS_CHAT_EN)
            valores["pref"] = ""
            valores["suf"] = rng.choice(SUFIJOS_CHAT_EN)
            titulo = titulo.lower() if rng.random() < 0.5 else titulo
            valores["art"] = "an" if titulo[:1].lower() in "aeiou" else "a"
        valores["titulo"] = titulo + (" virtual" if virtual else "")
        texto = _rellenar(plantilla, valores)
        gt_titulo = titulo
        titulo_en_frase = True
    else:
        titulo = titulo_formal
        valores["titulo"] = titulo + (" virtual" if virtual else "")
        usados = {"part", "ub", "dur", "record", "zona", "recurr"}
        texto = _unir([
            valores["titulo"], frag_fecha, frag_hora, frag_dur, frag_part,
            frag_ub, frag_record, frag_zona, frag_recurr,
        ])
        gt_titulo = titulo
        titulo_en_frase = True

    # lo que la plantilla no renderiza NO se etiqueta
    usados = set(usados)
    if usar_rango:
        usados |= {"hora", "dur"}     # el rango aporta hora_inicio y duracion
    if virtual:
        usados |= {"ub"}              # "virtual" viaja pegado al titulo
    for clave, nulo in NULOS.items():
        if clave not in usados:
            if clave == "part":
                gt_part = list(nulo)
            elif clave == "ub":
                gt_ub = nulo
            elif clave == "dur":
                gt_dur = nulo
            elif clave == "record":
                gt_record = nulo

    # slots cuyo fragmento tiene valor y efectivamente aparece en la frase
    slots_con_valor = set()
    if "part" in usados and frag_part:
        slots_con_valor.add("part")
    if "ub" in usados and (frag_ub or virtual):
        slots_con_valor.add("ub")
    if "dur" in usados and (frag_dur or usar_rango):
        slots_con_valor.add("dur")
    if "record" in usados and frag_record:
        slots_con_valor.add("record")

    # --- estilo chat: minusculas / sin tildes ---------------------------
    if chat:
        texto = texto.lower()
        if not verbo:
            gt_titulo = gt_titulo.lower()
        gt_part = [p.lower() for p in gt_part]
        if gt_ub:
            gt_ub = gt_ub.lower()
        if rng.random() < 0.55:
            texto = _sin_tildes(texto)
            if not verbo:
                gt_titulo = _sin_tildes(gt_titulo)
            gt_part = [_sin_tildes(p) for p in gt_part]
            if gt_ub:
                gt_ub = _sin_tildes(gt_ub)

    # --- ground truth temporal con la herramienta del pipeline ----------
    info = analizar_temporal(texto, FECHA_REF)
    gt_fecha, gt_hora = info["fecha"], info["hora_inicio"]

    if (frag_fecha is not None) != (gt_fecha is not None):
        return None
    if usar_rango:
        if gt_hora != hora_gt_rango:
            return None
    elif (frag_hora is not None) != (gt_hora is not None):
        return None

    # el target es SOLO lo que produce el modelo (6 campos)
    target = {
        "titulo": gt_titulo,
        "hora_inicio": gt_hora,
        "duracion_minutos": gt_dur,
        "participantes": gt_part,
        "ubicacion": gt_ub,
        "recordatorio_minutos": gt_record,
    }

    campos_llenos = sum(v is not None and v != [] for v in target.values())
    if chat:
        categoria = "chat"
    elif frag_fecha is None or gt_hora is None:
        categoria = "edge_case"
    elif es and frag_fecha in FECHAS_RELATIVAS_ES:
        categoria = "ambigua"
    elif (not es) and frag_fecha in FECHAS_EN[:11]:
        categoria = "ambigua"
    elif campos_llenos >= 5:
        categoria = "compleja"
    elif gt_part:
        categoria = "con_participantes"
    else:
        categoria = "simple"

    return {
        "id": idx,
        "texto": texto,
        "target": target,
        "meta": {
            "estilo": estilo,
            "categoria": categoria,
            "patron_participantes": patron_part,
            "titulo_derivado": bool(verbo),
            "titulo_en_frase": titulo_en_frase,
            "dirigido": dirigido,
            "slots_con_valor": sorted(slots_con_valor),
            "gt_fecha": gt_fecha,
            "gt_fecha_expr": info["fecha_expr"],
        },
    }


# ---------------------------------------------------------------------------
# generacion con control de calidad
# ---------------------------------------------------------------------------

def generar(n: int, seed: int, frases_test: list, dirigido: bool = False,
            ratio_dirigido: float = 0.40) -> tuple[list, dict]:
    rng = random.Random(seed)
    ng_test = [_ngramas(f["texto"]) for f in frases_test]
    vistos = set()

    datos, descartados = [], {"solape_test": 0, "duplicado": 0, "autochequeo": 0, "intentos": 0}
    intentos, tope = 0, n * 40

    while len(datos) < n and intentos < tope:
        intentos += 1
        es_dirigida = dirigido or (rng.random() < ratio_dirigido)
        m = _muestra(rng, len(datos) + 1, dirigido=es_dirigida)
        if m is None:
            descartados["autochequeo"] += 1
            continue
        clave = re.sub(r"\s+", " ", _norm_plano(m["texto"])).strip()
        if clave in vistos:
            descartados["duplicado"] += 1
            continue
        if any(_jaccard(_ngramas(m["texto"]), t) > 0.60 for t in ng_test):
            descartados["solape_test"] += 1
            continue
        vistos.add(clave)
        datos.append(m)

    descartados["intentos"] = intentos
    return datos, descartados


def _resumen(datos: list) -> dict:
    return {
        "n": len(datos),
        "por_categoria": dict(Counter(d["meta"]["categoria"] for d in datos)),
        "por_estilo": dict(Counter(d["meta"]["estilo"] for d in datos)),
        "patrones_participantes": dict(Counter(d["meta"]["patron_participantes"] for d in datos)),
        "titulos_derivados": sum(1 for d in datos if d["meta"]["titulo_derivado"]),
        "con_fecha": sum(1 for d in datos if d["meta"]["gt_fecha"]),
        "sin_fecha": sum(1 for d in datos if not d["meta"]["gt_fecha"]),
    }


def main():
    ap = argparse.ArgumentParser(description="Dataset sintetico especializado (6 campos, sin fuga)")
    ap.add_argument("--n", type=int, default=3200, help="ejemplos de entrenamiento")
    ap.add_argument("--dev", type=int, default=200)
    ap.add_argument("--hard-dev", type=int, default=150, help="solo patrones dificiles")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--perfil", choices=["mixto", "fallos", "general"], default="mixto",
                    help="mixto=60%% general + 40%% dirigido; fallos=solo patrones dificiles")
    ap.add_argument("--out", default=RUTA_SALIDA)
    args = ap.parse_args()

    with open(RUTA_BENCHMARK, encoding="utf-8") as f:
        frases_test = json.load(f)["frases"]
    print("Benchmark2 (SOLO test): %d frases" % len(frases_test))

    solo_dirigido = args.perfil == "fallos"
    ratio = 1.0 if solo_dirigido else (0.0 if args.perfil == "general" else 0.40)
    datos, descartados = generar(args.n + args.dev, args.seed, frases_test,
                                 dirigido=solo_dirigido, ratio_dirigido=ratio)
    hard, desc_hard = generar(args.hard_dev, args.seed + 7, frases_test, dirigido=True)

    if len(datos) < args.n + args.dev:
        print("AVISO: solo se generaron %d ejemplos" % len(datos))

    rng = random.Random(args.seed + 1)
    rng.shuffle(datos)
    train, dev = datos[:args.n], datos[args.n:args.n + args.dev]

    os.makedirs(args.out, exist_ok=True)

    def escribir(ruta, filas):
        with open(ruta, "w", encoding="utf-8") as f:
            for fila in filas:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    escribir(os.path.join(args.out, "train.jsonl"), train)
    escribir(os.path.join(args.out, "dev.jsonl"), dev)
    escribir(os.path.join(args.out, "hard_dev.jsonl"), hard)

    with open(os.path.join(args.out, "prompts.json"), "w", encoding="utf-8") as f:
        json.dump({
            "fecha_referencia": P.FECHA_REFERENCIA,
            "dia_referencia": P.DIA_REFERENCIA,
            "prompt_directo": P.PROMPT_DIRECTO,
            "prompt_estructurado": P.PROMPT_ESTRUCTURADO,
            "prompt_semantico": P.PROMPT_SEMANTICO,
            "campos_contrato": P.CAMPOS_CONTRATO,
            "campos_modelo": CAMPOS_MODELO,
        }, f, ensure_ascii=False, indent=1)

    stats = {
        "seed": args.seed,
        "perfil": args.perfil,
        "descartados": descartados,
        "train": _resumen(train),
        "dev": _resumen(dev),
        "hard_dev": _resumen(hard),
    }
    with open(os.path.join(args.out, "estadisticas.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    print("train.jsonl    : %d" % len(train))
    print("dev.jsonl      : %d" % len(dev))
    print("hard_dev.jsonl : %d (solo patrones dificiles)" % len(hard))
    print("descartados    : %s" % descartados)
    print("train patrones : %s" % stats["train"]["patrones_participantes"])
    print("train titulos derivados: %d" % stats["train"]["titulos_derivados"])
    print("hard_dev patrones: %s" % stats["hard_dev"]["patrones_participantes"])
    print("\nEjemplos dirigidos:")
    for d in [x for x in hard if x["meta"]["titulo_derivado"]][:2] + [x for x in hard if x["meta"]["patron_participantes"] == "quita"][:2] + [x for x in hard if x["meta"]["patron_participantes"] == "conserva"][:2]:
        print("  " + d["texto"])
        print("    -> " + json.dumps(d["target"], ensure_ascii=False))


if __name__ == "__main__":
    main()

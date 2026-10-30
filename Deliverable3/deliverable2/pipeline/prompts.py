# -*- coding: utf-8 -*-
"""
prompts.py -- Fuente unica de verdad de los tres prompts del sistema.

A  PROMPT_DIRECTO     : baseline de prompting directo (configuracion de D1).
B  PROMPT_ESTRUCTURADO: instruccion estructurada + few-shot (mejora medida en D1).
D  PROMPT_SEMANTICO   : extraccion solo semantica, SIN campo 'fecha' (fine-tuning).
                        La fecha la resuelve pipeline.resolvedor_temporal.

Los placeholders {dia} y {fecha} se rellenan con aplicar_referencia().
Las llaves literales de los ejemplos JSON van dobles ({{ }}).
"""

FECHA_REFERENCIA = "2026-09-01"
DIA_REFERENCIA = "martes"

CAMPOS_CONTRATO = [
    "titulo", "fecha", "hora_inicio", "duracion_minutos", "participantes",
    "ubicacion", "recordatorio_minutos", "zona_horaria", "recurrence",
]

# Lo que produce el modelo. El resto del contrato lo calcula el sistema:
#   fecha -> pipeline.resolvedor_temporal | zona_horaria y recurrence -> reglas.
CAMPOS_SEMANTICOS = [
    "titulo", "hora_inicio", "duracion_minutos",
    "participantes", "ubicacion", "recordatorio_minutos",
]

# ---------------------------------------------------------------------------
# A. Baseline: prompting directo (sin schema, sin reglas, sin few-shot)
# ---------------------------------------------------------------------------

PROMPT_DIRECTO = """Dada la siguiente frase sobre una reunion, extrae los campos en formato JSON:
- titulo
- fecha (formato YYYY-MM-DD, null si no especifica)
- hora_inicio (formato HH:MM 24h, null si no especifica)
- duracion_minutos (numero, null si no especifica)
- participantes (lista de nombres, [] si no hay)
- ubicacion (texto, null si no especifica)
- recordatorio_minutos (numero, null si no especifica)
- zona_horaria (texto)
- recurrence (texto, null si no se repite)

Frase: "{frase}"

Respuesta (SOLO JSON):"""

# ---------------------------------------------------------------------------
# B. Instruccion estructurada + few-shot (reproduccion literal de D1)
# ---------------------------------------------------------------------------

PROMPT_ESTRUCTURADO = """Eres un extractor de datos de calendario.

REGLAS:
1. HOY ES {dia} {fecha}. Calcula fechas relativas desde esta fecha.
2. Si un campo NO se menciona, usa null (o [] para participantes). NUNCA inventes.
3. titulo: nombre breve del evento; elimina fecha, hora, participantes y ubicacion, pero conserva sus descriptores (p. ej., "Cita médica" o "Reunión de planificación"). Conserva el idioma de la frase.
4. fecha: YYYY-MM-DD. hora_inicio: HH:MM 24h.
5. duracion_minutos: entero (1 hora=60). Si no hay = null.
6. participantes: lista de nombres reales. Si no hay = [].
7. ubicacion: donde se realiza. Si no se menciona = null.
8. recordatorio_minutos: entero. Si no se menciona = null.
9. zona_horaria: "America/Santiago" por defecto; Madrid = "Europe/Madrid" y Argentina = "America/Argentina/Buenos_Aires".
10. Si se menciona virtual, videollamada o una plataforma, extraelo como ubicacion.
11. Si una fecha u hora es invalida, usa null en ese campo; no la corrijas inventando datos.

EJEMPLOS:

Frase: "Reunión con Ana el viernes a las 10am"
{{"titulo": "Reunión", "fecha": "2026-09-04", "hora_inicio": "10:00", "duracion_minutos": null, "participantes": ["Ana"], "ubicacion": null, "recordatorio_minutos": null, "zona_horaria": "America/Santiago"}}

Frase: "Reunión de 2 horas el 15/09 a las 9:30 en la sala de conferencias, recordar 30 min"
{{"titulo": "Reunión", "fecha": "2026-09-15", "hora_inicio": "09:30", "duracion_minutos": 120, "participantes": [], "ubicacion": "sala de conferencias", "recordatorio_minutos": 30, "zona_horaria": "America/Santiago"}}

Frase: "Reunión"
{{"titulo": "Reunión", "fecha": null, "hora_inicio": null, "duracion_minutos": null, "participantes": [], "ubicacion": null, "recordatorio_minutos": null, "zona_horaria": "America/Santiago"}}

Frase: "Meeting on Friday at 10am"
{{"titulo": "Meeting", "fecha": "2026-09-04", "hora_inicio": "10:00", "duracion_minutos": null, "participantes": [], "ubicacion": null, "recordatorio_minutos": null, "zona_horaria": "America/Santiago"}}

Frase: "Junta virtual mañana a las 5 con el profe"
{{"titulo": "Junta", "fecha": "2026-09-02", "hora_inicio": "17:00", "duracion_minutos": null, "participantes": ["el profe"], "ubicacion": "virtual", "recordatorio_minutos": null, "zona_horaria": "America/Santiago"}}"""

# ---------------------------------------------------------------------------
# D. Extraccion semantica (6 campos) para fine-tuning y brazo D
#     Sin few-shot: con miles de ejemplos supervisados los ejemplos en el prompt
#     son redundantes y solo alargan la secuencia. Las reglas si se conservan.
# ---------------------------------------------------------------------------

PROMPT_SEMANTICO = """Eres un extractor de datos de calendario.

REGLAS:
1. Devuelve SOLO JSON con estos seis campos: titulo, hora_inicio, duracion_minutos, participantes, ubicacion, recordatorio_minutos.
2. NO calcules ni devuelvas fechas: el campo fecha lo resuelve otro componente del sistema.
3. NO devuelvas zona_horaria ni recurrence: los calcula el sistema con reglas.
4. Si un campo NO se menciona, usa null (o [] para participantes). NUNCA inventes.
5. titulo: nombre breve del evento; elimina hora, participantes y ubicacion, pero conserva sus descriptores (p. ej., "Cita médica", "Reunión de planificación"). Conserva el idioma de la frase.
6. Si la frase es un verbo de encuentro sin nombre de evento (p. ej. "quedamos el viernes", "presentamos el lunes"), usa la etiqueta nominal del evento: "quedamos" -> "Quedada", "presentamos" -> "Presentación", "comemos" -> "Almuerzo".
7. hora_inicio: HH:MM 24h. Si no hay = null.
8. duracion_minutos: entero (1 hora=60). Si no hay = null.
9. participantes: nombres tal como se mencionan, PERO quitando el articulo inicial singular ("el"/"la"/"the"): "con el cliente" -> ["cliente"], "con la Dani" -> ["Dani"], "with the team" -> ["team"]. El articulo plural o total SI se conserva: "con los clientes" -> ["los clientes"], "con todo el equipo" -> ["todo el equipo"], "con los 5 directores" -> ["los 5 directores"]. Excepcion: "el profe" se conserva entero -> ["el profe"]. Si no hay = [].
10. ubicacion: donde se realiza. Si no se menciona = null.
11. recordatorio_minutos: entero. Si no se menciona = null."""


def aplicar_referencia(prompt: str, fecha_ref: str = FECHA_REFERENCIA, dia_ref: str = DIA_REFERENCIA) -> str:
    return prompt.format(dia=dia_ref, fecha=fecha_ref)


def _mensajes(system: str, frase: str) -> list:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": 'Frase: "%s"' % frase},
    ]


def mensajes_directo(frase: str) -> list:
    """Brazo A: el prompt directo va como mensaje unico de usuario."""
    return [{"role": "user", "content": PROMPT_DIRECTO.format(frase=frase)}]


def mensajes_estructurado(frase: str, fecha_ref: str = FECHA_REFERENCIA) -> list:
    return _mensajes(aplicar_referencia(PROMPT_ESTRUCTURADO, fecha_ref), frase)


def mensajes_semantico(frase: str) -> list:
    return _mensajes(PROMPT_SEMANTICO, frase)


def objetivo_semantico(gt: dict) -> dict:
    """Target de entrenamiento: campos semanticos del GT, sin 'fecha'."""
    r = {c: gt.get(c) for c in CAMPOS_SEMANTICOS}
    return r

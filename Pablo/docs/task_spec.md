# Task Spec — AGENDA: Agendado desde lenguaje natural (ES)

## Definición
**Input:**
- `utterance: string` — español coloquial, puede contener fechas relativas ("mañana", "próximo martes", "en dos semanas", "cada martes"), horas ambiguas ("a las 8"), rangos ("del 2 al 4"), múltiples eventos.
- `now: string ISO8601` — timestamp de referencia, siempre `America/Santiago` (ej. `2026-08-31T14:00:00-04:00`).
- `calendar_context: Array[Event]` — eventos existentes para detección de conflicto.

**Output:** `JSON Array[Event]` con schema estricto:
```json
{
  "title": "string (3-60 chars)",
  "start": "ISO8601 con offset America/Santiago",
  "end": "ISO8601 con offset America/Santiago",
  "attendees": ["string"],
  "location": "string | null",
  "rrule": "string RFC5545 (FREQ=WEEKLY;BYDAY=...) | null",
  "conflict": "bool"
}
```

**Pseudocódigo de validación:**
```python
def is_correct(pred, gold):
  assert json.loads(pred)  # válido
  assert pred.start.tz == "America/Santiago"
  assert pred.start == gold.start and pred.end == gold.end
  assert pred.conflict == overlaps(pred, calendar_context)
  assert pred.rrule == gold.rrule
```

## Criterio de éxito (para jurado)
Un output es **correcto** iff:
1. JSON parseable y todos los campos presentes con tipos correctos.
2. `start` y `end` exactos (tolerancia 0 min, timezone correcto).
3. `conflict` es `true` iff el intervalo solapa con algún evento en `calendar_context`.
4. Si hay recurrencia, `rrule` es RFC5545 válido; si no, `null`.

## Métricas
- **JSON-validity:** % parseable
- **Exact-Match temporal:** % con start y end idénticos a gold
- **Conflict-F1:** precisión/recall de detección de choque
- Reporte D1: 20 casos (10 simples / 10 trampas). D2+: 50 casos.

## Ejemplos
Ver `dataset/examples_es.json` — IDs 1-10 simples, 11-20 trampas (temporal, conflicto, recurrencia, ambigua, relativa, multi-evento, rango, coloquial, timezone).

## Por qué falla prompting directo
Documentado en notebook: Gemma-2-2B zero-shot obtiene 45% EM, 70% JSON válido. Modos: off-by-week, sin timezone, omite conflict, rrule rota, alucina campos. El semestre atacará con date-parsing auxiliado + constrained decoding + function calling.

## Scope
- ES solo, timezone America/Santiago, duración por defecto 1h si no se especifica.
- No maneja cancelación/reagendado en D1 (futuro).

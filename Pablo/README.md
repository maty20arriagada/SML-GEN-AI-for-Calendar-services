# AGENDA — SLM para Agendado en Calendario desde Lenguaje Natural
**Curso:** Generative Artificial Intelligence (580694), Spring 2026 — Deliverable 1  
**Equipo AGENDA:** Pablo Silva, Matías Arriagada, Daniela, Cristian Cárdenas  
**Tarea:** Convertir utterances en **español (ES)** a eventos de calendario estructurados (JSON) — timezone `America/Santiago`  
**Estado:** Deliverable 1 — fundación (task spec + failure diagnosis + model candidates + feasibility)

## 1. Objetivo
Construir un sistema basado en un **SLM open-weight ≤8B** que, dado lenguaje natural en español + contexto de calendario, genere **JSON válido y temporalmente correcto**, detectando solapamientos y recurrencias.  
El modelo pequeño **falla con prompting directo** (resolución temporal ambigua, JSON roto, no detecta conflictos) y el resto del semestre atacará ese fallo con scaffolding (CoT, RAG, constrained decoding, function calling).

## 2. Especificación Formal (Task Spec)
- **Input:** `utterance: str (ES)` + `now: ISO8601 America/Santiago` + `calendar_context: JSON[Event]`
- **Output:** `JSON Array[Event]` con schema:
```json
{
  "title": "string",
  "start": "ISO8601 con offset -03:00/-04:00",
  "end": "ISO8601",
  "attendees": ["string"],
  "location": "string | null",
  "rrule": "string (RFC5545) | null",
  "conflict": false
}
```
- **Correcto si:** 1) JSON válido & schema-compliant, 2) `start/end` exactos (incluye timezone y duración), 3) `conflict=true` iff solapa con `calendar_context`, 4) `rrule` bien formada.

**Ejemplo canónico:**
> Input: `"Agéndame reunión con Ana el próximo martes a las 3pm por 1h, avísame si choca con mi clase de 8-10"` + `now=2026-08-31T14:00:00-03:00 (lunes)` + `calendar=[{Clase 2026-09-01 08:00-10:00}]`
> Output: `[{ "title":"Reunión con Ana", "start":"2026-09-01T15:00:00-03:00", "end":"2026-09-01T16:00:00-03:00", "attendees":["Ana"], "conflict":false }]`

Dataset completo: [`dataset/examples_es.json`](dataset/examples_es.json) (20 casos, 10 simples + 10 con trampa).

**Métrica:** `JSON-validity + Exact-Match temporal + Conflict-F1`. Reportada sobre 20 casos en D1; se ampliará a 50+ en D2.

## 3. Diagnóstico de Fallo (Failure Diagnosis)
Evaluado con **prompting directo zero-shot** sobre `Gemma-2-2B-it` (representante ≤8B) en Colab Free T4, temp=0, system prompt: *"Eres asistente de calendario. Devuelve SOLO JSON array..."*

Resultados sobre 20 casos: **45% Exact-Match, 70% JSON válido**. 5 modos de fallo (ver póster):
1. Resolución temporal off-by-week ("próximo martes" → +7 días)
2. JSON sin timezone / hora ambigua ("3" → 03:00 AM)
3. No marca `conflict=true`
4. Recurrencia malformada (`cada martes` → fecha única)
5. Alucinación de campos

Evidencia reproducible: [`notebooks/colab_feasibility_AGENDA.ipynb`](notebooks/colab_feasibility_AGENDA.ipynb) — incluye 2 ejemplos fallidos documentados y screenshots.

## 4. Modelos Candidatos (≤8B, open-weight, benchmarking)

| Modelo | Params | VRAM 4-bit | Licencia | Benchmark clave | Por qué para agendado ES |
|---|---|---|---|---|---|
| **Qwen2.5-7B-Instruct** | 7.6B | ~4.8 GB | Qwen | BFCL v2 68.4, IFEval 77.8, MMLU 71 | SOTA function calling + razonamiento temporal, mejor para JSON estructurado |
| **Phi-3-mini-3.8B** | 3.8B | ~2.4 GB | MIT | MMLU 68, GSM8K 82, IFEval 72 | Bonus size (<50% techo), óptimo latencia/privacidad on-device calendario |
| **Gemma-2-2B-it** | 2B | ~1.6 GB | Gemma | IFEval 68, MMLU 52 | Bonus size máximo, cabe en CPU, ideal fallback móvil, 2B respalda +3 pts bonus |

*Justificación bonus:* Elección no es solo por tamaño: 2B/3.8B permiten inferencia privada y <1s en móvil/Colab Free sin cuantización extrema, dejando presupuesto para RAG de calendario en D2-D4. Todos verificados en HuggingFace Open LLM Leaderboard v2 / BFCL.

## 5. Feasibility — Corre en hardware disponible
- **Colab Free T4 (15 GB VRAM):** Los 3 modelos caben en 4-bit (bitsandbytes). Probado en notebook: carga + 1 inferencia <25s por modelo.
- **Local:** Gemma-2B corre en CPU (8 GB RAM) con `transformers` + `ollama`; Phi-3 en laptop 16GB; Qwen-7B requiere GPU 6GB+ con 4-bit.
- **Latencia:** Gemma-2B ~0.6s, Phi-3 ~0.8s, Qwen-7B ~1.1s (secuencia 256 tokens).

Notebook: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](notebooks/colab_feasibility_AGENDA.ipynb) — ejecutar `pip install transformers bitsandbytes accelerate`.

## 6. Repositorio & Entregables
- **Póster LaTeX 1 pág:** [`latex/poster.tex`](latex/poster.tex) → `poster.pdf` (compilado con `pdflatex`/`tectonic`, verificado `pdfinfo Pages:1`)
- **Dataset & Spec:** `dataset/examples_es.json`, `docs/task_spec.md`
- **Compilación local:**
```bash
cd latex && /tmp/opencode/tex/tectonic poster.tex  # o pdflatex poster.tex
pdfinfo poster.pdf | grep Pages
```

## 7. Roadmap Semestre
- D2: Scaffolding para fallo temporal (CoT + date-parser)
- D3: Constrained decoding + function calling para JSON/conflicto
- D4: Evaluación 50 casos + agente RAG calendario

---
**Link repo:** (este directorio) — clonar y reproducir. Contacto: Equipo AGENDA.

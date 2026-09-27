# Referencias y evidencia empírica para Deliverable 2

Mapa de papers organizados por **qué afirmación respaldan** y **qué mejora habilitan**.
Las claves citables están en `referencias.bib`.

---

## 1. El modelo no debe calcular fechas (justifica la herramienta)

| Ref | Hallazgo clave | Uso en nuestra entrega |
|---|---|---|
| `qian2023limitations` (ACL 2023) | Los LM fallan en tareas simbólicas elementales (copia, suma); ni CoT ni "LMs with callable programs" lo resuelven del todo | Cita directa para el diagnóstico: no pedirle al modelo aritmética de fechas |
| `bhatia2025datefragments` (EMNLP 2025) | La tokenización fragmenta fechas (`20250312` → `202, 503, 12`); la fragmentación correlaciona con caídas de hasta 10 pts en resolución de fechas | Mecanismo *por qué* Qwen3-4B falla en "pasado mañana", "en dos semanas": el cálculo temporal es frágil en LM |
| Gambardella et al., ACL 2024 (short) | Los LM aciertan el primer dígito de una multiplicación y fallan el último; el problema fácil es el que rompe | Apoyo al argumento "lo fácil determinista no lo delegues al modelo" — [link](https://aclanthology.org/2024.acl-short.8/) |

## 2. Tool use / delegar a código determinista funciona (la intervención)

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `schick2023toolformer` (NeurIPS 2023) | Los LM "struggle with arithmetic... where much simpler specialized models excel". Toolformer (modelo chico + calculadora y **calendario** como tools) supera a OPT-66B y GPT-3 | Evidencia fundacional de tool use; incluye literalmente un calendario como herramienta |
| `gao2023pal` (ICML 2023) | **PAL**: el LM descompone el problema y el intérprete ejecuta; +15 pts sobre PaLM-540B con CoT en GSM8K | El análogo exacto de nuestra tesis: "descomponer en el modelo, calcular en el intérprete" |
| MathSensei (NAACL 2024) | Tool-augmented LLM rinde mejor en problemas con cómputo complejo; en problemas simples la herramienta aporta menos | Apoya acotar la herramienta a lo que realmente falla (fechas relativas) — [link](https://aclanthology.org/2024.naacl-long.54.pdf) |

## 3. Resolución temporal por REGLAS = estado del arte clásico (valida el resolvedor)

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `strotgen2010heideltime` (SemEval 2010) | **HeidelTime**, basado en reglas, logra el mejor F1 (86%) y la mejor normalización de valores en TempEval-2, superando a sistemas de ML | La resolución de expresiones temporales se ha resuelto con reglas desde hace 15 años: nuestro resolvedor es el mismo patrón |
| `chang2012sutime` (LREC 2012) | **SUTime**, determinista por regex, supera al SOTA en TempEval-2. "Most temporal patterns can be captured effectively with rules". Limitación declarada: **lenguaje ambiguo** | (a) valida el resolvedor; (b) su límite ("the water from the spring") es análogo a nuestro failure case semántico |
| `stroetgen2015baseline` (EMNLP 2015) | HeidelTime multilingüe como baseline para todos los idiomas, **incluye español** | Si queremos ampliar la gramática del resolvedor, este es el punto de partida |

## 4. El razonamiento temporal sigue siendo difícil (sección de límites)

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `chu2024timebench` (ACL 2024) | TimeBench: incluso GPT-4 queda lejos de humanos en razonamiento temporal (aritmética de fechas, expresiones implícitas) | Contexto: el piso de error en fechas no es un bug nuestro, es un problema abierto |
| `bazaga2025tiser` (ACL 2025) | TISER (timeline + self-reflection): modelos abiertos pequeños superan a modelos cerrados mayores en tareas temporales | **Mejora posible**: pasar de verificación/autoreflexión sobre la fecha resuelta (test-time scaling) |
| `zheng2024naturalplan` (2024) | Natural Plan: en *Calendar Scheduling* GPT-4o y Gemini-1.5-Pro rinden 43.7% / 48.9%; el rendimiento se desploma con la complejidad | El scheduling desde NL es difícil incluso para modelos frontier → respalda medir con un set chico y declarado (n=45) |
| TIMO (COLM 2024) | Self-critic temporal optimization: integrar capacidad matemática mejora el razonamiento temporal | Alternativa evaluada (no adoptada: requiere fine-tuning) — [link](https://arxiv.org/abs/2406.14192) |

## 5. Function calling con modelos pequeños (model economy)

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `erdogan2024tinyagent` (EMNLP 2024) | TinyAgent-1.1B/7B fine-tuneados igualan o superan a GPT-4-Turbo en function calling **en su dominio**; usan **tool retrieval** para acortar el prompt | (a) modelo chico + herramientas puede ser suficiente; (b) **mejora posible**: retrieval de ejemplos few-shot |
| ToolACE (ICLR 2025) | Síntesis de datos para function calling; escala de 0.5B a 7B con ganancias fuertes en modelos chicos | Ruta de mejora si hubiera más tiempo: fine-tune con datos sintéticos — [link](https://arxiv.org/abs/2409.00920) |
| PA-Tool (2025) | Adaptar los **schemas** de las herramientas al modelo chico mejora tool-use hasta 17% sin reentrenar; reduce 80% los errores de schema | **Mejora barata**: simplificar/alinear el schema del prompt de extracción (ya lo hacemos al descomponer; se puede afinar) — [link](https://arxiv.org/abs/2510.07248) |
| Small Models, Big Tasks (EASE 2026) | SLMs son frágiles ante perturbaciones del input en function calling | Refuerza la necesidad de post-procesamiento determinista — [link](https://dl.acm.org/doi/full/10.1145/3756681.3757001) |

## 6. Salida estructurada (JSON)

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `geng2023grammar` (EMNLP 2023) | Grammar-constrained decoding garantiza JSON válido sin fine-tuning | **Mejora posible**: añadir decodificación restringida al prompt de extracción (complementa, no reemplaza, la herramienta de fechas) |
| Schema RL (ACL 2025) | Constrained decoding no alcanza con schemas complejos; SchemaBench lo mide | Por qué preferimos un schema chico y descompuesto sobre un schema monolítico de 9 campos — [link](https://aclanthology.org/2025.acl-long.243.pdf) |

## 7. Descomposición de tareas

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `zhang2025selectthendecompose` (EMNLP 2025) | Taxonomía de descomposición (tool-augmented vs pure-LLM, decomposition-first vs interleaved); dilema rendimiento-costo | Marco para situar nuestra intervención: "decomposition-first + tool-augmented" |
| ACONIC (2025) | Descomponer según complejidad formal mejora tareas de scheduling +15 pts | Apoyo a descomponer por tipo de subproblema (semántico vs temporal) — [link](https://arxiv.org/abs/2510.07772) |

## 8. Dominio calendario / agentes

| Ref | Hallazgo clave | Uso |
|---|---|---|
| `wijerathne2025scheduleme` (PACLIC 2025) | ScheduleMe: asistente multi-agente para Google Calendar desde NL | Trabajo relacionado directo (nosotros: un modelo chico + herramienta, no multi-agente) |
| ProEvent (2026) | "Models lacking robust temporal reasoning may benefit from auxiliary tools, such as calendar or calculator utilities" | Cita textual perfecta para nuestra intervención — [link](https://arxiv.org/html/2607.17701) |
| `yang2025qwen3` | Qwen3: 0.6B–235B, 119 idiomas, modo thinking/non-thinking, fuerte en tool usage (BFCL-v3 61.9 en 4B-Instruct-2507) | Ficha técnica del modelo comprometido |

---

## Mejoras accionables (ordenadas por costo/beneficio)

1. **Grammar-constrained decoding** en el paso de extracción (`geng2023grammar`): garantiza JSON válido y aísla los errores al contenido. Costo bajo (una librería tipo `outlines`/`xgrammar`).
2. **Alinear el schema al modelo chico** (`PA-Tool`): un solo objeto JSON plano, sin campos anidados, nombres cortos. Costo bajo.
3. **Verificación/autoreflexión de la fecha** (`bazaga2025tiser`): una segunda pasada que coteje `fecha` contra la expresión literal del texto; si no coincide, marcar para revisión en vez de inventar. Costo medio.
4. **Tool retrieval de ejemplos few-shot** (`erdogan2024tinyagent`): seleccionar los k ejemplos más similares a la frase en vez de los 5 fijos. Costo medio.
5. **Ampliar la gramática del resolvedor con patrones de HeidelTime/SUTime** (`stroetgen2015baseline`): duraciones, recurrencia (`cada semana`), rangos (`de 9 a 12`) — cubre el campo `recurrence` del contrato de 9 campos. Costo bajo/medio.
6. **Fine-tuning con datos sintéticos de function calling** (`ToolACE`) o DPO sobre cadenas correctas/incorrectas: ruta más pesada, solo si sobra tiempo (riesgo con la fecha límite).

## Nota de honestidad

- Las entradas de `referencias.bib` con `and others` tienen la lista de autores incompleta a propósito: el dato verificado es primer autor + año + venue. Completar antes de la versión final si se citan en el PDF.
- Las referencias de la sección 5 (PA-Tool, ToolACE, EASE 2026) y 6–8 están como enlace en este archivo; si entran al PDF, agregarlas al `.bib` con los autores del artículo.

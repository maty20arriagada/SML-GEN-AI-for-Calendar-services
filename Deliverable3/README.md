# CalendarBot — Deliverable 3: sistema de agentes

Mensaje en lenguaje natural (ES/EN, formal o de chat) → evento de calendario con un contrato de 9 campos
(`titulo, fecha, hora_inicio, duracion_minutos, participantes, ubicacion, recordatorio_minutos, zona_horaria, recurrence`).
Es la misma tarea, la misma falla y el mismo criterio de "correcto" de los Deliverables 1 y 2 (`evaluar.py`: los 8 campos
puntuables coinciden con el ground truth, `null`/`[]` si falta información, nada inventado). El sistema reconstruye la solución
del D2 (Qwen3-4B-Instruct-2507 + LoRA `checkpoint-300` + resolvedor temporal) como **cuatro agentes**.

**Video (≤3 min):** PEGAR_LINK_DEL_VIDEO · **Documento:** `documento/deliverable3.pdf`

**Un solo modelo para todos los agentes:** `Qwen/Qwen3-4B-Instruct-2507` (4 B parámetros) con el adapter LoRA del D2.
Hardware: Google Colab, Tesla T4 (15,6 GB), fp16.

## Los agentes

| Agente | Rol | Qué decide | Herramientas | Prompt (versionado) |
|---|---|---|---|---|
| **A1 Triage** | ¿hay un evento agendable? | `continuar` / `rechazar` (detiene el flujo) | `detectar_expresion_temporal` | `deliverable3/prompts/a1_triage_v2.txt` |
| **A2 Extractor** | 6 campos semánticos (LoRA) | pasa; si su JSON no es válido se reintenta una vez | — | `deliverable3/prompts/a2_extractor_v1.txt` |
| **A3 Temporal** | fecha, hora, duración, recordatorio, zona, recurrencia | qué herramientas llamar, cuándo `terminar` (≤3 pasos; respaldo declarado si su JSON es inválido dos veces) | `resolver_fecha`, `normalizar_hora`, `calcular_duracion`, `extraer_recordatorio`, `extraer_zona_horaria`, `extraer_recurrencia`, `expandir_participantes` | `deliverable3/prompts/a3_agente_v1.txt` |
| **A4 Verificador** | auditar el evento contra la frase | `aprobar` / `corregir` / `devolver_a_A3` (máx. 1 vuelta) | `validar_contrato` | `deliverable3/prompts/a4_agente_v1.txt` |

Código: `deliverable3/agentes_v3.py` (agentes), `deliverable3/grafo_v4.py` (orquestador con el bucle A4→A3 y el baseline E0),
`deliverable3/tools.py` + `tools_v2.py` (herramientas deterministas), `deliverable3/trazas.py` (registro de mensajes).
Prompts de las ablaciones: `a3_sin_tools_v1.txt` (T1), `a4_sin_fewshot_v1.txt` (T2), `a4_sin_cot_v1.txt` (T3). Los demás archivos de
`prompts/` pertenecen a los intentos anteriores (E2/E3) y se conservan solo por reproducibilidad.

## Brazos y técnicas

| Brazo | Qué es |
|---|---|
| `E0` | prompt directo (`PROMPT_DIRECTO` del D2) con el modelo base, sin LoRA ni agentes |
| `E1` | solución del D2: LoRA + resolvedor temporal |
| `E4` | sistema de agentes completo |
| `E4T1` … `E4T5` | `E4` quitando una técnica a la vez: T1 herramientas en A3 · T2 few-shot contrastivo en A4 · T3 rúbrica/CoT en A4 · T4 verificador y bucle A4→A3 · T5 compuerta de triage A1 |

Inputs (n = 160, mismo criterio): **A** 93 (`frases.json` + `benchmark_ft.json`, donde se hizo el diagnóstico), **B** 41
(`benchmark_heldout.json`, validación por clase de falla construida tras el análisis de errores), **C** 26
(`benchmark_independiente.json`, frases redactadas sin conocer el sistema ni sus resultados). `fecha_referencia` = 2026-09-01 (martes).

## Reproducir lo que muestra el video

1. Abrir `subir_a_colab/deliverable3_colab.ipynb` en Google Colab con GPU **T4**.
2. Seguir `subir_a_colab/LEEME_COLAB.txt` (sube `d3_proyecto.zip`, el adapter y `d3_previos.zip`).
3. Celda **8** (smoke) y celda **DEMO**: imprimen, para cada input, los **mensajes entre agentes y herramientas** (`A1 → A2 → A3 ⇄ herramientas → A4 → salida`) y el evento final, junto a lo que da E1 sobre la misma frase. Eso es lo que se ve en el video.
4. Celdas **9** (corrida) y **10** (resultados): producen la tabla de resultados (E0, E1, E4, ablaciones) y `comparacion_d3_v4.json`.

Los resultados de la corrida real y las trazas de **todos** los inputs están en `resultados/` (`resultados_{brazo}_{bench}.json`,
`traces/trazas_{brazo}_{bench}.jsonl`, `traces/video/demo_*_E4.jsonl`), con `hardware_intento3.json`. El caso de falla del documento
es el registro `id` 20 de `resultados/traces/trazas_E4_benchmark_independiente.jsonl` (copia en `traces/falla/E4_independiente_id20.jsonl`).

Los números del PDF no se copian a mano: `documento/numeros.tex` se regenera desde los zips de resultados con

```
cd documento && python hacer_numeros.py ../subir_a_colab/d3_previos.zip ../d3_resultados_intento3.zip fallo.tex
```

El adapter LoRA (`subir_a_colab/adapter_model.safetensors`) pesa unos 132 MB: GitHub no acepta archivos de más de 100 MB sin
Git LFS, así que en el repositorio va con LFS (`git lfs track "*.safetensors"`) o como archivo de un release.

## Demo en vivo con Google Calendar

`subir_a_colab/demo_calendarbot_d3.ipynb` (se regenera con `python demo_vivo/generar_notebook_demo.py`): chat en Colab T4 (formato de la demo del D2: celda con formulario, pregunta lo que falta, muestra E1 al lado) que corre E4
sobre la frase, muestra qué decidió cada agente y crea el evento en el calendario «CalendarBot» de Google con
`demo_vivo/calendario.py` (el del Deliverable 2, sin cambios). Un evento rechazado por A1 no se envía; si falta fecha u hora, el bot lo pregunta; si falla la API
queda un `.ics` de respaldo. Necesita un `credentials.json` propio (cliente OAuth «Desktop app»), que no va en el zip ni en el repositorio.

## Probar el código sin GPU

```
python -m unittest discover -s deliverable3/tests -t .        # 142 tests, modelo simulado
(cd deliverable2 && python -m unittest discover -s tests)     # 28 tests de D2
python deliverable3/preparar_zip.py                           # regenera d3_proyecto.zip para Colab
```
El modelo real solo corre en Colab; los tests usan motores simulados con el mismo método `generar(mensajes)`.

## Estructura

```
demo_vivo/          demo en vivo: calendario.py (Google/Outlook/.ics, de D2), demo_calendar.py y generador del notebook
deliverable3/       agentes, orquestador, herramientas, trazas, prompts/ y tests/
deliverable2/       pipeline de D2 que se reutiliza (resolvedor temporal, normalización, prompts del baseline)
frases.json  benchmark_ft.json  benchmark_heldout.json  benchmark_independiente.json  evaluar.py  benchmark_ft.py
subir_a_colab/      notebook, zips y adapter que se suben a Colab
resultados/         resultados de la corrida real por brazo y conjunto, hardware y traces/ (todas las trazas + video/)
traces/falla/       traza del caso de falla del documento
d3_resultados_intento3.zip   zip descargado de Colab (fuente de documento/numeros.tex)
documento/          deliverable3.tex (PDF de una página), numeros.tex, fallo.tex y hacer_numeros.py
```

Continuidad con los intentos anteriores: `intento1` (D2 + primer sistema E1/E2, 93 inputs) e `intento2` (E3, reglas deterministas en A3/A4)
quedaron como evidencia del diagnóstico que originó este diseño (no se incluyen aquí; los resultados suyos que se reutilizan, E1 en A y B y el caché del modelo, van en `subir_a_colab/d3_previos.zip`); el caso de falla del documento y su traza se describen en `documento/deliverable3.tex`.

# AGENTS.md

Deliverable 2 de la tarea semestral de *Generative Artificial Intelligence (580694)*:
convertir mensajes en lenguaje natural (ES/EN, informales) en un JSON de evento de
calendario de 9 campos. Python 3.11 puro + notebooks de Colab; no hay build system,
lint ni typecheck configurados. `python -m unittest` es la única verificación.

## Reglas que rompen el entregable si se ignoran

- **`benchmark/benchmark2.json` (45 frases) es SOLO test.** Nunca entrenar ni ajustar
  prompts con él: entrenar con él invalida la evidencia (fuga de datos). El dataset de
  entrenamiento es sintético y se genera con `datos/generar_dataset.py`.
- **`evaluar.py` es el archivo original de D1 y no se modifica.** `experimentos/evaluar_todo.py`
  lo carga vía `importlib` para conservar el criterio de corrección. Reimplementar la
  métrica invalida la comparación con D1.
- **Se emiten 9 campos pero se evalúan 8.** `recurrence` se emite con semántica `null`
  (el ground truth no lo trae); los evaluados son `evaluar.py:CAMPOS_OBLIGATORIOS`.
- **Los resultados con modelo mock van sellados `entorno: "MOCK (no es evidencia)"`.**
  Nunca presentarlos como evidencia; los reales llegan de Colab con `entorno: "hf:..."`.
- `docs/tabla_resultados.tex`, `datos/train.jsonl`, `datos/dev.jsonl` y
  `resultados/reporte_*.csv` son **generados**: no editar a mano.
- **`correr_experimento.py` sobrescribe `resultados/resultados_{brazo}.json` y
  `evaluar_todo.py` sobrescribe `reporte_*.csv`, `resumen.json` y `tabla_resultados.tex`.**
  Una corrida `--mock` ya no puede pisar resultados reales (el script lo bloquea); si
  necesitas smoke tests, usa `--salida resultados/mock`. Los resultados reales solo se
  regeneran desde Colab.

## Comandos verificados

```bash
python -m unittest discover -s tests        # 28 tests: resolvedor 45/45 + pipeline + API
python datos/generar_dataset.py --n 3200 --dev 200 --hard-dev 150 --seed 42   # regenera train/dev/hard_dev
python datos/validar_dataset.py             # debe decir "TOTAL problemas: 0"
python datos/preparar_zip.py                # genera proyecto.zip para Colab
python experimentos/correr_experimento.py --brazo D --mock     # smoke sin GPU
python experimentos/correr_experimento.py --brazo D --adapter <ruta-loRA>
python experimentos/evaluar_todo.py         # métricas + tabla LaTeX (no requiere GPU)
python calendario/demo_local.py [--real] [--ics]   # end-to-end: baseline vs solución + evento
```

Las corridas del modelo real (brazos A-D sobre las 45 frases) se hacen en **Colab T4**
(`notebooks/deliverable2_colab.ipynb`); los resultados se bajan a `resultados/` y luego
`evaluar_todo.py` se puede correr en local.

## Brazos experimentales (mismas 45 frases, mismo criterio)

| Brazo | Prompt | Fecha | Qué mide |
|---|---|---|---|
| A | directo (baseline de D1) | modelo | línea base |
| B | estructurado + few-shot | modelo | aporte del prompt |
| C | estructurado + few-shot | `resolvedor_temporal` | aporte de la herramienta |
| D | semántico (fine-tunneado) | `resolvedor_temporal` | solución final |

Definidos en `pipeline/pipeline.py:BRAZOS`. Resultados actuales (modelo base, sin adapter):
A 2.2% / B 73.3% / C 82.2% / D 84.4% de exactitud. Ojo: `resultados_D.json` está
**reconstruido** desde las métricas y los casos de fallo de la corrida real (el original se
perdió); reproduce métricas idénticas, pero re-correr el brazo D en Colab deja el archivo crudo.

## Arquitectura

- `pipeline/resolvedor_temporal.py` — herramienta **determinista** de fechas/horas. El
  modelo nunca calcula fechas en los brazos C/D. Los tests exigen que resuelva las 45/45
  frases del benchmark; si cambias la gramática, deben seguir en verde.
- `pipeline/normalizacion.py` — extracción de JSON del modelo + ensamblado del contrato
  de 9 campos. `ensamblar_evento(..., fecha_desde_tool=True|False)` decide quién calcula la fecha.
- `pipeline/prompts.py` — única fuente de los 3 prompts (directo / estructurado / semántico).
- `pipeline/modelo.py` — `GeneradorHF` (transformers, requiere GPU) y `GeneradorMock` (tests).
- `calendario/calendar_api.py` — API local que sustituye a Google Calendar (misma interfaz
  que `events.insert`); desviación declarada en el documento.
- `entrenamiento/qlora_colab.ipynb` — QLoRA 4-bit del extractor **semántico** (sin campo
  `fecha`). El adapter resultante va en la variable `ADAPTER` de `notebooks/deliverable2_colab.ipynb`.

## Quirks de este entorno (win32 + PowerShell 5.1)

- `python -c "..."` con comillas dobles dentro: PowerShell se las come. Usar comillas
  simples dentro del código Python o escribir un `.py` temporal.
- **Nunca usar `Compress-Archive` para `proyecto.zip`**: guarda las rutas con `\` y en
  Colab (Linux) el zip se extrae como archivos planos, sin el paquete `pipeline/`.
  Usar `python datos/preparar_zip.py` (separadores POSIX).
- Hay `torch` **CPU** instalado (transformers 5.17 / trl 0.21 / peft 0.21) solo para el
  smoke test del motor: `python entrenamiento/qlora_entrenar.py --smoke --max-steps 6 --accum 2`.
  Nunca entrenar ni inferir con la GTX 1650 local; el entrenamiento real va en Colab T4.
- **Máscara de loss**: `qlora_entrenar.py` pretokeniza y construye `completion_mask` él
  mismo. No volver a delegar en trl 0.21: con transformers v5 enmascara 2 tokens y
  entrena sobre todo el prompt de sistema. El prompt ocupa ~520 tokens: `max_length`
  se mide de los datos (con 384 se truncaba el 100% de los ejemplos).
- El MCP de Colab (`colab-mcp`) está registrado en la config local de Claude Code de
  este proyecto; carga al iniciar sesión y requiere abrir la conexión con el navegador.
- En T4 se usa **fp16**, nunca `bf16` (T4 no lo soporta de forma nativa).

## Referencias

- `docs/referencias.md` / `docs/referencias.bib` — papers que respaldan la intervención
  (PAL, Toolformer, HeidelTime/SUTime) y las mejoras pendientes; listos para citar en el LaTeX.
- `docs/deliverable1.tex` — entrega de D1 (estilo del documento de una página).
- `datos/train.jsonl` — el target de entrenamiento son **6 campos semánticos** (`titulo`,
  `hora_inicio`, `duracion_minutos`, `participantes`, `ubicacion`, `recordatorio_minutos`);
  `meta.gt_fecha` es solo trazabilidad. `hard_dev.jsonl` son solo patrones difíciles
  (artículos de participantes, títulos derivados del verbo) y se usa para early stopping.

# SML-GEN-AI-for-Calendar-services

Convertir mensajes en lenguaje natural (español/inglés, incluidos mensajes informales
tipo WhatsApp/Telegram) en un **evento JSON de calendario de 9 campos**, listo para una
API de calendario. Proyecto del ramo *Generative Artificial Intelligence (580694)*.

**Modelo comprometido:** `Qwen/Qwen3-4B-Instruct-2507` (4.0B, Apache 2.0) + adapter LoRA
propio. **Intervención:** fine-tuning del extractor semántico + herramienta determinista
de resolución de fechas.

> **Experimento de tamaño (rubro *Model economy*)**: el notebook de entrenamiento acepta
> modelos de 0.5B / 1.7B / 4B (`MODELO_ACTUAL`). La regla es quedarse con el **más chico
> que cumpla la barra** (≥ 95% en Benchmark2 corriendo el brazo D). Si se usa un modelo
> fuera de los 3 candidatos de D1, la desviación se declara y se defiende en el documento:
> *tarea angosta de extracción; un modelo chico fine-tunneado iguala al 4B con prompting*.

```
mensaje ──> [1] Qwen3-4B + LoRA     -> 6 campos semanticos (sin fecha)
        ──> [2] resolvedor_temporal -> fecha (determinista)
        ──> [3] normalizacion      -> contrato de 9 campos
        ──> [4] calendar_api       -> evento + .ics
```

## Reproducción

### En tu máquina (solo CPU, sin GPU)

```bash
python -m unittest discover -s tests          # 28 tests
python datos/generar_dataset.py --n 3200 --dev 200 --hard-dev 150 --seed 42
python datos/validar_dataset.py               # debe decir "TOTAL problemas: 0"
python experimentos/evaluar_todo.py           # metricas + tabla LaTeX
python calendario/demo_local.py --ics         # demo end-to-end (modelo mock)
python datos/preparar_zip.py                  # proyecto.zip para Colab
```

Esto **no usa la GPU**: generar datos, testear, evaluar resultados y compilar LaTeX son
tareas de CPU de segundos.

### En Google Colab (GPU T4 — entrenamiento e inferencia)

1. `python datos/preparar_zip.py` → sube `proyecto.zip` al notebook.
2. Abre `notebooks/deliverable2_colab.ipynb` (`Archivo → Subir notebook`) y activa **T4**.
3. Ejecuta en orden: carga del proyecto, brazos A-D, evaluación, celda DEMO.
4. Para entrenar el adapter: `entrenamiento/qlora_colab.ipynb` (config completa para T4,
   con evaluación por exact-match sobre `hard_dev`). El adapter se guarda en HF Hub/Drive
   y se pasa a `ADAPTER` en `deliverable2_colab.ipynb`.

## Brazos experimentales (mismas 45 frases, mismo criterio)

| Brazo | Prompt | Fecha | Qué mide |
|---|---|---|---|
| A | directo (baseline de D1) | modelo | línea base |
| B | estructurado + few-shot | modelo | aporte del prompt |
| C | estructurado + few-shot | `resolvedor_temporal` | aporte de la herramienta |
| D | semántico (fine-tunneado) | `resolvedor_temporal` | solución final |

Resultados en Benchmark2 (n=45, criterio de `evaluar.py` de D1):

| Brazo | Exactitud | titulo | fecha | participantes |
|---|---|---|---|---|
| A | 2.2% | 82.2 | 4.4 | 80.0 |
| B | 73.3% | 95.6 | 84.4 | 86.7 |
| C | 82.2% | 95.6 | **100** | 86.7 |
| D | 84.4% | 97.8 | **100** | 86.7 |

*(D con modelo base, sin adapter. Con el fine-tune la meta es ≥ 95%.)*

## Reglas del proyecto

- **Benchmark2 (45 frases) es SOLO test.** Nunca entrenar con él: los datos de
  entrenamiento son sintéticos (`datos/generar_dataset.py`).
- **`evaluar.py` es el archivo de D1 y no se modifica** — `evaluar_todo.py` lo importa
  para conservar el criterio de corrección.
- **Se emiten 9 campos, se evalúan 8** (`recurrence` con semántica `null`).
- Los resultados con modelo mock llevan sello `MOCK (no es evidencia)`.
- Ver `AGENTS.md` para el detalle de comandos y quirks del entorno.

## Anexo: descargar y probar el modelo en tu equipo

Todo el entrenamiento corre en Colab. Si quieres quedarte el modelo:

```bash
# adapter LoRA (lo que nosotros entrenamos, ~20-50 MB)
huggingface-cli download <usuario>/qwen3-4b-semantic-lora

# modelo base (publico, Apache 2.0, ~8 GB fp16)
huggingface-cli download Qwen/Qwen3-4B-Instruct-2507
```

Para **usarlo en tu máquina**:

- **GPU con poca VRAM (4 GB)**: usa una versión cuantizada 4-bit (~2-2.5 GB) vía
  `bitsandbytes`/GPTQ/AWQ. El modelo en fp16 (8 GB) **no cabe** en 4 GB de VRAM.
- **Solo CPU, sin tocar la GPU** (lo más amable con el equipo): exporta a **GGUF** y
  correlo con `llama.cpp`:
  ```bash
  python convert_hf_to_gguf.py qwen3-4b-semantic-merged --outfile modelo.gguf --outtype q4_k_m
  ./llama-cli -m modelo.gguf -p 'Frase: "agenda reunion manana 10am porfa"' -n 128
  ```
  Cero carga sobre la GPU, sin instalar `torch`.

**Advertencias**
1. Descargar ≠ correr bien: cuantiza antes de inferir en GPUs pequeñas.
2. El campo `fecha` no lo da el modelo — se resuelve con `pipeline/resolvedor_temporal.py`.
   Para el contrato completo, corre el pipeline (`calendario/demo_local.py --real`),
   no el modelo desnudo.

## Instrucciones del video (≤3 min)

| Tiempo | Qué debe verse |
|---|---|
| 0:00-0:30 | Diagnóstico D1 + brazo **A** (baseline) sobre la frase elegida |
| 0:30-1:30 | Brazo **D** corriendo en Colab sobre la **misma** frase |
| 1:30-2:15 | Evento creado en el calendario + tabla A-D (n=45) |
| 2:15-2:45 | Failure case y límites |
| 2:45-3:00 | Repositorio y cómo reproducirlo |

Pasos técnicos:
1. En Colab (GPU T4), ejecuta la celda **DEMO** de `notebooks/deliverable2_colab.ipynb`.
2. Graba la pantalla con OBS (o la grabadora del sistema) desde antes de ejecutar la celda,
   **sin cortes que oculten la ejecución** — solo se ve hasta el minuto 3:00.
3. Usa una frase que no la favorezca (p. ej. `q onda, quedamos el viernes a las 7 en lo de siempre?`
   o `agenda reunion manana 10am porfa`) y muestra baseline y solución sobre esa misma frase.
4. Sube el video a YouTube **con link abierto** y adjunta el enlace.

## Estructura

```
pipeline/        resolvedor_temporal, prompts, normalizacion, modelo, pipeline
benchmark/       benchmark1.json (35) y benchmark2.json (45) con ground truth
datos/           generador de dataset sintetico, validador, train/dev/hard_dev
entrenamiento/   qlora_colab.ipynb (fine-tuning en T4)
experimentos/    correr_experimento.py (brazos A-D), evaluar_todo.py
calendario/      calendar_api.py (API local), demo_local.py
notebooks/       deliverable2_colab.ipynb (pipeline completo + DEMO)
tests/           28 tests (resolvedor 45/45, pipeline, API)
docs/            referencias, deliverable1.tex, tabla_resultados.tex
```

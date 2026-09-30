# CalendarBot — natural language → calendar event

**Generative Artificial Intelligence (580694), Spring 2026 · Universidad de Concepción**
Team: Matías Arriagada · Cristian Cárdenas · Pablo Silva · Daniela Vidal
Repository: <https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services>

This README reproduces exactly what the Deliverable 2 video shows: the same notebook, the same input, the
same baseline bubble on screen, and the same benchmark numbers.

---

## 1. What the system does

A Spanish or English message (formal or informal) is converted into a calendar-ready event:

```json
{
  "titulo": "...", "fecha": "YYYY-MM-DD", "hora_inicio": "HH:MM",
  "duracion_minutos": 60, "participantes": ["..."], "ubicacion": "...",
  "recordatorio_minutos": 10, "zona_horaria": "America/Santiago",
  "recurrencia": { "frecuencia": "weekly", "intervalo": 1, "dias": ["monday"], "hasta": null, "veces": null }
}
```

An output counts as correct only if **every scored value matches the ground truth**, mentioned data is
preserved, `null` / `[]` is used when information is missing, and **nothing is invented**. Relative dates are
computed from the reference day **2026-09-01 (Tuesday)**.

## 2. The failure this fixes (diagnosis from Deliverable 1)

With the minimal instruction *"schedule this meeting"* (no schema, no field list), **0 of 45** Benchmark2
phrases produce parseable JSON: the model answers in prose, reformulates the request and invents dates and
participants. With a structured instruction the output becomes usable, but an error floor remains and it is
concentrated in **relative-date resolution** (and in title/participant discipline).

Deliverable 2 attacks that floor with two explicit changes:

1. **Dates leave the LLM.** `resolvedor_temporal.py` computes the date with an auditable grammar. If the
   expression is not in the grammar it returns `null` — it never invents. Timezone and recurrence are also
   computed by rules, not by the model.
2. **The remaining six fields are fine-tuned.** A LoRA adapter (`qwen3-4b-semantic-lora`, `checkpoint-300`)
   is trained on the same structured prompt (`PROMPT_SEMANTICO`) the benchmark uses.

Baseline and solution share the model, the prompt, the resolver and the correctness criterion; **only the
adapter differs**.

## 3. Selected model

| Candidate (Deliverable 1) | Params | Accuracy | Relative dates | Invented |
|---|---|---|---|---|
| **Qwen3-4B-Instruct-2507** ✅ | 4.0B | **64.4 %** | **82.2 %** | **0** |
| Phi-4-Mini | 3.8B | 51.1 % | 68.9 % | 1 |
| Phi-3.5-Mini | 3.8B | 46.7 % | 64.4 % | 5 |

`Qwen/Qwen3-4B-Instruct-2507` (Alibaba, version `2507`), with adapter
`qwen3-4b-semantic-lora/checkpoint-300`. Highest score of the trio, best relative dates, zero invented values,
and it beats larger models — scale does not buy temporal reasoning.

## 4. Files

**This deliverable**

| File | What it is |
|---|---|
| `chat_calendarbot_lora.ipynb` | **The demo notebook.** Message → fine-tuned extractor → temporal resolver → 9-field JSON → Google Calendar (or `.ics`). Shows the direct-prompting baseline next to the solution on the same input. |
| `benchmark_antes.ipynb` | Benchmark of the base model (no adapter) over `frases.json` (45) and `benchmark_ft.json` (48). Produces `resultados_antes.zip`. |
| `benchmark_despues.ipynb` | Same benchmark with the LoRA merged, plus the before/after comparison. Produces `resultados_despues.zip` and `comparacion.zip`. |
| `resultados_antes.zip`, `resultados_despues.zip` | Raw model outputs, per-phrase reports and hardware record of each run. |
| `comparacion.zip` | `comparacion_frases.json`, `comparacion_benchmark_ft.json` (including McNemar p-values) and both `hardware_*.json`. |
| `informe/entregable2.tex`, `informe/entregable2.pdf` | One-page technical document (LaTeX, pipeline diagram, results, limits). |

**From Deliverable 1** (already in this repository): task specification, `Benchmark2` with ground truth,
`evaluar.py` (the correctness criterion used here), the baseline/improved Qwen3 notebooks and the CSV reports
of the four models.

The benchmark notebooks open with five `%%writefile` cells (`resolvedor_temporal.py`, `evaluar.py`,
`benchmark_ft.py`, `frases.json`, `benchmark_ft.json`) that materialise those files in the working directory;
the chat notebook writes `calendario.py` and `resolvedor_temporal.py`. Running a notebook once therefore also
gives you the tools used in section 8.

## 5. Requirements

* Google Colab with a **Tesla T4** GPU (Runtime → Change runtime type → GPU). The benchmark asserts CUDA.
* Installed by the first code cell of every notebook (“1. Instalar dependencias”), pinned to the versions the
  adapter was trained with: `transformers==5.17.0`, `peft==0.21.0`, `accelerate==1.15.0`.
* Adapter files: `adapter_config.json` and `adapter_model.safetensors` from `checkpoint-300`
  (uploaded when the notebook asks, or read from the shared Drive folder `qwen3-4b-semantic-lora/checkpoint-300`).
* Google Calendar is optional: `credentials.json` (OAuth desktop client) and, optionally, `token_google.json`.
  Without them use `DESTINO = "solo .ics"` — everything else in the video works the same.

## 6. Reproduce what the video shows (Part A)

Notebook: **`chat_calendarbot_lora.ipynb`**, GPU T4, run the cells in order (cells are referenced by the title
shown in Colab):

1. **“1. Instalar dependencias”** – installs the pinned versions and checks that the GPU is a T4.
2. **The two `%%writefile` cells that follow** – write `calendario.py` (payload builders for Google/Outlook +
   `.ics` fallback) and `resolvedor_temporal.py` (the deterministic date grammar).
3. **“4. Subir credenciales de Google”** – upload `credentials.json` and optionally `token_google.json`.
   *Skip it and set `DESTINO = "solo .ics"` if you only want the `.ics` file.*
4. **“5. Ubicar el adapter LoRA (checkpoint-300)”** – `subir archivos` → upload `adapter_config.json` and
   `adapter_model.safetensors`, or `drive` → mount Drive and point to `qwen3-4b-semantic-lora/checkpoint-300`.
5. **“6. Cargar Qwen3-4B + adapter LoRA”** – loads `Qwen/Qwen3-4B-Instruct-2507` **without merging** the
   adapter, so the same model object can also run the baseline through `model.disable_adapter()`.
6. **“7. Extractor fine-tuneado + resolvedor de fechas”** – defines `extraer()` (the solution) and
   `baseline()` (direct prompting on the base model).
7. **“8. Preparar el chat”** – sets up the three bubbles: *Tú*, *CalendarBot (Qwen3-4B + LoRA)* and
   *Sin CalendarBot (prompt directo, Qwen3-4B sin fine-tuning)*.
8. **“9. Chat: escribe tu solicitud y ejecuta la celda”** – the run. Parameters:

   ```python
   SOLICITUD        = "Agenda la entrega de GENIA para mañana a las 23:59 desde mi casa en conjunto con Matías, Pablo y Daniela"
   DESTINO          = "google"      # or "solo .ics"
   MOSTRAR_BASELINE = True          # shows the direct-prompting baseline on the SAME input
   REINICIAR_CHAT   = True
   ```

   For every execution you get, side by side:
   * the **baseline bubble** (orange, dashed): prose from the base model with a single direct instruction —
     no schema, no JSON, no calendar event;
   * the **CalendarBot bubble**: the 9-field JSON, the human-readable summary, the raw LoRA output
     (6 fields, no date — the resolver computes it) with the inference time;
   * the created event: a Google Calendar link (`DESTINO = "google"`) or a downloadable `.ics` file.

   If the message has no date or no time, the bot asks for the missing field and the **next message completes
   only that field** (`PENDIENTE`) — a second run of the same cell with a short answer demonstrates it.
9. **“10. (Opcional) Hardware usado en esta sesión”** – GPU / VRAM report for the record.

Any message works; the video uses an input that was not picked to flatter the system, with
`MOSTRAR_BASELINE = True` so the baseline is visible on the same input.

## 7. Reproduce the before/after benchmark (Part B)

Both notebooks take ~15 minutes on a T4 and use **the same criterion** (`evaluar.py` from Deliverable 1):
a phrase passes only if all 8 scored fields are exactly right.

1. **`benchmark_antes.ipynb`** — GPU T4, run all cells in order (referencing them by their Colab title):
   * **“1. Instalar dependencias”** and the five `%%writefile` cells that follow (tools + both benchmarks);
   * **“2. Cargar Qwen3-4B base, SIN fine-tuning”** — loads the base model **without** the adapter;
   * **“3. Extractor (idéntico al del chat)”** — the structured prompt + resolver + rules;
   * **“4. Correr los benchmarks (~10 min)”**, then **“5. Pruebas automáticas: PASA / FALLA por frase”**;
   * **“6. Descargar resultados_antes.zip”** — downloads **`resultados_antes.zip`**. Save it; the next
     notebook asks for it.
2. **`benchmark_despues.ipynb`** — GPU T4, run the cells in order:
   * **“2. Ubicar el adapter LoRA (checkpoint-300)”** — upload `adapter_config.json` +
     `adapter_model.safetensors` (or point to Drive);
   * **“3. Cargar Qwen3-4B + LoRA”** — loads the model and **merges** the adapter (`merge_and_unload`),
     so inference cost is identical to the base model;
   * **“4. Extractor (idéntico al del chat)”**, **“5. Correr los benchmarks (~10 min)”**,
     **“6. Pruebas automáticas: PASA / FALLA por frase”**;
   * **“7. Descargar resultados_despues.zip”** — downloads **`resultados_despues.zip`**;
   * **“8. Comparar antes vs después (sube resultados_antes.zip)”** — uploads the zip from step 1 and
     downloads **`comparacion.zip`**.

## 8. Re-check the numbers offline (Part C)

```bash
# phrase-level PASS/FAIL with the Deliverable 1 criterion
python benchmark_ft.py --probar   frases.json         resultados_antes_frases.json
python benchmark_ft.py --probar   benchmark_ft.json   resultados_despues_benchmark_ft.json

# before vs after on the same benchmark
python benchmark_ft.py --comparar frases.json         resultados_antes_frases.json resultados_despues_frases.json
python benchmark_ft.py --comparar benchmark_ft.json   resultados_antes_benchmark_ft.json resultados_despues_benchmark_ft.json

# dates the resolver alone gets (independent of the model): 45/45 and 45/48
python benchmark_ft.py --techo    benchmark_ft.json
```

`benchmark_ft.py` imports `evaluar.py` and `resolvedor_temporal.py`, so keep them in the same directory —
run the `%%writefile` cells of either benchmark notebook once (or copy those three files out of them).

## 9. Expected results (verification)

Phrase-level accuracy, all 8 scored fields exact:

| Set | N | Baseline (base model + prompt + resolver) | Solution (+ LoRA) | Δ |
|---|---|---|---|---|
| `frases.json` (Benchmark2, from D1) | 45 | 33 (**73.3 %**) | 44 (**97.8 %**) | +24.5 pp |
| `benchmark_ft.json` (unseen) | 48 | 31 (**64.6 %**) | 40 (**83.3 %**) | +18.7 pp |
| **Total** | **93** | **64 (68.8 %)** | **84 (90.3 %)** | **+21.5 pp** |

* Field-level: 711/744 (95.6 %) → 735/744 (98.8 %); 24 phrases fixed, 4 broken.
* McNemar: `p = 0.0034` on `frases.json`, `p = 0.0352` on `benchmark_ft.json`
  (exact combined `p ≈ 1.8 × 10⁻⁴`) — see `comparacion_*.json`.
* Latency per message: 4.79 s → 3.77 s.
* Direct-prompting baseline from Deliverable 1 (same 45 phrases): **0/45 parseable** — no event can be created.
* Hardware: Tesla T4, `float16`, 7.7 GB VRAM peak, greedy decoding (`max_new_tokens=256`),
  load 215 s (base) / 408 s (merged adapter).

## 10. Known limits

1. **The adapter drops the meridiem.** `Reunión el 10/09 a las 10 pm` → `10:00` instead of `22:00`
   (and `8 pm` → `08:00` instead of `20:00`), where the base model was right. Training targets are written
   in 24-hour form, so the adapter copies the literal digits and discards `pm`. 2 of 93 phrases.
2. **Participants are over-generated.** `Ensayo de la banda…` → `["banda"]`, `Vacuna del perro…` → `["perro"]`
   where the ground truth is `[]`: training examples are dominated by non-empty participant lists, so the
   adapter fills the field with a noun taken from the title.
3. **The resolver is the ceiling for dates** (45/48, identical before and after). `el viernes 18` is ambiguous
   between weekday and day-of-month (rule → 2026-09-04, truth → 2026-09-18); `31/09` is invalid and the rule
   rolls over to 2026-10-31 instead of refusing; and the grammar has **no English relative dates**, so
   `tomorrow` yields `null`.
4. **Dates cannot improve from fine-tuning** — by design they are computed outside the model, so the
   before/after delta lives in the other six fields. A new date expression means editing the grammar.

## 11. Deliverables

* **Technical document (one page, LaTeX):** [`informe/entregable2.pdf`](informe/entregable2.pdf)
  — source in [`informe/entregable2.tex`](informe/entregable2.tex);
  rebuild with `latexmk -pdf informe/entregable2.tex`.
* **Video (max 3:00):** _paste the open-access link here before submitting._

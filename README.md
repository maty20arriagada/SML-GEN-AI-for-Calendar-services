# SML-GEN-AI-for-Calendar-services

## Equipo

Matias Arriagada, Cristián Cárdenas, Pablo Silva y Daniela Vidal.

## Deliverable 3 (sistema de agentes)

La entrega del Deliverable 3 está en [`Deliverable3/`](Deliverable3/): ver su [`README.md`](Deliverable3/README.md) (agentes, prompts versionados, resultados, trazas y cómo reproducir el video) y el documento `Deliverable3/documento/deliverable3.pdf`.

## Tarea

Convertir mensajes naturales en español e inglés, incluidos mensajes informales,
en un evento JSON listo para un servicio de calendario. La salida contiene ocho
campos: `titulo`, `fecha`, `hora_inicio`, `duracion_minutos`, `participantes`,
`ubicacion`, `recordatorio_minutos` y `zona_horaria`.

El criterio de exactitud exige que todos los campos coincidan con el *ground
truth*, usando `null` o `[]` cuando no existe información y sin inventar datos.
Las fechas relativas se interpretan desde el 1 de septiembre de 2026.

## Estado actual

- Benchmark1: 35 frases para medir prompting directo.
- Benchmark2: 45 frases, incluyendo casos ambiguos, complejos y mensajes de chat.
- TinyLlama-1.1B: 6/45 (13.3%) con prompt directo.
- Qwen2-0.5B: 0/35 (0.0%) con prompt directo (Benchmark1).
- Qwen4B-Instruct: 20/45 (44.4%) con prompt directo.
- Mistral-7B-Instruct: 27/45 (60.0%) con prompt directo.
- Qwen3-4B-Instruct-2507: 29/45 (64.4%) con system prompt, few-shot y post-procesamiento.
- La ejecución fue realizada en Google Colab con GPU NVIDIA T4.

## Archivos principales

- `deliverable1.tex`: entrega formal (1 página, compilar con pdflatex).
- `frases.json`: Benchmark1 con ground truth (35 frases).
- `frases (1).json`: Benchmark2 con ground truth (45 frases).
- `prueba_d1.ipynb`: baseline con TinyLlama y Qwen2.
- `prueba_d2.ipynb`: prompting mejorado y evaluación de Qwen3.
- `reporte_tinyllama.csv`: resultados detallados de TinyLlama en Benchmark2.
- `reporte_mistral7B.csv`: resultados detallados de Mistral-7B en Benchmark2.
- `reporte_qwen4B.csv`: resultados detallados de Qwen4B en Benchmark2.
- `evaluar.py`: métricas globales, por campo, por categoría y tipo de error.

## Ejecución

1. Abrir `prueba_d2.ipynb` en Google Colab y activar una GPU T4.
2. Subir `frases (1).json` y ejecutar las celdas en orden.
3. Para evaluar salidas guardadas localmente, ejecutar `python evaluar.py --evaluar tinyllama`.
## Skill `agenda-reuniones` para Qwen3-4B-Instruct-2507 + Google Calendar, zona `America/Santiago`.

## Abrir en Colab (repo privado)

Opción A — UI: Colab → Abrir cuaderno → pestaña GitHub → autoriza `maty20arriagada` → `SML-GEN-AI-for-Calendar-services` → `notebooks/agenda_colab.ipynb`.

Opción B — Clone con PAT en Colab (celda 2 del notebook lo hace solo si falta la skill):
```python
# Secrets necesarios: GITHUB_PAT (scope repo), HF_TOKEN (Read)
```

## Estructura

- `.opencode/skills/agenda-reuniones/SKILL.md` — skill portable, también usada como system-prompt en Colab
- `notebooks/agenda_colab.ipynb` — flujo HF Inference API + Calendar
- `requirements-colab.txt`, `scripts/get_google_token.py`
- `opencode.json` — config opencode local (HF + MCP remoto Google)
- `INICIAR.md` — uso local opencode. `COLAB.md` — uso Colab.

## Subir D2 al privado

```bash
git init
git branch -M main
git remote add origin https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services.git
git add .opencode opencode.json notebooks requirements-colab.txt scripts INICIAR.md COLAB.md README.md .env.example init-check.sh
git commit -m "skill agenda + colab Qwen 4B Chile"
git push -u origin main
```

No subir `.env` ni `token.json`.
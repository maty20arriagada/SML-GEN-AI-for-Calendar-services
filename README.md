# SML-GEN-AI-for-Calendar-services

## Equipo

Matias Arriagada, Cristián Cárdenas, Pablo Silva y Daniela Vidal.

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

- `frases.json`: Benchmark1 con ground truth.
- `frases (1).json`: Benchmark2 con ground truth.
- `prueba_d1.ipynb`: baseline con TinyLlama y Qwen2.
- `prueba_d2.ipynb`: prompting mejorado y evaluación de Qwen3.
- `resultados_qwen_mejorado.json`: salidas normalizadas de Qwen3 en Benchmark2.
- `reporte_tinyllama.csv`: resultados detallados de TinyLlama en Benchmark2.
- `reporte_mistral7B.csv`: resultados detallados de Mistral-7B en Benchmark2.
- `reporte_qwen4B.csv`: resultados detallados de Qwen4B en Benchmark2.
- `deliverable1.tex` / `deliverable1.pdf`: entrega formal (1 página).
- `logo_dii.png`: logo del Departamento de Ingeniería Industrial.
- `evaluar.py`: métricas globales, por campo, por categoría y tipo de error.

## Ejecución

1. Abrir `prueba_d2.ipynb` en Google Colab y activar una GPU T4.
2. Subir `frases (1).json` y ejecutar las celdas en orden.
3. Para evaluar salidas guardadas localmente, ejecutar `python evaluar.py --evaluar tinyllama`.

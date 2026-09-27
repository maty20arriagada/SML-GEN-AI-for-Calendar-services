# Guía: correr el brazo D en Colab (para un integrante que no entrenó el modelo)

Objetivo: evaluar el adapter LoRA **ya entrenado** sobre las 45 frases de Benchmark2
(brazo D) y devolver `resultados_D.json`. No se reentrena nada. Tiempo: ~25 min de GPU.

## Qué necesitas (checklist)

| # | Qué | Dónde |
|---|---|---|
| 1 | Cuenta Google con cuota de GPU disponible en Colab | https://colab.research.google.com |
| 2 | Acceso al repo del equipo (privado) | https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services |
| 3 | El cuaderno `deliverable2/notebooks/brazo_D_colab.ipynb` | https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services/blob/main/deliverable2/notebooks/brazo_D_colab.ipynb |
| 4 | El zip del proyecto `deliverable2/proyecto.zip` (descárgalo a tu PC con el botón *Download raw file*) | https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services/blob/main/deliverable2/proyecto.zip |
| 5 | La carpeta de Drive `qwen3-4b-semantic-lora` compartida por Matías (link por chat) | Google Drive → *Compartido conmigo* |

## Paso 0 — Dejar el adapter en tu Drive (una sola vez)

1. En Google Drive, ve a **Compartido conmigo** y busca `qwen3-4b-semantic-lora`.
2. Clic derecho → **Organizar → Agregar acceso directo** → elige **Mi unidad** → *Agregar*.
3. Comprueba que en **Mi unidad** aparece `qwen3-4b-semantic-lora` y que dentro está
   `checkpoint-300/` con `adapter_model.safetensors` y `adapter_config.json`.

> El nombre y la ubicación importan: el cuaderno busca exactamente
> `/content/drive/MyDrive/qwen3-4b-semantic-lora/checkpoint-300`. Si no lo encuentra,
> la celda 3 se detiene con un mensaje claro.

## Paso 1 — Abrir el cuaderno en Colab

1. Entra a https://colab.research.google.com → **Archivo → Abrir cuaderno → pestaña GitHub**.
2. Marca *Incluir repositorios privados* (autoriza GitHub si lo pide) y busca
   `maty20arriagada/SML-GEN-AI-for-Calendar-services`.
3. Abre `deliverable2/notebooks/brazo_D_colab.ipynb`.
   *(Alternativa: descarga el .ipynb desde GitHub y súbelo con **Archivo → Subir cuaderno**.)*

## Paso 2 — Activar GPU

**Entorno de ejecución → Cambiar tipo de entorno de ejecución → T4 GPU → Guardar.**

## Paso 3 — Ejecutar las celdas en orden

| Celda | Qué hace | Qué debes ver |
|---|---|---|
| 1 | Instala dependencias fijadas | `GPU OK: Tesla T4` (si falla el `assert`, estás en CPU → Paso 2) |
| 2 | Pide `proyecto.zip` | Sube el zip del checklist #4 → `Proyecto listo en /content/proyecto` |
| 3 | Monta Drive y ubica el adapter | Autoriza Drive → `Adapter encontrado: ...checkpoint-300` |
| 4 | Corre el brazo D (45 frases) | `Cargando ... + adapter` y luego 45 líneas; ~15 min |
| 5 | Vista previa de la métrica | Exactitud del brazo D (el modelo base daba **84.4%**); `entorno: hf:...+adapter` |
| 6 | Respaldo y descarga | Se descargan `resultados_D.json` y `resultados_D_crudo.json`; copia en `Mi unidad/resultados_brazo_D/` |

Mantén la pestaña abierta mientras corre la celda 4.

## Paso 4 — Entregar

Envía a Matías los dos archivos de la celda 6 (o compártele `Mi unidad/resultados_brazo_D/`)
y una captura de la salida de la celda 5. **No** los subas al repo tú: se integran en local
con `python experimentos/evaluar_todo.py` para regenerar la tabla con los 4 brazos.

## Reglas que no se pueden romper

- **No correr los brazos A, B ni C** con este cuaderno: ya tienen resultados reales y
  deben medirse sin adapter.
- **No usar `benchmark/benchmark2.json` para entrenar ni ajustar prompts** (es solo test).
- **No cambiar las versiones de la celda 1**: el adapter se entrenó con transformers 5.17 / peft 0.21.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `assert` de GPU falla / `nvidia-smi` no existe | Runtime en CPU → Paso 2 y re-ejecutar la celda 1 |
| "No se puede conectar al backend de GPU" | Tu cuota se agotó: otro integrante debe correrlo, o esperar ~12-24 h |
| `Falta adapter_config.json ...` | No está el acceso directo en *Mi unidad* → Paso 0 |
| El selector de archivos no aparece | Vuelve a ejecutar la celda 2 (el widget solo vive en la sesión actual) |
| Error de `size mismatch` al cargar el adapter | Versiones distintas: *Entorno de ejecución → Desconectar y borrar* y empezar desde la celda 1 |
| Se cortó la sesión en la celda 4 | Repetir celdas 1 → 4 (no hay estado que conservar) |

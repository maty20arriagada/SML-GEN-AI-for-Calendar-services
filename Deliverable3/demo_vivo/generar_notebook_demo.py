# -*- coding: utf-8 -*-
"""
generar_notebook_demo.py - Arma subir_a_colab/demo_calendarbot_d3.ipynb: chat de CalendarBot con el sistema
de agentes E4 conectado a Google Calendar (demo en vivo para el video).

Mismas versiones y mismo modelo que subir_a_colab/deliverable3_colab.ipynb (Qwen3-4B-Instruct-2507 + LoRA
checkpoint-300). No editar el .ipynb a mano: cambiar este script y correr
  python demo_vivo/generar_notebook_demo.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SALIDA = ROOT / "subir_a_colab" / "demo_calendarbot_d3.ipynb"

INTRO = """# CalendarBot D3 en vivo — agentes E4 + Google Calendar

Mensaje en lenguaje natural → **A1** (triage) → **A2** (extractor, Qwen3-4B + LoRA) → **A3** (elige herramientas para fecha, hora, zona, recurrencia) → **A4** (verifica y puede devolver a A3) → contrato de 9 campos → evento en el calendario **CalendarBot** de tu Google Calendar.

Necesitas en tu computador (carpeta `subir_a_colab/` del intento 3): `d3_proyecto.zip`, `adapter_config.json`, `adapter_model.safetensors`, y `credentials.json` (cliente OAuth «Desktop app» de Google Cloud, el mismo del Deliverable 2). Opcional: `token_google.json` (vale 7 días) para no repetir el login; si venció, se renueva en tu computador con `python probar_google.py` en la carpeta del Deliverable 2.

- Cada ejecución de la celda 6 es un mensaje. Si falta el día o la hora, el bot lo pregunta y el siguiente mensaje lo completa. Con `SIMULACRO` no se crea nada.
- Junto a E4 se muestra lo que habría dado la solución D2 (E1) sobre la misma frase.
- Un evento rechazado por A1 o sin fecha/hora **no** se envía.
- Si falla la API de Google se escribe un `.ics` de respaldo.
- `credentials.json` y `token_google.json` quedan solo en esta sesión de Colab: no van al zip ni al repositorio.
"""

DEPS = """# 1) Dependencias (T4) — mismas versiones con las que se entrenó el LoRA
!nvidia-smi -L
%pip install -q "transformers==5.17.0" "peft==0.21.0" "accelerate==1.15.0"
%pip uninstall -y -q torchao
import torch
assert torch.cuda.is_available(), "Sin GPU: cambia el runtime a T4 y vuelve a correr"
print("GPU OK:", torch.cuda.get_device_name(0))
"""

REPO = """# 2) Subir d3_proyecto.zip (codigo + prompts + demo_vivo)
import os, sys, zipfile
from google.colab import files

REPO = "/content/repo"
os.makedirs(REPO, exist_ok=True)
if not os.path.isdir(os.path.join(REPO, "demo_vivo")):
    print("Sube d3_proyecto.zip (carpeta subir_a_colab):")
    subidos = files.upload()
    nombre = next(f for f in subidos if f.endswith(".zip"))
    with zipfile.ZipFile(nombre) as z:
        z.extractall(REPO)

os.chdir(REPO)
sys.path.insert(0, REPO)
from deliverable3 import benchmark_agentes as ba   # deja deliverable2/ en sys.path
assert "E4" in ba.BRAZOS, "este zip no es el del intento3"
assert os.path.isfile("demo_vivo/demo_calendar.py"), "este zip no trae demo_vivo/: regeneralo con preparar_zip.py"
print("OK: deliverable3 + demo_vivo listos en", REPO)
"""

ADAPTER = """# 3) Adapter LoRA checkpoint-300 (el mismo de D2)
ORIGEN_ADAPTER = "subir archivos"  # @param ["subir archivos", "drive"]
RUTA_DRIVE = "/content/drive/MyDrive/qwen3-4b-semantic-lora/checkpoint-300"  # @param {type:"string"}
import os, shutil
from google.colab import files

NECESARIOS = ["adapter_config.json", "adapter_model.safetensors"]

if ORIGEN_ADAPTER == "drive":
    from google.colab import drive
    drive.mount("/content/drive")
    ADAPTER = RUTA_DRIVE
else:
    ADAPTER = "/content/adapter"
    os.makedirs(ADAPTER, exist_ok=True)
    faltan = [f for f in NECESARIOS if not os.path.isfile(os.path.join(ADAPTER, f))]
    if faltan:
        print("Sube:", ", ".join(faltan), "(de checkpoint-300; el .safetensors pesa ~130 MB)")
        for nombre in files.upload():
            clave = "adapter_config.json" if "adapter_config" in nombre else "adapter_model.safetensors"
            shutil.move(nombre, os.path.join(ADAPTER, clave))
assert os.path.isfile(os.path.join(ADAPTER, "adapter_config.json")), "falta adapter_config.json"
assert os.path.isfile(os.path.join(ADAPTER, "adapter_model.safetensors")), "falta adapter_model.safetensors"

# La subida de Colab a veces se corta: un .safetensors incompleto falla despues con "header too large"
import json, struct
ruta_st = os.path.join(ADAPTER, "adapter_model.safetensors")
tam = os.path.getsize(ruta_st)
with open(ruta_st, "rb") as f:
    largo = struct.unpack("<Q", f.read(8))[0]
    ok = largo < 10_000_000 and tam > 100_000_000
    if ok:
        try:
            json.loads(f.read(largo))
        except Exception:
            ok = False
if not ok:
    os.remove(ruta_st)
    raise RuntimeError(f"adapter_model.safetensors corrupto o incompleto ({tam} bytes; deben ser ~132187888). "
                       "Se borro: vuelve a correr esta celda y sube el archivo de nuevo")
print("adapter OK:", ADAPTER, f"({tam/1e6:.0f} MB)")
"""

CREDENCIALES = """# 4) Credenciales de Google (OAuth «Desktop app», las del Deliverable 2)
import os
from google.colab import files

faltan = [f for f in ["credentials.json", "token_google.json"] if not os.path.exists(f)]
if faltan:
    print("Sube credentials.json (y token_google.json si ya hiciste el login antes; si no, cancela esa parte):")
    try:
        for nombre in files.upload():
            print("recibido:", nombre)
    except Exception as e:
        print("sin subida:", e)
print("credentials.json:", "OK" if os.path.exists("credentials.json") else "FALTA (sin él solo funciona el simulacro)")
print("token_google.json:", "OK" if os.path.exists("token_google.json") else "no hay: se pedirá login la primera vez")
"""

MODELO = """# 5) Cargar Qwen3-4B + LoRA una vez (~8 GB fp16); sirve a los cuatro agentes
import time
from pipeline.modelo import GeneradorHF

MODELO_ID = "Qwen/Qwen3-4B-Instruct-2507"
t0 = time.perf_counter()
motor = GeneradorHF(MODELO_ID, adapter=ADAPTER, dtype="float16")
print(f"cargado en {motor.modelo.device} en {time.perf_counter()-t0:.0f} s")
"""

CHAT = """# @title 6. Chat: escribe tu solicitud y ejecuta la celda (cada ejecucion es un mensaje)
from demo_vivo import demo_calendar as dc

SOLICITUD = "Agéndame una reunión con Pablo el viernes a las 4 en la sala B-11, recuérdame 15 min antes"  # @param {type:"string"}
DESTINO = "google"  # @param ["google", "solo .ics"]
SIMULACRO = False  # @param {type:"boolean"}
MOSTRAR_D2 = True  # @param {type:"boolean"}
REINICIAR_CHAT = False  # @param {type:"boolean"}

if "CHAT" not in globals():
    CHAT = dc.Chat(motor, dir_trazas="demo_vivo/trazas", descargar=files.download)
if REINICIAR_CHAT:
    CHAT.reiniciar()
if DESTINO == "google" and not os.path.exists("credentials.json"):
    print("Falta credentials.json: se corre en simulacro")
    SIMULACRO = True
CHAT.enviar = not SIMULACRO
CHAT.destino = "google" if DESTINO == "google" else "ics"
CHAT.mostrar_baseline = MOSTRAR_D2
CHAT.mensaje(SOLICITUD)
"""

EJEMPLOS = """## Frases para probar

- `Café con el postulante a becario el viernes a las 11:00` — caso de B donde A2 corta el rol («postulante»)
- `Reunión el 10/09 a las 10 pm` — am/pm: el modelo solo lee 10:00, A3 lo lleva a 22:00
- `Dinner with Tom at 7 pm New York time on October 9` — falla real de C (zona): en la corrida quedó INCOMPLETO (sin fecha) y por eso no se envía
- `Hola, ¿qué tal?` — A1 rechaza y no se crea nada

Las trazas JSONL quedan en `demo_vivo/trazas/` (descárgalas si las quieres para el video).
"""


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(keepends=True)}


def codigo(texto):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": texto.rstrip("\n").splitlines(keepends=True)}


def main():
    celdas = [md(INTRO), codigo(DEPS), codigo(REPO), codigo(ADAPTER), codigo(CREDENCIALES),
              codigo(MODELO), codigo(CHAT), md(EJEMPLOS)]
    nb = {"cells": celdas,
          "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []},
                       "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    SALIDA.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()

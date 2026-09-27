# -*- coding: utf-8 -*-
"""
demo_local.py -- Demo end-to-end del sistema SIN chat (reproducible sin tokens).

Corre el pipeline completo sobre una frase: mensaje -> modelo -> herramienta
de fechas -> contrato de 9 campos -> evento creado en la API de calendario.
Muestra el brazo A (baseline) junto al brazo D (solucion) sobre la MISMA
frase, que es exactamente lo que debe verse en el video.

Uso:
  python calendario/demo_local.py                          # con modelo mock
  python calendario/demo_local.py --frase "agenda reunion manana 10am porfa"
  python calendario/demo_local.py --real --adapter qwen3-4b-semantic-lora
"""

from __future__ import annotations

import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from calendario.calendar_api import LocalCalendarAPI  # noqa: E402
from pipeline.modelo import GeneradorHF, GeneradorMock  # noqa: E402
from pipeline.pipeline import CalendarPipeline  # noqa: E402

FRASE_DEMO = "agenda reunion manana 10am porfa"
FRASE_DIFICIL = "q onda, quedamos el viernes a las 7 en lo de siempre?"


def _mock_de_demo() -> GeneradorMock:
    """Respuestas tipicas de un modelo sin fine-tuning (para ver el contraste)."""
    return GeneradorMock(respuestas={
        "*": json.dumps({
            "titulo": "agenda reunion",
            "fecha": "2026-09-10",          # fecha inventada por el modelo
            "hora_inicio": "10:00",
            "duracion_minutos": None,
            "participantes": [],
            "ubicacion": None,
            "recordatorio_minutos": None,
            "zona_horaria": "America/Santiago",
        }, ensure_ascii=False),
    })


def main():
    ap = argparse.ArgumentParser(description="Demo end-to-end del pipeline (sin Telegram)")
    ap.add_argument("--frase", default=FRASE_DEMO)
    ap.add_argument("--real", action="store_true", help="usar el modelo HF en vez del mock")
    ap.add_argument("--modelo", default="Qwen/Qwen3-4B-Instruct-2507")
    ap.add_argument("--adapter", default=None, help="ruta del adapter LoRA (brazo D)")
    ap.add_argument("--ics", action="store_true", help="exportar tambien un .ics")
    args = ap.parse_args()

    if args.real:
        print("Cargando %s%s..." % (args.modelo, " + adapter" if args.adapter else ""))
        generador = GeneradorHF(args.modelo, adapter=args.adapter)
    else:
        print("Modo MOCK (sin GPU): el contraste baseline/solucion es ilustrativo.")
        generador = _mock_de_demo()

    tuberia = CalendarPipeline(generador)
    api = LocalCalendarAPI()

    print("\n" + "=" * 72)
    print("FRASE: %s" % args.frase)
    print("=" * 72)

    print("\n[A] BASELINE (prompt directo, fecha del modelo):")
    a = tuberia.baseline(args.frase)
    print(json.dumps(tuberia.solo_contrato(a), ensure_ascii=False, indent=1))

    print("\n[D] SOLUCION (extractor semantico + herramienta de fechas):")
    d = tuberia.solucion(args.frase)
    print(json.dumps(tuberia.solo_contrato(d), ensure_ascii=False, indent=1))

    if a.get("fecha") != d.get("fecha"):
        print("\n  >> la herramienta corrige la fecha: %r -> %r" % (a.get("fecha"), d.get("fecha")))

    registro = api.create_event(tuberia.solo_contrato(d))
    print("\nEvento creado en la API de calendario: %s" % registro["id"])
    print(json.dumps(registro, ensure_ascii=False, indent=1))

    if args.ics:
        ruta = api.exportar_ics()
        print("\nICS exportado en: %s" % ruta)

    print("\nEventos almacenados: %d" % len(api.list_events()))


if __name__ == "__main__":
    main()

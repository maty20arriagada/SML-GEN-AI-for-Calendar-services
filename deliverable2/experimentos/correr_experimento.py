# -*- coding: utf-8 -*-
"""
correr_experimento.py -- Corre un brazo del sistema sobre Benchmark2 (45 frases).

Salida: resultados/resultados_{brazo}.json con el formato que consume evaluar.py
de D1 ([{"id", "texto", "resultado_modelo"}]), ademas de las respuestas crudas
del modelo para depuracion.

Uso:
  python experimentos/correr_experimento.py --brazo A --mock
  python experimentos/correr_experimento.py --brazo D --adapter qwen3-4b-semantic-lora
  python experimentos/correr_experimento.py --brazo todos --real --modelo Qwen/Qwen3-4B-Instruct-2507

En Colab: subir el repo y ejecutar igual con !python.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from pipeline.modelo import GeneradorHF, GeneradorMock  # noqa: E402
from pipeline.pipeline import BRAZOS, CalendarPipeline  # noqa: E402

RUTAS_BENCHMARK = [
    os.path.join(RAIZ, "benchmark", "benchmark2.json"),
    "/content/benchmark/benchmark2.json",
    "/content/frases (1).json",
    "benchmark/benchmark2.json",
]
RUTA_SALIDA = os.path.join(RAIZ, "resultados")


def cargar_benchmark() -> list:
    for ruta in RUTAS_BENCHMARK:
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                data = json.load(f)
            frases = data["frases"] if isinstance(data, dict) else data
            print("Benchmark: %s (%d frases)" % (ruta, len(frases)))
            return frases
    raise FileNotFoundError("No se encontro benchmark2.json")


def correr(brazo: str, tuberia: CalendarPipeline, frases: list, salida_dir: str, entorno="hf",
           fuerza: bool = False, verbose=True) -> str:
    ruta = os.path.join(salida_dir, "resultados_%s.json" % brazo)

    # proteccion: nunca pisar resultados reales con datos de un modelo mock
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            existentes = json.load(f)
        entorno_viejo = existentes[0].get("entorno", "") if existentes else ""
        if "MOCK" in entorno.upper() and "MOCK" not in entorno_viejo.upper():
            if not fuerza:
                raise SystemExit(
                    "[BLOQUEADO] %s contiene resultados reales (%s) y esta corrida es MOCK.\n"
                    "  Usa --fuerza para pisarlos, o --salida <otra_carpeta> para no tocarlos."
                    % (ruta, entorno_viejo or "sin sello"))
            print("AVISO: pisando resultados reales de %s por orden --fuerza" % brazo)

    filas, crudos = [], []
    t0 = time.time()
    for fr in frases:
        evento = tuberia.correr_brazo(brazo, fr["texto"])
        filas.append({
            "id": fr["id"],
            "texto": fr["texto"],
            "resultado_modelo": CalendarPipeline.solo_contrato(evento),
            "entorno": entorno,
        })
        crudos.append({"id": fr["id"], "crudo": evento.get("_crudo"), "error": evento.get("_error_modelo")})
        if verbose:
            marca = "ok" if evento.get("fecha") else "sin fecha"
            print("  [%s] id=%2d %-60s %s" % (brazo, fr["id"], fr["texto"][:60], marca))

    os.makedirs(salida_dir, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False, indent=1)
    with open(os.path.join(salida_dir, "resultados_%s_crudo.json" % brazo), "w", encoding="utf-8") as f:
        json.dump(crudos, f, ensure_ascii=False, indent=1)
    print("Brazo %s: %d frases en %.1fs -> %s" % (brazo, len(frases), time.time() - t0, ruta))
    return ruta


def main():
    ap = argparse.ArgumentParser(description="Corre brazos A-D sobre Benchmark2")
    ap.add_argument("--brazo", default="D", choices=["A", "B", "C", "D", "todos"])
    ap.add_argument("--modelo", default="Qwen/Qwen3-4B-Instruct-2507")
    ap.add_argument("--adapter", default=None, help="adapter LoRA (brazo D)")
    ap.add_argument("--mock", action="store_true", help="sin GPU: modelo mock")
    ap.add_argument("--fuerza", action="store_true",
                    help="permitir que una corrida MOCK pise resultados reales")
    ap.add_argument("--salida", default=RUTA_SALIDA)
    args = ap.parse_args()

    frases = cargar_benchmark()

    if args.mock:
        print("AVISO: modelo MOCK. Los resultados NO son evidencia; es un smoke test.")
        generador = GeneradorMock(respuestas={"*": "{}"})
    else:
        print("Cargando %s%s..." % (args.modelo, " + adapter" if args.adapter else ""))
        generador = GeneradorHF(args.modelo, adapter=args.adapter)

    tuberia = CalendarPipeline(generador)
    brazos = list(BRAZOS) if args.brazo == "todos" else [args.brazo]
    entorno = "MOCK (no es evidencia)" if args.mock else "hf:%s%s" % (
        args.modelo, " +adapter" if args.adapter else "")

    for b in brazos:
        # el adapter solo aplica al brazo D; se recomienda correr brazos por separado
        correr(b, tuberia, frases, args.salida, entorno=entorno, fuerza=args.fuerza)


if __name__ == "__main__":
    main()

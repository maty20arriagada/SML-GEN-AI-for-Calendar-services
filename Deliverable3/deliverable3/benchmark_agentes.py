# -*- coding: utf-8 -*-
"""
benchmark_agentes.py - Orquestador de benchmarks y ablaciones para Deliverable 3.
Permite evaluar E1 (baseline D2), E2 (sistema multi-agente) y ablaciones E2T1..E2T4, E2W.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, List, Set

# Asegurar que deliverable2 y pipeline estén en sys.path
_ROOT = Path(__file__).resolve().parent.parent
for _p in [_ROOT, _ROOT / "deliverable2"]:
    if str(_p) not in sys.path and _p.exists():
        sys.path.insert(0, str(_p))

from deliverable3.agentes import BRAZOS as CFG_BRAZOS
from deliverable3.grafo import ejecutar

BRAZOS: List[str] = list(CFG_BRAZOS.keys())  # ["E1", "E2", "E2W", "E2T1", "E2T2", "E2T3", "E2T4"]

# Buscar dónde residen frases.json y benchmark_ft.json
if (_ROOT / "frases.json").exists():
    RUTA_BENCH = _ROOT
elif Path("/content/repo/frases.json").exists():
    RUTA_BENCH = Path("/content/repo")
else:
    RUTA_BENCH = _ROOT


def _cargar_bench(ruta_o_nombre: str | Path) -> tuple[list, dict]:
    p = Path(ruta_o_nombre)
    if not p.is_file():
        p = RUTA_BENCH / p.name
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("frases", []), data.get("metadata", {"fecha_referencia": "2026-09-01"})


def correr_brazo(brazo: str, args: Any, motor: Any) -> List[dict]:
    """
    Ejecuta un brazo experimental sobre un benchmark.
    Guarda resultados_{brazo}_{bench}.json y trazas solicitadas.
    """
    cfg = CFG_BRAZOS[brazo]
    frases, metadata = _cargar_bench(args.bench)
    fecha_ref = metadata.get("fecha_referencia", "2026-09-01")

    # IDs de los que se requiere guardar traza
    ids_traza: Set[int] = set()
    if getattr(args, "traza", None):
        for parte in str(args.traza).split(","):
            parte = parte.strip()
            if parte.isdigit():
                ids_traza.add(int(parte))

    dir_salida = Path(args.salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    dir_trazas = Path(args.dir_trazas) if getattr(args, "dir_trazas", None) else dir_salida / "traces"
    dir_trazas.mkdir(parents=True, exist_ok=True)

    bench_stem = Path(args.bench).stem
    print(f"[{brazo}] Corriendo sobre {args.bench} ({len(frases)} frases)...")

    resultados = []
    todas_las_trazas = []   # los mensajes entre agentes de TODOS los inputs (consigna D3)
    for i, frase_item in enumerate(frases, 1):
        fid = frase_item["id"]
        texto = frase_item["texto"]

        t0 = time.perf_counter()
        evento, traza = ejecutar(texto, cfg=cfg, motor=motor, fecha_ref=fecha_ref)
        dt = time.perf_counter() - t0

        todas_las_trazas.append({"id": fid, **traza.a_dict()})
        if fid in ids_traza:
            ruta_tr = dir_trazas / f"traza_{brazo}_{bench_stem}_{fid}.jsonl"
            traza.guardar(ruta_tr)

        resultados.append({
            "id": fid,
            "texto": texto,
            "resultado_modelo": evento,
            "segundos": round(dt, 2),
            "json_valido": True,
        })
        if i % 10 == 0 or i == len(frases):
            print(f"  [{i:2d}/{len(frases)}] {dt:4.1f} s  {texto[:55]}")

    with open(dir_trazas / f"trazas_{brazo}_{bench_stem}.jsonl", "w", encoding="utf-8") as f:
        for t in todas_las_trazas:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    ruta_res = dir_salida / f"resultados_{brazo}_{bench_stem}.json"
    with open(ruta_res, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"  Guardado: {ruta_res}")
    return resultados


def resumen(args: Any) -> None:
    """Imprime un resumen de los resultados disponibles en el directorio de salida."""
    dir_salida = Path(args.salida) if hasattr(args, "salida") else Path(".")
    archivos = list(dir_salida.glob("resultados_*.json"))
    print("\n" + "=" * 60)
    print(f"RESUMEN DE BENCHMARKS EN {dir_salida} ({len(archivos)} corridas)")
    print("=" * 60)
    for a in sorted(archivos):
        try:
            with open(a, "r", encoding="utf-8") as f:
                d = json.load(f)
            print(f"  * {a.name:<35s}: {len(d)} casos")
        except Exception as e:
            print(f"  * {a.name:<35s}: error leyendo ({e})")

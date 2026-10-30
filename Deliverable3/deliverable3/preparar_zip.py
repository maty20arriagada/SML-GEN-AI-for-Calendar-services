# -*- coding: utf-8 -*-
"""
preparar_zip.py - Empaqueta el proyecto en d3_proyecto.zip para ejecución en Google Colab.
Permite subir todo el código y benchmarks de forma autónoma sin requerir credenciales de Git.
"""

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SALIDA_ZIP = ROOT / "d3_proyecto.zip"


def empaquetar() -> Path:
    print(f"Empaquetando proyecto en: {SALIDA_ZIP.name}...")
    
    patrones_incluir = [
        "deliverable3/**/*",
        "demo_vivo/*.py",          # solo código: nunca credentials.json ni token_google.json
        "deliverable2/pipeline/**/*",
        "deliverable2/calendario/**/*",
        "deliverable2/benchmark/**/*",
        "deliverable2/tests/**/*",
        "deliverable2/evaluar.py",
        "deliverable2/benchmark_ft.py",
        "deliverable2/resolvedor_temporal.py",
        "frases.json",
        "benchmark_ft.json",
        "benchmark_heldout.json",
        "benchmark_independiente.json",
        "evaluar.py",
        "benchmark_ft.py",
        "resolvedor_temporal.py",
    ]

    archivos_agregados = 0
    with zipfile.ZipFile(SALIDA_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for pat in patrones_incluir:
            for p in ROOT.glob(pat):
                if p.is_file() and "__pycache__" not in str(p) and not p.name.endswith(".pyc"):
                    rel = p.relative_to(ROOT)
                    z.write(p, rel)
                    archivos_agregados += 1
                    
    tam_kb = round(SALIDA_ZIP.stat().st_size / 1024, 1)
    print(f"Listo: {SALIDA_ZIP.name} creado ({tam_kb} KB, {archivos_agregados} archivos).")
    return SALIDA_ZIP


if __name__ == "__main__":
    empaquetar()

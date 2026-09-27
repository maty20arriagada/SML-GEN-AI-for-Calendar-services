# -*- coding: utf-8 -*-
"""
preparar_zip.py -- Genera proyecto.zip para subir a Google Colab.

Usa zipfile de Python (separadores POSIX '/'). NO usar Compress-Archive de
Windows: guarda las rutas con barras invertidas y en Linux/Colab el zip se
extrae como archivos planos (el paquete 'pipeline' deja de existir).

Uso:
  python datos/preparar_zip.py
"""

from __future__ import annotations

import os
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "proyecto.zip")

INCLUIR_DIRS = ["pipeline", "calendario", "benchmark", "experimentos", "datos", "tests", "docs", "entrenamiento"]
INCLUIR_ARCHIVOS = ["evaluar.py"]
EXCLUIR_DIRS = {"__pycache__", ".ipynb_checkpoints", "resultados"}
EXCLUIR_EXT = {".pyc", ".zip"}


def main():
    if os.path.exists(SALIDA):
        os.remove(SALIDA)

    rutas = []
    for d in INCLUIR_DIRS:
        base = os.path.join(RAIZ, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, nombres in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in EXCLUIR_DIRS]
            for n in nombres:
                if os.path.splitext(n)[1] in EXCLUIR_EXT:
                    continue
                rutas.append(os.path.join(dirpath, n))
    for a in INCLUIR_ARCHIVOS:
        p = os.path.join(RAIZ, a)
        if os.path.exists(p):
            rutas.append(p)

    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta in rutas:
            rel = os.path.relpath(ruta, RAIZ).replace(os.sep, "/")   # separadores POSIX
            z.write(ruta, rel)

    with zipfile.ZipFile(SALIDA) as z:
        nombres = z.namelist()
    print("proyecto.zip -> %s" % SALIDA)
    print("archivos: %d" % len(nombres))
    print("muestra:", nombres[:6])
    assert all("/" not in n.replace("/", "") or "\\" not in n for n in nombres), "hay barras invertidas"
    assert not any("\\" in n for n in nombres), "se colaron separadores Windows"
    print("OK: separadores POSIX, sin __pycache__")


if __name__ == "__main__":
    main()

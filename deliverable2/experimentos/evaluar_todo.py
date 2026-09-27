# -*- coding: utf-8 -*-
"""
evaluar_todo.py -- Evalua los brazos A-D con el CRITERIO IDENTICO al de D1.

Importa evaluar.py tal cual (sin reimplementar nada) y aplica
evaluar_resultado/calcular_metricas sobre las mismas 45 frases de Benchmark2,
de modo que baseline y solucion se miden exactamente igual.

Salidas:
  resultados/resumen.json            metricas de todos los brazos
  resultados/reporte_{brazo}.csv     detalle por frase (columnas de D1)
  docs/tabla_resultados.tex          tabla para el documento de una pagina

Uso:
  python experimentos/evaluar_todo.py
  python experimentos/evaluar_todo.py --brazos A D
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

RUTA_EVALUAR = os.path.join(RAIZ, "evaluar.py")
RUTAS_BENCHMARK = [
    os.path.join(RAIZ, "benchmark", "benchmark2.json"),
    "/content/benchmark/benchmark2.json",
    "/content/frases (1).json",
]
RUTA_RESULTADOS = os.path.join(RAIZ, "resultados")
RUTA_DOCS = os.path.join(RAIZ, "docs")

NOMBRES_BRAZOS = {
    "A": "Prompt directo (baseline)",
    "B": "Prompt estructurado",
    "C": "Prompt estructurado + tool",
    "D": "Fine-tune + tool (solucion)",
}


def cargar_evaluar():
    """Carga evaluar.py de D1 sin modificarlo: criterio identico garantizado."""
    spec = importlib.util.spec_from_file_location("evaluar_d1", RUTA_EVALUAR)
    if spec is None or spec.loader is None:
        raise ImportError("No se pudo cargar %s" % RUTA_EVALUAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def cargar_benchmark() -> list:
    for ruta in RUTAS_BENCHMARK:
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                data = json.load(f)
            return data["frases"] if isinstance(data, dict) else data
    raise FileNotFoundError("No se encontro benchmark2.json")


def cargar_resultados(brazo: str) -> tuple[dict, str]:
    ruta = os.path.join(RUTA_RESULTADOS, "resultados_%s.json" % brazo)
    if not os.path.exists(ruta):
        return {}, ""
    with open(ruta, encoding="utf-8") as f:
        filas = json.load(f)
    entorno = filas[0].get("entorno", "") if filas else ""
    return {f["id"]: f["resultado_modelo"] for f in filas}, entorno


def evaluar_brazo(evaluador, frases: list, predicciones: dict):
    evaluados = []
    for fr in frases:
        if fr["id"] not in predicciones:
            continue
        evaluados.append(evaluador.evaluar_resultado(fr, predicciones[fr["id"]]))
    return evaluados, evaluador.calcular_metricas(evaluados)


def escribir_csv(ruta: str, evaluados: list, campos: list) -> None:
    columnas = ["id", "texto", "exacto"]
    for c in campos:
        columnas += ["%s_gt" % c, "%s_pred" % c, "%s_ok" % c]
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(columnas)
        for ev in evaluados:
            fila = [ev["id"], ev["texto"], ev["es_correcto_total"]]
            for d in ev["detalles"]:
                fila += [d["esperado"], d["obtenido"], d["correcto"]]
            w.writerow(fila)


def escribir_latex(ruta: str, resultados: dict, campos: list, n: int) -> None:
    lineas = [
        "% Generado por experimentos/evaluar_todo.py -- no editar a mano",
        "% Criterio de correccion: evaluar.py de D1 (8 campos con ground truth)",
        "\\begin{center}",
        "\\scriptsize",
        "\\begin{tabular}{@{}l" + "c" * (1 + len(campos)) + "@{}}",
        "\\toprule",
        "Brazo & Exact. & " + " & ".join("\\texttt{%s}" % c.replace("_", "\\_") for c in campos) + " \\\\",
        "\\midrule",
    ]
    for brazo, datos in resultados.items():
        m = datos["metricas"]
        fila = "%s (%s) & \\textbf{%.1f\\%%}" % (NOMBRES_BRAZOS.get(brazo, brazo), brazo, m["precision_total"])
        for c in campos:
            fila += " & %.1f\\%%" % m["precision_por_campo"].get(c, {}).get("precision", 0.0)
        lineas.append(fila + " \\\\")
    lineas += [
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{center}",
        "",
        "%% n=%d frases de Benchmark2 (held-out), mismo criterio para todos los brazos" % n,
    ]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Evalua brazos con el criterio de D1")
    ap.add_argument("--brazos", nargs="+", default=["A", "B", "C", "D"])
    args = ap.parse_args()

    evaluador = cargar_evaluar()
    campos = list(evaluador.CAMPOS_OBLIGATORIOS)
    frases = cargar_benchmark()
    print("Benchmark2: %d frases | criterio: evaluar.py de D1 (%d campos)"
          % (len(frases), len(campos)))

    os.makedirs(RUTA_RESULTADOS, exist_ok=True)
    os.makedirs(RUTA_DOCS, exist_ok=True)

    resultados = {}
    for brazo in args.brazos:
        predicciones, entorno = cargar_resultados(brazo)
        if not predicciones:
            print("  [%s] sin resultados (corre antes: correr_experimento.py --brazo %s)" % (brazo, brazo))
            continue
        if "MOCK" in entorno.upper():
            print("  [%s] AVISO: resultados de un modelo MOCK (%s). NO son evidencia." % (brazo, entorno))
        evaluados, metricas = evaluar_brazo(evaluador, frases, predicciones)
        resultados[brazo] = {"metricas": metricas, "n": len(evaluados), "entorno": entorno}

        escribir_csv(os.path.join(RUTA_RESULTADOS, "reporte_%s.csv" % brazo), evaluados, campos)

        print("\n" + "=" * 62)
        print("  BRAZO %s -- %s" % (brazo, NOMBRES_BRAZOS.get(brazo, "")))
        print("  exactitud: %d/%d = %.1f%%" % (
            metricas["correctos_totales"], metricas["total_frases"], metricas["precision_total"]))
        for c in campos:
            v = metricas["precision_por_campo"].get(c, {})
            print("    %-22s %5.1f%% (%d/%d)" % (c, v.get("precision", 0), v.get("correctos", 0), v.get("total", 0)))
        if metricas.get("errores_por_tipo"):
            print("    errores:", metricas["errores_por_tipo"])

    if resultados:
        with open(os.path.join(RUTA_RESULTADOS, "resumen.json"), "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)
        escribir_latex(os.path.join(RUTA_DOCS, "tabla_resultados.tex"), resultados, campos, len(frases))
        print("\nEscritos: resultados/resumen.json, resultados/reporte_*.csv, docs/tabla_resultados.tex")

    print("\n--- comparacion rapida ---")
    for brazo, datos in sorted(resultados.items()):
        print("  %s %-32s %5.1f%%" % (brazo, NOMBRES_BRAZOS.get(brazo, ""), datos["metricas"]["precision_total"]))


if __name__ == "__main__":
    main()

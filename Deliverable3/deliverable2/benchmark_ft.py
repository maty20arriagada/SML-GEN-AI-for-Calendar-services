"""
benchmark_ft.py - Pruebas automaticas del antes/despues del fine-tuning (LoRA).

Cada frase de un benchmark es una prueba: PASA si los 8 campos coinciden con el ground truth
segun evaluar.py del D1 (mismo criterio para antes y despues). Lo usan benchmark_antes.ipynb y
benchmark_despues.ipynb en Colab; en local sirve para volver a revisar los resultados bajados.

Uso local:
  python benchmark_ft.py --probar   <benchmark.json> <resultados.json>
  python benchmark_ft.py --comparar <benchmark.json> <resultados_antes.json> <resultados_despues.json>
  python benchmark_ft.py --techo    <benchmark.json>     # fechas que acierta el resolvedor (no depende del modelo)

Formato de resultados (compatible con evaluar.py): [{id, texto, resultado_modelo, crudo, segundos, json_valido}]
"""

import json
import os
import sys
from math import comb

import evaluar as ev
import resolvedor_temporal as rt


def cargar(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["frases"], data["metadata"]


def guardar(obj, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def correr(ruta_benchmark, extraer):
    """extraer(texto, fecha_ref) -> (evento, info) con info = {crudo, segundos, error}."""
    frases, meta = cargar(ruta_benchmark)
    resultados = []
    for i, frase in enumerate(frases, 1):
        evento, info = extraer(frase["texto"], meta["fecha_referencia"])
        resultados.append({
            "id": frase["id"], "texto": frase["texto"], "resultado_modelo": evento,
            "crudo": info["crudo"], "segundos": round(info["segundos"], 2), "json_valido": not info["error"],
        })
        print(f"  [{i:2d}/{len(frases)}] {info['segundos']:5.1f} s  {frase['texto'][:70]}")
    return resultados


def _evaluar(frases, resultados):
    mapa = {r["id"]: r["resultado_modelo"] for r in resultados}
    return [ev.evaluar_resultado(f, mapa.get(f["id"]) or {}) for f in frases]


def techo_fecha(frases, fecha_ref):
    """Fechas correctas del resolvedor solo: igual antes y despues (el modelo no calcula la fecha)."""
    return sum(rt.resolver_fecha(f["texto"], fecha_ref) == f["ground_truth"]["fecha"] for f in frases)


def probar(ruta_benchmark, resultados, nombre, detalle=True):
    """Corre las pruebas: PASA/FALLA por frase y metricas de evaluar.py. Devuelve (metricas, evaluados)."""
    frases, meta = cargar(ruta_benchmark)
    evaluados = _evaluar(frases, resultados)
    if detalle:
        print(f"\nPRUEBAS: {nombre} sobre {os.path.basename(ruta_benchmark)} ({len(frases)} frases)")
        for e in evaluados:
            print(f"  {'PASA ' if e['es_correcto_total'] else 'FALLA'} #{e['id']:<3d} {e['texto'][:80]}")
            for d in e["detalles"]:
                if not d["correcto"]:
                    print(f"          {d['campo']}: esperado {d['esperado']!r} -> obtenido {d['obtenido']!r} ({d['tipo_error']})")
    metricas = ev.calcular_metricas(evaluados)
    metricas["json_valido"] = sum(1 for r in resultados if r.get("json_valido", True))
    tiempos = [r["segundos"] for r in resultados if "segundos" in r]
    metricas["segundos_promedio"] = round(sum(tiempos) / len(tiempos), 2) if tiempos else None
    metricas["techo_fecha_resolvedor"] = techo_fecha(frases, meta["fecha_referencia"])
    ev.imprimir_reporte(metricas, nombre)
    print(f"  JSON valido: {metricas['json_valido']}/{len(frases)} | segundos por frase: {metricas['segundos_promedio']}"
          f" | fechas que acierta el resolvedor solo: {metricas['techo_fecha_resolvedor']}/{len(frases)}")
    return metricas, evaluados


def _mcnemar(b, c):
    """p-valor exacto (binomial, dos colas) sobre los pares discordantes."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def comparar(ruta_benchmark, res_antes, res_despues):
    """Antes vs despues sobre las mismas frases y el mismo criterio. Devuelve un resumen (dict)."""
    frases, meta = cargar(ruta_benchmark)
    ea, ed = _evaluar(frases, res_antes), _evaluar(frases, res_despues)
    ma, md = ev.calcular_metricas(ea), ev.calcular_metricas(ed)
    n = len(frases)

    def pct(x):
        return f"{x:5.1f}%"

    print("\n" + "=" * 72)
    print(f"  ANTES vs DESPUES DEL FINE-TUNING - {os.path.basename(ruta_benchmark)} ({n} frases)")
    print("=" * 72)
    print(f"  {'':28s} {'antes':>10s} {'despues':>10s} {'cambio':>10s}")
    print(f"  {'frases 100% correctas':28s} {ma['correctos_totales']:>6d}/{n:<3d} {md['correctos_totales']:>6d}/{n:<3d}"
          f" {md['correctos_totales'] - ma['correctos_totales']:>+10d}")
    print(f"  {'exactitud':28s} {pct(ma['precision_total']):>10s} {pct(md['precision_total']):>10s}"
          f" {md['precision_total'] - ma['precision_total']:>+9.1f}pp")
    ja = sum(1 for r in res_antes if r.get("json_valido", True))
    jd = sum(1 for r in res_despues if r.get("json_valido", True))
    print(f"  {'JSON valido':28s} {ja:>6d}/{n:<3d} {jd:>6d}/{n:<3d}")
    ta = [r["segundos"] for r in res_antes if "segundos" in r]
    td = [r["segundos"] for r in res_despues if "segundos" in r]
    if ta and td:
        print(f"  {'segundos por frase':28s} {sum(ta) / len(ta):>10.2f} {sum(td) / len(td):>10.2f}")

    print("\n  --- Exactitud por campo ---")
    for campo in ev.CAMPOS_OBLIGATORIOS:
        a, d = ma["precision_por_campo"][campo]["precision"], md["precision_por_campo"][campo]["precision"]
        nota = "  (resolvedor: igual en ambos)" if campo == "fecha" else "  (reglas: igual en ambos)" if campo == "zona_horaria" else ""
        print(f"  {campo:28s} {pct(a):>10s} {pct(d):>10s} {d - a:>+9.1f}pp{nota}")

    print("\n  --- Exactitud por categoria ---")
    for cat in sorted(md["precision_por_categoria"]):
        a, d = ma["precision_por_categoria"][cat], md["precision_por_categoria"][cat]
        print(f"  {cat:28s} {a['correctos']:>6d}/{a['total']:<3d} {d['correctos']:>6d}/{d['total']:<3d}"
              f" {d['correctos'] - a['correctos']:>+10d}")

    arreglo = [(x, y) for x, y in zip(ea, ed) if not x["es_correcto_total"] and y["es_correcto_total"]]
    rompio = [(x, y) for x, y in zip(ea, ed) if x["es_correcto_total"] and not y["es_correcto_total"]]
    p = _mcnemar(len(rompio), len(arreglo))
    print(f"\n  Frases que el fine-tuning ARREGLO ({len(arreglo)}):")
    for x, _ in arreglo:
        fallos = ", ".join(d["campo"] for d in x["detalles"] if not d["correcto"])
        print(f"    #{x['id']:<3d} {x['texto'][:70]}  [antes fallaba: {fallos}]")
    print(f"  Frases que el fine-tuning ROMPIO ({len(rompio)}):")
    for _, y in rompio:
        fallos = ", ".join(d["campo"] for d in y["detalles"] if not d["correcto"])
        print(f"    #{y['id']:<3d} {y['texto'][:70]}  [ahora falla: {fallos}]")
    print(f"\n  McNemar exacto (pares discordantes {len(arreglo)} vs {len(rompio)}): p = {p:.3f}"
          + ("  -> diferencia significativa (p < 0.05)" if p < 0.05 else "  -> no alcanza significancia (p >= 0.05)"))
    print("=" * 72)

    return {
        "benchmark": os.path.basename(ruta_benchmark), "total_frases": n,
        "antes": ma, "despues": md,
        "arreglo": [x["id"] for x, _ in arreglo], "rompio": [y["id"] for _, y in rompio],
        "mcnemar_p": p,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--probar":
        with open(args[2], encoding="utf-8") as f:
            probar(args[1], json.load(f), os.path.splitext(os.path.basename(args[2]))[0])
    elif len(args) == 4 and args[0] == "--comparar":
        with open(args[2], encoding="utf-8") as f, open(args[3], encoding="utf-8") as g:
            comparar(args[1], json.load(f), json.load(g))
    elif len(args) == 2 and args[0] == "--techo":
        frases, meta = cargar(args[1])
        print(f"fechas correctas del resolvedor: {techo_fecha(frases, meta['fecha_referencia'])}/{len(frases)}")
    else:
        print(__doc__)
        sys.exit(1)

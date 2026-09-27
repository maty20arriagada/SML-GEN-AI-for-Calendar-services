"""
evaluar.py - Script de evaluación del benchmark de agendamiento de reuniones.

Uso:
  1. Generar salidas del modelo: python evaluar.py --generar
  2. Evaluar resultados:        python evaluar.py --evaluar
  3. Comparar modelos:          python evaluar.py --comparar

Archivos esperados:
  benchmark/frases.json          -> Benchmark con ground truth
  benchmark/resultados_{modelo}.json -> Salidas del modelo a evaluar
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_PATH = os.path.join(SCRIPT_DIR, "frases.json")
RESULTADOS_DIR = SCRIPT_DIR

CAMPOS_OBLIGATORIOS = [
    "titulo", "fecha", "hora_inicio", "duracion_minutos",
    "participantes", "ubicacion", "recordatorio_minutos", "zona_horaria"
]


def cargar_benchmark():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["frases"], data["metadata"]


def cargar_resultados(nombre_modelo):
    path = os.path.join(RESULTADOS_DIR, f"resultados_{nombre_modelo}.json")
    if not os.path.exists(path):
        print(f"[ERROR] No se encontro: {path}")
        print(f"        Primero genera las salidas con: python evaluar.py --generar")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def comparar_campos(esperado, obtenido):
    """Compara dos valores de campo y retorna (correcto, tipo_error)."""
    if esperado is None and obtenido is None:
        return True, None
    if esperado is None and obtenido is not None:
        return False, "inventado"
    if esperado is not None and obtenido is None:
        return False, "omision"

    if isinstance(esperado, list):
        if not isinstance(obtenido, list):
            return False, "formato_incorrecto"
        esp_set = set(str(x).strip().lower() for x in esperado)
        opt_set = set(str(x).strip().lower() for x in obtenido)
        if esp_set == opt_set:
            return True, None
        faltantes = esp_set - opt_set
        extra = opt_set - esp_set
        if faltantes:
            return False, "omision"
        if extra:
            return False, "inventado"
        return False, "formato_incorrecto"

    esp_str = str(esperado).strip().lower()
    opt_str = str(obtenido).strip().lower()

    if esp_str == opt_str:
        return True, None

    if isinstance(esperado, str) and isinstance(obtenido, str):
        if esp_str in opt_str or opt_str in esp_str:
            return True, None

    return False, "valor_incorrecto"


def evaluar_resultado(frase, resultado_modelo):
    """Evalúa un resultado contra el ground truth. Retorna dict con detalles."""
    gt = frase["ground_truth"]
    detalles = []
    campos_correctos = 0
    total_campos = len(CAMPOS_OBLIGATORIOS)

    for campo in CAMPOS_OBLIGATORIOS:
        esperado = gt.get(campo)
        obtenido = resultado_modelo.get(campo)

        # Caso especial: duracion_minutos puede inferirse de hora_inicio + duracion
        if campo == "duracion_minutos" and obtenido is None and esperado is not None:
            # No penalizar si el modelo no infiere duración
            pass

        correcto, tipo_error = comparar_campos(esperado, obtenido)
        if correcto:
            campos_correctos += 1

        detalles.append({
            "campo": campo,
            "esperado": esperado,
            "obtenido": obtenido,
            "correcto": correcto,
            "tipo_error": tipo_error
        })

    es_correcto_total = campos_correctos == total_campos

    return {
        "id": frase["id"],
        "texto": frase["texto"],
        "categoria": frase["categoria"],
        "campos_correctos": campos_correctos,
        "total_campos": total_campos,
        "es_correcto_total": es_correcto_total,
        "detalles": detalles
    }


def calcular_metricas(resultados):
    """Calcula métricas agregadas de todos los resultados."""
    total = len(resultados)
    correctos_total = sum(1 for r in resultados if r["es_correcto_total"])

    errores_por_tipo = defaultdict(int)
    errores_por_categoria = defaultdict(lambda: {"total": 0, "correctos": 0})
    campos_acertados = defaultdict(int)
    campos_total = defaultdict(int)

    for r in resultados:
        cat = r["categoria"]
        errores_por_categoria[cat]["total"] += 1
        if r["es_correcto_total"]:
            errores_por_categoria[cat]["correctos"] += 1

        for d in r["detalles"]:
            campo = d["campo"]
            campos_total[campo] += 1
            if d["correcto"]:
                campos_acertados[campo] += 1
            elif d["tipo_error"]:
                errores_por_tipo[d["tipo_error"]] += 1

    metricas = {
        "total_frases": total,
        "correctos_totales": correctos_total,
        "precision_total": round(correctos_total / total * 100, 1) if total > 0 else 0,
        "precision_por_categoria": {},
        "precision_por_campo": {},
        "errores_por_tipo": dict(errores_por_tipo)
    }

    for cat, vals in errores_por_categoria.items():
        metricas["precision_por_categoria"][cat] = {
            "total": vals["total"],
            "correctos": vals["correctos"],
            "precision": round(vals["correctos"] / vals["total"] * 100, 1) if vals["total"] > 0 else 0
        }

    for campo in CAMPOS_OBLIGATORIOS:
        t = campos_total.get(campo, 0)
        c = campos_acertados.get(campo, 0)
        metricas["precision_por_campo"][campo] = {
            "total": t,
            "correctos": c,
            "precision": round(c / t * 100, 1) if t > 0 else 0
        }

    return metricas


def imprimir_reporte(metricas, nombre_modelo="modelo"):
    """Imprime el reporte en consola."""
    print("\n" + "=" * 60)
    print(f"  REPORTE DE EVALUACION: {nombre_modelo.upper()}")
    print("=" * 60)

    print(f"\n  Total frases:    {metricas['total_frases']}")
    print(f"  Correctas:       {metricas['correctos_totales']}")
    print(f"  Precision total: {metricas['precision_total']}%")

    print("\n  --- Precision por categoria ---")
    for cat, vals in sorted(metricas["precision_por_categoria"].items()):
        barra = "#" * int(vals["precision"] / 5)
        print(f"  {cat:20s}: {vals['precision']:5.1f}% ({vals['correctos']}/{vals['total']}) {barra}")

    print("\n  --- Precision por campo ---")
    for campo, vals in metricas["precision_por_campo"].items():
        barra = "#" * int(vals["precision"] / 5)
        print(f"  {campo:25s}: {vals['precision']:5.1f}% ({vals['correctos']}/{vals['total']}) {barra}")

    if metricas["errores_por_tipo"]:
        print("\n  --- Errores por tipo ---")
        for tipo, cantidad in sorted(metricas["errores_por_tipo"].items(), key=lambda x: -x[1]):
            print(f"  {tipo:25s}: {cantidad}")

    print("\n" + "=" * 60)


def guardar_reporte(metricas, nombre_modelo, resultados_detalles):
    """Guarda el reporte como JSON."""
    reporte = {
        "modelo": nombre_modelo,
        "fecha_evaluacion": datetime.now().isoformat(),
        "metricas": metricas,
        "detalles_por_frase": resultados_detalles
    }
    path = os.path.join(RESULTADOS_DIR, f"reporte_{nombre_modelo}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    print(f"\n  Reporte guardado en: {path}")


def modo_generar():
    """Genera una plantilla de resultados para que el usuario la complete."""
    frases, _ = cargar_benchmark()
    plantilla = []
    for frase in frases:
        plantilla.append({
            "id": frase["id"],
            "texto": frase["texto"],
            "resultado_modelo": {
                "titulo": None,
                "fecha": None,
                "hora_inicio": None,
                "duracion_minutos": None,
                "participantes": [],
                "ubicacion": None,
                "recordatorio_minutos": None,
                "zona_horaria": None
            }
        })

    path = os.path.join(RESULTADOS_DIR, "resultados_PLANTILLA.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plantilla, f, indent=2, ensure_ascii=False)
    print(f"Plantilla generada: {path}")
    print("Completa 'resultado_modelo' para cada frase y renombra a resultados_{nombre_modelo}.json")


def modo_evaluar(nombre_modelo):
    """Evalúa los resultados de un modelo específico."""
    frases, metadata = cargar_benchmark()
    resultados_raw = cargar_resultados(nombre_modelo)

    mapa_resultados = {}
    for r in resultados_raw:
        mapa_resultados[r["id"]] = r["resultado_modelo"]

    resultados_evaluados = []
    for frase in frases:
        rid = frase["id"]
        if rid in mapa_resultados:
            ev = evaluar_resultado(frase, mapa_resultados[rid])
            resultados_evaluados.append(ev)
        else:
            print(f"[WARN] Frase {rid} sin resultado del modelo")

    metricas = calcular_metricas(resultados_evaluados)
    imprimir_reporte(metricas, nombre_modelo)
    guardar_reporte(metricas, nombre_modelo, resultados_evaluados)

    return metricas


def modo_comparar(modelos):
    """Compara múltiples modelos lado a lado."""
    todos_metricas = {}
    for modelo in modelos:
        frases, _ = cargar_benchmark()
        resultados_raw = cargar_resultados(modelo)
        mapa = {r["id"]: r["resultado_modelo"] for r in resultados_raw}

        evaluados = []
        for frase in frases:
            if frase["id"] in mapa:
                evaluados.append(evaluar_resultado(frase, mapa[frase["id"]]))

        todos_metricas[modelo] = calcular_metricas(evaluados)

    print("\n" + "=" * 70)
    print("  COMPARACION DE MODELOS")
    print("=" * 70)
    print(f"\n  {'Modelo':20s} {'Precision':>10s} {'Correctas':>10s} {'Total':>8s}")
    print("  " + "-" * 50)
    for modelo, m in sorted(todos_metricas.items(), key=lambda x: -x[1]["precision_total"]):
        print(f"  {modelo:20s} {m['precision_total']:>9.1f}% {m['correctos_totales']:>9d} {m['total_frases']:>7d}")

    print("\n  --- Precision por campo ---")
    campos = CAMPOS_OBLIGATORIOS
    header = f"  {'Campo':25s}"
    for modelo in modelos:
        header += f" {modelo[:10]:>12s}"
    print(header)
    print("  " + "-" * (25 + 13 * len(modelos)))

    for campo in campos:
        linea = f"  {campo:25s}"
        for modelo in modelos:
            p = todos_metricas[modelo]["precision_por_campo"].get(campo, {}).get("precision", 0)
            linea += f" {p:>11.1f}%"
        print(linea)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUso:")
        print("  python evaluar.py --generar                    # Genera plantilla")
        print("  python evaluar.py --evaluar <nombre_modelo>    # Evalúa un modelo")
        print("  python evaluar.py --comparar m1 m2 m3          # Compara modelos")
        print("\nEjemplo:")
        print("  python evaluar.py --evaluar tinyllama")
        sys.exit(0)

    if sys.argv[1] == "--generar":
        modo_generar()
    elif sys.argv[1] == "--evaluar" and len(sys.argv) >= 3:
        modo_evaluar(sys.argv[2])
    elif sys.argv[1] == "--comparar" and len(sys.argv) >= 4:
        modo_comparar(sys.argv[2:])
    else:
        print("[ERROR] Argumentos invalidos. Ejecuta sin argumentos para ver ayuda.")

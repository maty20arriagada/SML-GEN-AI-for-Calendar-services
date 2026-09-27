# -*- coding: utf-8 -*-
"""
validar_dataset.py -- Verifica que los labels del dataset sintetico sean
extraibles de la frase (no inventados) y que no haya fuga con Benchmark2.

Reglas que valida:
  1. El target tiene exactamente los 6 campos del modelo.
  2. titulo (si esta en la frase), participantes y ubicacion (no nulos) aparecen
     como subcadena normalizada de la frase. Los titulos derivados del verbo
     (meta.titulo_derivado) se saltean: la etiqueta no esta en la superficie.
  3. El resolvedor temporal coincide con la fecha/hora guardadas en meta.
  4. Ninguna frase de train/dev/hard_dev se solapa con las 45 frases de Benchmark2.

Uso:  python datos/validar_dataset.py
"""

import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from pipeline.resolvedor_temporal import FECHA_REF, analizar_temporal  # noqa: E402

RUTA_DATOS = os.path.join(RAIZ, "datos")
RUTA_BENCHMARK = os.path.join(RAIZ, "benchmark", "benchmark2.json")

CAMPOS_MODELO = [
    "titulo", "hora_inicio", "duracion_minutos",
    "participantes", "ubicacion", "recordatorio_minutos",
]


def _norm(s: str) -> str:
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s)


def _subcadena(haystack: str, needle: str) -> bool:
    return _norm(needle).strip() in _norm(haystack)


def _ngramas(s: str, n: int = 3) -> set:
    t = re.sub(r"\s+", " ", _norm(s)).strip()
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))} if len(t) >= n else {t}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def cargar_jsonl(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def validar(filas, nombre, ng_test):
    problemas = []
    for fila in filas:
        texto, tgt, meta = fila["texto"], fila["target"], fila.get("meta", {})

        if sorted(tgt.keys()) != sorted(CAMPOS_MODELO):
            problemas.append((fila["id"], "campos_target", sorted(tgt.keys()), texto))
            continue

        if meta.get("titulo_en_frase", True):
            if not _subcadena(texto, tgt["titulo"]):
                problemas.append((fila["id"], "titulo", tgt["titulo"], texto))
        for p in tgt["participantes"]:
            if not _subcadena(texto, p):
                problemas.append((fila["id"], "participante", p, texto))
        if tgt["ubicacion"] and not _subcadena(texto, tgt["ubicacion"]):
            problemas.append((fila["id"], "ubicacion", tgt["ubicacion"], texto))

        info = analizar_temporal(texto, FECHA_REF)
        if meta.get("gt_fecha") != info["fecha"]:
            problemas.append((fila["id"], "fecha_meta", meta.get("gt_fecha"), texto))
        if tgt["hora_inicio"] != info["hora_inicio"]:
            problemas.append((fila["id"], "hora", tgt["hora_inicio"], texto))

        # etiquetado: un campo solo puede tener valor si su fragmento aparece en la frase
        slots = set(meta.get("slots_con_valor", []))
        for slot, presente in [
            ("dur", tgt["duracion_minutos"] is not None),
            ("record", tgt["recordatorio_minutos"] is not None),
            ("ub", tgt["ubicacion"] is not None),
            ("part", bool(tgt["participantes"])),
        ]:
            if presente != (slot in slots):
                problemas.append((fila["id"], "slot_inconsistente:" + slot, presente, texto))

        for t in ng_test:
            if _jaccard(_ngramas(texto), t) > 0.60:
                problemas.append((fila["id"], "SOLAPE_TEST", "-", texto))
                break

    print("%-14s %5d filas -> %d problemas" % (nombre, len(filas), len(problemas)))
    for p in problemas[:15]:
        print("   id=%s campo=%s valor=%r frase=%r" % p)
    return problemas


def main():
    with open(RUTA_BENCHMARK, encoding="utf-8") as f:
        frases_test = json.load(f)["frases"]
    ng_test = [_ngramas(f["texto"]) for f in frases_test]

    total = 0
    for nombre in ("train.jsonl", "dev.jsonl", "hard_dev.jsonl"):
        ruta = os.path.join(RUTA_DATOS, nombre)
        if not os.path.exists(ruta):
            print("%s no existe (ok si aun no se genero)" % nombre)
            continue
        total += len(validar(cargar_jsonl(ruta), nombre, ng_test))

    print("\nTOTAL problemas: %d" % total)
    if total:
        sys.exit(1)


if __name__ == "__main__":
    main()

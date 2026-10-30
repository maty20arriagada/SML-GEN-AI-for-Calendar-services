# -*- coding: utf-8 -*-
"""
hacer_numeros.py - Genera numeros.tex (macros del PDF) a partir de los resultados reales de Colab.

Uso (desde intento3/documento):
    python hacer_numeros.py ../subir_a_colab/d3_previos.zip d3_resultados_intento3.zip [fallo.tex]

Lee resultados_{brazo}_{bench}.json de los zips (los del segundo pisan a los del primero), evalua con evaluar.py
(mismo criterio que todo el proyecto) y escribe los conteos por conjunto, los McNemar exactos, las tasas de
respaldo de A3 y de devolucion de A4 (de las trazas) y el hardware. El texto del caso de falla se escribe a mano
en fallo.tex (\\failinput, \\failwhy) y se agrega al final si se pasa como tercer argumento.
"""

import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import benchmark_ft as bft  # noqa: E402

SETS = {"A": ["frases.json", "benchmark_ft.json"], "B": ["benchmark_heldout.json"],
        "C": ["benchmark_independiente.json"]}
SETS["T"] = SETS["A"] + SETS["B"] + SETS["C"]
ARMS = ["E0", "E1", "E4", "E4T1", "E4T2", "E4T3", "E4T4", "E4T5"]


def leer(zips):
    datos, trazas, hw = {}, {}, {}
    for z in (zipfile.ZipFile(p) for p in zips):
        for n in z.namelist():
            nombre = Path(n).name
            if nombre.startswith("resultados_") and nombre.endswith(".json"):
                brazo, bench = nombre[len("resultados_"):-5].split("_", 1)
                datos[(brazo, bench + ".json")] = json.loads(z.read(n))
            elif nombre.startswith("trazas_") and nombre.endswith(".jsonl"):
                brazo, bench = nombre[len("trazas_"):-6].split("_", 1)
                trazas[(brazo, bench + ".json")] = [json.loads(x) for x in z.read(n).decode("utf-8").splitlines()]
            elif nombre == "hardware_intento3.json":
                hw = json.loads(z.read(n))
    return datos, trazas, hw


def correctos(datos, brazo, benches):
    out = []
    for b in benches:
        if (brazo, b) not in datos:
            return None
        frases, _ = bft.cargar(str(RAIZ / b))
        out += [x["es_correcto_total"] for x in bft._evaluar(frases, datos[(brazo, b)])]
    return out


def fmt_p(p):
    return "$p<0.001$" if p < 0.001 else f"$p={p:.3f}$"


def main():
    zips = sys.argv[1:3]
    datos, trazas, hw = leer(zips)
    L = [r"\newcommand{\setres}[3]{\expandafter\def\csname R#1#2\endcsname{#3}}",
         r"\newcommand{\R}[2]{\csname R#1#2\endcsname}"]
    for brazo in ARMS:
        for s, benches in SETS.items():
            c = correctos(datos, brazo, benches)
            txt = "--" if c is None else f"{sum(c)} ({100 * sum(c) / len(c):.0f}\\%)"
            L.append(f"\\setres{{{brazo}}}{{{s}}}{{{txt}}}")
    # solo el porcentaje (franja de cifras y gráfico de puntos)
    L.append(r"\newcommand{\setpct}[3]{\expandafter\def\csname P#1#2\endcsname{#3}}\newcommand{\PCT}[2]{\csname P#1#2\endcsname}")
    for brazo in ARMS:
        for s, benches in SETS.items():
            c = correctos(datos, brazo, benches)
            L.append(f"\\setpct{{{brazo}}}{{{s}}}{{{'--' if c is None else f'{100 * sum(c) / len(c):.0f}'}}}")
    # set B por clase de falla (mapa de calor): \cls{brazo}{categoria} -> \heatcell{correctos}{total}
    L.append(r"\newcommand{\setcls}[4]{\expandafter\def\csname CLS#1#2\endcsname{\heatcell{#3}{#4}}}\newcommand{\cls}[2]{\csname CLS#1#2\endcsname}")
    frases_b, _ = bft.cargar(str(RAIZ / "benchmark_heldout.json"))
    for brazo in ARMS:
        if (brazo, "benchmark_heldout.json") not in datos:
            continue
        ev = bft._evaluar(frases_b, datos[(brazo, "benchmark_heldout.json")])
        cuenta = {}
        for f, x in zip(frases_b, ev):
            c, t = cuenta.get(f["categoria"], (0, 0))
            cuenta[f["categoria"]] = (c + x["es_correcto_total"], t + 1)
        for cat, (c, t) in cuenta.items():
            L.append(f"\\setcls{{{brazo}}}{{{cat}}}{{{c}}}{{{t}}}")
    # diferencia de cada brazo frente a E4 (mismos inputs)
    L += [r"\newcommand{\setdelta}[3]{\expandafter\def\csname D#1#2\endcsname{#3}}",
          r"\newcommand{\dlt}[2]{\csname D#1#2\endcsname}"]
    for brazo in ARMS:
        for s, benches in SETS.items():
            c, ref = correctos(datos, brazo, benches), correctos(datos, "E4", benches)
            d = None if c is None or ref is None else sum(c) - sum(ref)
            txt = "--" if d is None else ("0" if d == 0 else ("+" if d > 0 else "$-$") + str(abs(d)))
            L.append(f"\\setdelta{{{brazo}}}{{{s}}}{{{txt}}}")
            if s == "T":   # barra de la sección 4: 0,03 cm por input perdido
                L.append(f"\\expandafter\\def\\csname BL{brazo}\\endcsname{{{0 if d is None else abs(d) * 0.03:.2f}cm}}")
    L.append(r"\newcommand{\dlen}[1]{\csname BL#1\endcsname}")
    L.append(r"\newcommand{\nA}{93}\newcommand{\nB}{41}\newcommand{\nC}{26}\newcommand{\nT}{160}")
    for s in ("T", "C"):
        e1, e4 = correctos(datos, "E1", SETS[s]), correctos(datos, "E4", SETS[s])
        if e1 is None or e4 is None:
            L.append(f"\\newcommand{{\\pVal{s}}}{{--}}\\newcommand{{\\fix{s}}}{{--}}\\newcommand{{\\brok{s}}}{{--}}")
            continue
        a = sum(1 for x, y in zip(e1, e4) if x and not y)
        b = sum(1 for x, y in zip(e1, e4) if not x and y)
        L.append(f"\\newcommand{{\\pVal{s}}}{{{fmt_p(bft._mcnemar(a, b))}}}\\newcommand{{\\fix{s}}}{{{b}}}\\newcommand{{\\brok{s}}}{{{a}}}")
    # salidas distintas de E4 (no solo el conteo): cuántos inputs cambian al quitar cada técnica
    L.append(r"\newcommand{\setchg}[2]{\expandafter\def\csname CHG#1\endcsname{#2}}\newcommand{\chg}[1]{\csname CHG#1\endcsname}")
    for brazo in ARMS[3:]:
        dif = 0
        for b in SETS["T"]:
            if (brazo, b) not in datos or ("E4", b) not in datos:
                dif = "--"
                break
            ref = {x["id"]: x["resultado_modelo"] for x in datos[("E4", b)]}
            dif += sum(1 for x in datos[(brazo, b)] if x["resultado_modelo"] != ref.get(x["id"]))
        L.append(f"\\setchg{{{brazo}}}{{{dif}}}")
    n = respaldo = vueltas = rechazos = corr = corr_rech = 0
    for (brazo, _), ts in trazas.items():
        if brazo != "E4":
            continue
        for t in ts:
            n += 1
            ag = [x for x in t["turnos"] if x["tipo"] == "agente"]
            respaldo += any(x.get("respaldo") for x in ag if x["agente"] == "A3_Temporal")
            vueltas += any(x.get("accion") == "devolver_a_A3" for x in ag if x["agente"] == "A4_Verificador")
            rechazos += any(x.get("accion") == "rechazar" for x in ag if x["agente"] == "A1_Triage")
            for x in ag:
                if x["agente"] == "A4_Verificador" and x.get("accion") == "corregir":
                    corr += 1
                    corr_rech += bool(x.get("correcciones_rechazadas"))
    pct = lambda k: "--" if not n else f"{100 * k / n:.0f}\\%"
    L.append(f"\\newcommand{{\\fallbackrate}}{{{pct(respaldo)}}}\\newcommand{{\\loopsrate}}{{{pct(vueltas)}}}")
    L.append(f"\\newcommand{{\\triagerej}}{{{rechazos}}}\\newcommand{{\\corrN}}{{{corr}}}\\newcommand{{\\corrRej}}{{{corr_rech}}}")
    va, ve = hw.get("vram_max_agentes_gb"), hw.get("vram_max_E0_modelo_base_gb")
    vd = "--" if va is None or ve is None else f"{float(va) - float(ve):.2f}"
    L.append(f"\\newcommand{{\\vramA}}{{{va or '--'}}}\\newcommand{{\\vramE}}{{{ve or '--'}}}\\newcommand{{\\vramD}}{{{vd}}}")
    if len(sys.argv) > 3:
        L.append(Path(sys.argv[3]).read_text(encoding="utf-8"))
    else:
        L.append(r"\newcommand{\failinput}{[FAILURE INPUT]}\newcommand{\failwhy}{[WHY IT FAILS]}")
    Path(__file__).with_name("numeros.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("numeros.tex escrito;", n, "trazas de E4")


if __name__ == "__main__":
    main()

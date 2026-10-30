# -*- coding: utf-8 -*-
"""
demo_calendar.py - Demo en vivo de CalendarBot (E4) conectada a Google Calendar.

frase -> E4 (A1 -> A2 -> A3 <-> herramientas -> A4) -> contrato de 9 campos -> calendario.py -> Google Calendar

calendario.py es el del Deliverable 2 sin cambios (OAuth de escritorio, calendario "CalendarBot",
respaldo .ics si falla la API). Este módulo agrega lo propio del D3:
  - la fecha de referencia es hoy (America/Santiago), no la fija de los benchmarks;
  - un evento RECHAZADO (A1) o sin fecha/hora no se envía; si falta fecha u hora el chat lo pregunta,
    como en la demo del D2, y el siguiente mensaje completa solo lo que faltaba;
  - E4 entrega `recurrence` como texto RRULE y calendario.py espera un dict: se convierte aquí;
  - junto a E4 se muestra la solución D2 (E1) sobre la misma frase.

Chat (Colab, ver generar_notebook_demo.py):
  chat = dc.Chat(motor, enviar=True)
  chat.mensaje("Agéndame una reunión con Pablo el viernes a las 4")
Sin modelo, para ver cómo quedaría un evento ya extraído:
  python demo_vivo/demo_calendar.py evento.json
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from demo_vivo import calendario
except ImportError:   # ejecutado como script desde demo_vivo/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import calendario

ESTADOS_SIN_EVENTO = ("RECHAZADO", "INCOMPLETO")
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
            "septiembre", "octubre", "noviembre", "diciembre"]
UNIDADES = {"daily": "día", "weekly": "semana", "monthly": "mes"}
CAMPOS_E1 = ["fecha", "hora_inicio", "duracion_minutos", "participantes", "ubicacion", "recordatorio_minutos", "zona_horaria"]


def hoy_santiago() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")
    except Exception:   # sin base de zonas (Windows sin tzdata): offset fijo, basta para la fecha de referencia
        return (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")


def estado_final(traza) -> Optional[str]:
    for turno in reversed(traza.turnos):
        if turno.get("tipo") == "evento":
            return turno["estado"]
    return None


def faltante(evento: Dict[str, Any]) -> List[str]:
    return [t for t, campo in (("qué día", "fecha"), ("a qué hora", "hora_inicio")) if not evento.get(campo)]


def completar(pendiente: Dict[str, Any], nuevo: Dict[str, Any]) -> Dict[str, Any]:
    """Rellena solo los campos que le faltaban al evento pendiente."""
    r = dict(pendiente)
    for campo, valor in nuevo.items():
        if r.get(campo) in (None, []) and valor not in (None, []):
            r[campo] = valor
    return r


# --- contrato -> calendario ------------------------------------------------------------------------------

def rrule_a_dict(rr: Any) -> Any:
    """'RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=5' -> dict que entiende calendario.py. Un dict pasa tal cual."""
    if not rr or isinstance(rr, dict):
        return rr
    partes = dict(p.split("=", 1) for p in str(rr).replace("RRULE:", "").split(";") if "=" in p)
    out: Dict[str, Any] = {"frecuencia": partes.get("FREQ", "WEEKLY").lower()}
    if partes.get("INTERVAL", "").isdigit():
        out["intervalo"] = int(partes["INTERVAL"])
    if partes.get("COUNT", "").isdigit():
        out["veces"] = int(partes["COUNT"])
    return out


def para_calendario(evento: Dict[str, Any]) -> Dict[str, Any]:
    ev = dict(evento)
    ev["recurrence"] = rrule_a_dict(ev.get("recurrence"))
    return ev


# --- texto -----------------------------------------------------------------------------------------------

def fecha_es(iso: str) -> str:
    f = datetime.strptime(iso, "%Y-%m-%d")
    return f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month - 1]} de {f.year}"


def resumen(ev: Dict[str, Any]) -> str:
    """Frase corta para el chat (HTML)."""
    t = f"<b>{html.escape(ev.get('titulo') or 'Reunión')}</b> el {fecha_es(ev['fecha'])} a las {ev['hora_inicio']}"
    dur = ev.get("duracion_minutos")
    t += f" ({dur} min)" if dur else f" ({calendario.DURACION_DEFECTO} min, duración por defecto)"
    if ev.get("ubicacion"):
        t += f" en {html.escape(str(ev['ubicacion']))}"
    if ev.get("participantes"):
        t += " con " + ", ".join(html.escape(str(p)) for p in ev["participantes"])
    t += "."
    rec = rrule_a_dict(ev.get("recurrence"))
    if rec:
        unidad = UNIDADES.get(rec.get("frecuencia"), "semana")
        n = int(rec.get("intervalo") or 1)
        t += f" Se repite cada {unidad}." if n == 1 else f" Se repite cada {n} {unidad}s."
    if ev.get("recordatorio_minutos") is not None:
        t += f" Te aviso {int(ev['recordatorio_minutos'])} min antes."
    return t


def resumen_traza(traza) -> list:
    """Una línea por decisión de agente: qué decidió cada uno y qué herramientas llamó A3."""
    lineas = []
    for t in traza.turnos:
        if t["tipo"] != "agente":
            continue
        partes = [t["agente"] + ":", str(t.get("accion", "")).strip()]
        if t.get("herramientas"):
            partes.append("herramientas=" + ",".join(t["herramientas"]))
        if t.get("respaldo"):
            partes.append("(respaldo: todas las herramientas)")
        lineas.append(" ".join(p for p in partes if p))
    lineas.append(f"estado final: {estado_final(traza)}")
    return lineas


def describir(evento: Dict[str, Any]) -> list:
    dur = evento.get("duracion_minutos")
    dur_txt = f"{dur} min" if dur else f"{calendario.DURACION_DEFECTO} min (por defecto: la frase no la dice)"
    rec = evento.get("recordatorio_minutos")
    return [
        f"título:       {evento.get('titulo')}",
        f"cuándo:       {evento.get('fecha')} {evento.get('hora_inicio')} ({evento.get('zona_horaria')})",
        f"duración:     {dur_txt}",
        f"participantes: {', '.join(evento.get('participantes') or []) or '—'}",
        f"ubicación:    {evento.get('ubicacion') or '—'}",
        f"recordatorio: {f'{rec} min antes' if rec is not None else '—'}",
        f"recurrencia:  {evento.get('recurrence') or '—'}",
    ]


# --- envío -----------------------------------------------------------------------------------------------

def _a_google(evento, enviar, credenciales, ruta_token) -> Dict[str, Any]:
    res = calendario.crear_en_google(para_calendario(evento), credenciales, ruta_token, enviar=enviar)
    return {"creado": bool(res.get("id")), "simulacro": not enviar,
            "link": res.get("htmlLink"), "ics": res.get("ics"), "error": res.get("error")}


def crear_evento(evento: Dict[str, Any], traza, enviar: bool = True,
                 credenciales: str = "credentials.json", ruta_token: str = "token_google.json") -> Dict[str, Any]:
    """Crea el evento en Google Calendar salvo que el sistema no haya llegado a un evento completo."""
    estado = estado_final(traza)
    if estado == "RECHAZADO":
        return {"creado": False, "estado": estado, "motivo": "A1 rechazó la frase: no es un evento agendable"}
    if estado == "INCOMPLETO" or faltante(evento):
        return {"creado": False, "estado": estado, "motivo": "el evento quedó sin fecha u hora: no se envía"}
    return {"estado": estado, **_a_google(evento, enviar, credenciales, ruta_token)}


def preguntar() -> bool:
    return input("¿Crear el evento en Google Calendar? [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")


def procesar(frase: str, motor: Any, *, fecha_ref: Optional[str] = None, enviar: bool = True,
             confirmar: Optional[Callable[[], bool]] = None, dir_trazas: Optional[str] = None,
             credenciales: str = "credentials.json", ruta_token: str = "token_google.json",
             salida: Callable[[str], None] = print) -> Dict[str, Any]:
    """Una frase en texto plano (sin chat): E4, muestra el resultado y, si se confirma, crea el evento."""
    from deliverable3.agentes import BRAZOS
    from deliverable3.grafo import ejecutar

    fecha_ref = fecha_ref or hoy_santiago()
    evento, traza = ejecutar(frase, cfg=BRAZOS["E4"], motor=motor, fecha_ref=fecha_ref)
    salida(f"\nAgentes (hoy = {fecha_ref}):")
    for linea in resumen_traza(traza):
        salida("  " + linea)
    estado = estado_final(traza)
    if estado not in ESTADOS_SIN_EVENTO:
        salida("\nEvento:")
        for linea in describir(evento):
            salida("  " + linea)
    if dir_trazas:
        Path(dir_trazas).mkdir(parents=True, exist_ok=True)
        salida("  traza -> " + traza.guardar(Path(dir_trazas) / f"demo_{datetime.now().strftime('%H%M%S')}.jsonl"))

    if confirmar is not None and estado not in ESTADOS_SIN_EVENTO and not confirmar():
        resultado = {"creado": False, "estado": estado, "motivo": "no confirmado por la persona"}
    else:
        resultado = crear_evento(evento, traza, enviar=enviar, credenciales=credenciales, ruta_token=ruta_token)
    if not resultado["creado"]:
        salida(f"\nNo se creó: {resultado.get('motivo') or 'simulacro'}")
    elif resultado.get("link"):
        salida(f"\nCreado: {resultado['link']}")
    return {"evento": evento, "traza": traza, **resultado}


# --- chat (formato de la demo del D2) ---------------------------------------------------------------------

class Chat:
    """Chat de una celda tipo formulario: cada `mensaje()` es un turno; si falta fecha u hora, el siguiente
    mensaje completa el evento pendiente (esa vuelta corre E4 sin A1: «el viernes a las 4» solo no es un evento)."""

    ESTILOS = {
        "tu": ("flex-end", "#dcf8c6", "Tú"),
        "bot": ("flex-start", "#f1f0f0", "CalendarBot (agentes E4)"),
        "baseline": ("flex-start", "#fff4e5", "Solución D2 (E1), misma frase"),
    }

    def __init__(self, motor: Any, *, enviar: bool = True, destino: str = "google", mostrar_baseline: bool = True,
                 dir_trazas: Optional[str] = None, credenciales: str = "credentials.json",
                 ruta_token: str = "token_google.json", descargar: Optional[Callable[[str], None]] = None):
        self.motor, self.enviar, self.destino = motor, enviar, destino
        self.mostrar_baseline, self.dir_trazas = mostrar_baseline, dir_trazas
        self.credenciales, self.ruta_token, self.descargar = credenciales, ruta_token, descargar
        self.historial: List[Tuple[str, str]] = []
        self.pendiente: Optional[Dict[str, Any]] = None

    def reiniciar(self) -> None:
        self.historial.clear()
        self.pendiente = None

    def _detalle(self, ev, traza) -> str:
        return ("<details style='margin-top:6px'><summary>Agentes y JSON</summary>"
                "<pre style='white-space:pre-wrap'>" + html.escape("\n".join(resumen_traza(traza))) + "</pre>"
                "<pre style='white-space:pre-wrap'>" + html.escape(json.dumps(ev, indent=2, ensure_ascii=False))
                + "</pre></details>")

    def _entregar(self, evento) -> str:
        if self.destino == "google":
            res = _a_google(evento, self.enviar, self.credenciales, self.ruta_token)
            if res["link"]:
                return f"Listo, agendé {resumen(evento)} <a href='{res['link']}' target='_blank'>Ver en el calendario</a>"
            if res["simulacro"]:
                return f"(simulacro, no se creó nada) Habría agendado {resumen(evento)}"
            return (f"No pude crearlo en Google ({html.escape(str(res['error']))}). Preparé {resumen(evento)} "
                    f"Te dejo el archivo {html.escape(str(res['ics']))} para importarlo.")
        ruta = f"evento_{datetime.now().strftime('%H%M%S')}.ics"
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(calendario.a_ics(para_calendario(evento)))
        if self.descargar:
            self.descargar(ruta)
        return f"Preparé {resumen(evento)} Te dejo el archivo {ruta} para agregarlo a tu calendario."

    def mensaje(self, solicitud: str, *, fecha_ref: Optional[str] = None, mostrar: bool = True) -> Dict[str, Any]:
        from deliverable3.agentes import BRAZOS
        from deliverable3.grafo import ejecutar

        fecha_ref = fecha_ref or hoy_santiago()
        self.historial.append(("tu", html.escape(solicitud)))
        if self.mostrar_baseline:
            e1, _ = ejecutar(solicitud, cfg=BRAZOS["E1"], motor=self.motor, fecha_ref=fecha_ref)
            self.historial.append(("baseline", "<pre style='white-space:pre-wrap;margin:0'>" + html.escape(
                json.dumps({c: e1.get(c) for c in CAMPOS_E1}, ensure_ascii=False, indent=1)) + "</pre>"))

        cfg = BRAZOS["E4T5"] if self.pendiente is not None else BRAZOS["E4"]
        evento, traza = ejecutar(solicitud, cfg=cfg, motor=self.motor, fecha_ref=fecha_ref)
        estado = estado_final(traza)
        if self.pendiente is not None:
            evento = completar(self.pendiente, evento)
        if self.dir_trazas:
            Path(self.dir_trazas).mkdir(parents=True, exist_ok=True)
            traza.guardar(Path(self.dir_trazas) / f"demo_{datetime.now().strftime('%H%M%S')}.jsonl")

        creado = False
        if estado == "RECHAZADO" and self.pendiente is None:
            texto = ("Eso no parece un evento para agendar (A1 lo rechazó). ¿Me lo escribes de otra forma?"
                     + self._detalle(evento, traza))
        elif faltante(evento):
            self.pendiente = evento
            titulo = html.escape(evento.get("titulo") or "la reunión")
            texto = (f"Anoté <b>{titulo}</b>, pero me falta saber {' y '.join(faltante(evento))}. ¿Me lo dices?"
                     + self._detalle(evento, traza))
        else:
            self.pendiente = None
            texto = self._entregar(evento) + self._detalle(evento, traza)
            creado = True
        self.historial.append(("bot", texto))
        if mostrar:
            self.mostrar()
        return {"evento": evento, "traza": traza, "estado": estado, "pendiente": self.pendiente, "entregado": creado}

    def html(self) -> str:
        burbujas = []
        for quien, contenido in self.historial:
            lado, fondo, nombre = self.ESTILOS[quien]
            borde = "1px dashed #d08a00" if quien == "baseline" else "none"
            burbujas.append(
                f"<div style='display:flex;justify-content:{lado};margin:6px 0'>"
                f"<div style='max-width:75%;background:{fondo};color:#111;border:{borde};border-radius:12px;"
                f"padding:8px 12px;font-family:sans-serif;font-size:14px'>"
                f"<div style='font-size:11px;color:#555;margin-bottom:2px'>{nombre}</div>{contenido}</div></div>")
        return "<div style='max-width:760px'>" + "".join(burbujas) + "</div>"

    def mostrar(self) -> None:
        from IPython.display import HTML, display
        display(HTML(self.html()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        ev = json.load(f)
    print("\n".join(describir(ev)))
    print()
    calendario.crear_en_google(para_calendario(ev), enviar=False)

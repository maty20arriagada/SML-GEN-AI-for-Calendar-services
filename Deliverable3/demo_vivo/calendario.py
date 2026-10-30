"""
calendario.py - Lleva el JSON del modelo (contrato de 9 campos) a Outlook o Google Calendar.

Uso:
  python calendario.py <id_frase>    -> muestra los payloads de Graph y Google y escribe
                                        evento_<id>.ics a partir del ground truth de frases.json

Funciones:
  a_evento_graph(evento)                     -> payload para POST /me/calendars/{id}/events (Outlook)
  a_evento_google(evento)                    -> payload para POST /calendars/{id}/events (Google)
  a_ics(evento)                              -> mismo evento como texto iCalendar (respaldo)
  crear_en_outlook(evento, client_id, ...)   -> login (device code) + creacion en Outlook
  crear_en_google(evento, credenciales, ...) -> login (link + pegar URL) + creacion en Google

Decisiones de diseño:
  - Sin duracion_minutos se usa DURACION_DEFECTO (el calendario exige hora de termino).
  - Los participantes van en la descripcion del evento, no como invitados: la API exige
    correos y enviaria invitaciones reales.
  - Los eventos se crean en un calendario aparte llamado CALENDARIO.
"""

import json
import os
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DURACION_DEFECTO = 30
CALENDARIO = "CalendarBot"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite"]

GOOGLE_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_REDIRECT = "http://localhost"
# solo calendarios creados por la app + ver la lista para no duplicar CALENDARIO
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

# IANA -> nombre Windows que usa Outlook
ZONAS_WINDOWS = {
    "America/Santiago": "Pacific SA Standard Time",
    "Europe/Madrid": "Romance Standard Time",
    "America/Argentina/Buenos_Aires": "Argentina Standard Time",
    "America/Lima": "SA Pacific Standard Time",
    "America/Bogota": "SA Pacific Standard Time",
    "America/Mexico_City": "Central Standard Time (Mexico)",
    "America/New_York": "Eastern Standard Time",
    "America/Los_Angeles": "Pacific Standard Time",
    "Europe/London": "GMT Standard Time",
    "UTC": "UTC",
}

DIAS_ICS = {
    "monday": "MO", "tuesday": "TU", "wednesday": "WE", "thursday": "TH",
    "friday": "FR", "saturday": "SA", "sunday": "SU",
}
DIAS_SEMANA = list(DIAS_ICS)  # indice = datetime.weekday()

# Chile: horario de verano desde el primer domingo de septiembre hasta el primer domingo de abril
VTIMEZONE_SANTIAGO = """BEGIN:VTIMEZONE
TZID:America/Santiago
BEGIN:STANDARD
DTSTART:19700405T000000
TZOFFSETFROM:-0300
TZOFFSETTO:-0400
RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19700906T000000
TZOFFSETFROM:-0400
TZOFFSETTO:-0300
RRULE:FREQ=YEARLY;BYMONTH=9;BYDAY=1SU
END:DAYLIGHT
END:VTIMEZONE"""


def _inicio_fin(evento):
    if not isinstance(evento, dict) or "error" in evento:
        raise ValueError("el modelo no entrego un evento valido")
    if not evento.get("fecha") or not evento.get("hora_inicio"):
        raise ValueError("falta fecha/hora: no se puede crear el evento")
    inicio = datetime.strptime(f"{evento['fecha']} {evento['hora_inicio']}", "%Y-%m-%d %H:%M")
    duracion = evento.get("duracion_minutos") or DURACION_DEFECTO
    return inicio, inicio + timedelta(minutes=int(duracion))


def _recurrencia(evento):
    return evento.get("recurrencia", evento.get("recurrence"))


def _dias_recurrencia(rec, inicio):
    return [d.lower() for d in (rec.get("dias") or [])] or [DIAS_SEMANA[inicio.weekday()]]


def _cuerpo(evento):
    participantes = evento.get("participantes") or []
    return f"Participantes: {', '.join(participantes)}" if participantes else ""


def a_evento_graph(evento):
    """JSON del contrato -> payload de Microsoft Graph (recurso event)."""
    inicio, fin = _inicio_fin(evento)
    zona = ZONAS_WINDOWS.get(evento.get("zona_horaria") or "America/Santiago", "UTC")
    fmt = "%Y-%m-%dT%H:%M:00"

    payload = {
        "subject": evento.get("titulo") or "Reunión",
        "start": {"dateTime": inicio.strftime(fmt), "timeZone": zona},
        "end": {"dateTime": fin.strftime(fmt), "timeZone": zona},
        "isReminderOn": evento.get("recordatorio_minutos") is not None,
    }
    if evento.get("recordatorio_minutos") is not None:
        payload["reminderMinutesBeforeStart"] = int(evento["recordatorio_minutos"])
    if evento.get("ubicacion"):
        payload["location"] = {"displayName": evento["ubicacion"]}
    if _cuerpo(evento):
        payload["body"] = {"contentType": "text", "content": _cuerpo(evento)}

    rec = _recurrencia(evento)
    if rec:
        frecuencia = rec.get("frecuencia", "weekly")
        patron = {"interval": int(rec.get("intervalo") or 1)}
        if frecuencia == "daily":
            patron["type"] = "daily"
        elif frecuencia == "monthly":
            patron.update(type="absoluteMonthly", dayOfMonth=inicio.day)
        else:
            patron.update(type="weekly", daysOfWeek=_dias_recurrencia(rec, inicio))
        rango = {"startDate": evento["fecha"]}
        if rec.get("hasta"):
            rango.update(type="endDate", endDate=rec["hasta"])
        elif rec.get("veces"):
            rango.update(type="numbered", numberOfOccurrences=int(rec["veces"]))
        else:
            rango["type"] = "noEnd"
        payload["recurrence"] = {"pattern": patron, "range": rango}

    return payload


def _escapar_ics(texto):
    return (str(texto).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _rrule(rec, inicio, tzid):
    """Recurrencia del contrato -> regla RRULE (RFC 5545), la usan .ics y Google."""
    frecuencia = rec.get("frecuencia", "weekly")
    regla = f"FREQ={frecuencia.upper()};INTERVAL={int(rec.get('intervalo') or 1)}"
    if frecuencia == "weekly":
        regla += ";BYDAY=" + ",".join(DIAS_ICS[d] for d in _dias_recurrencia(rec, inicio))
    if rec.get("hasta"):
        # con zona horaria el estandar exige UNTIL en UTC: fin del dia local (Chile = UTC-4 como maximo)
        desfase = 4 if tzid == "America/Santiago" else 0
        hasta = datetime.strptime(rec["hasta"], "%Y-%m-%d") + timedelta(hours=23 + desfase, minutes=59, seconds=59)
        regla += f";UNTIL={hasta.strftime('%Y%m%dT%H%M%S')}Z"
    elif rec.get("veces"):
        regla += f";COUNT={int(rec['veces'])}"
    return regla


def a_evento_google(evento):
    """JSON del contrato -> payload de Google Calendar (recurso Event). Google acepta zonas IANA."""
    inicio, fin = _inicio_fin(evento)
    zona = evento.get("zona_horaria") or "America/Santiago"
    fmt = "%Y-%m-%dT%H:%M:00"

    recordatorio = evento.get("recordatorio_minutos")
    payload = {
        "summary": evento.get("titulo") or "Reunión",
        "start": {"dateTime": inicio.strftime(fmt), "timeZone": zona},
        "end": {"dateTime": fin.strftime(fmt), "timeZone": zona},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": int(recordatorio)}] if recordatorio is not None else [],
        },
    }
    if evento.get("ubicacion"):
        payload["location"] = evento["ubicacion"]
    if _cuerpo(evento):
        payload["description"] = _cuerpo(evento)
    rec = _recurrencia(evento)
    if rec:
        payload["recurrence"] = [f"RRULE:{_rrule(rec, inicio, zona)}"]
    return payload


def a_ics(evento):
    """JSON del contrato -> texto iCalendar (.ics) que Outlook importa con doble clic."""
    inicio, fin = _inicio_fin(evento)
    tzid = evento.get("zona_horaria") or "America/Santiago"
    fmt = "%Y%m%dT%H%M%S"

    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CalendarBot//UdeC GAI//ES", "CALSCALE:GREGORIAN"]
    if tzid == "America/Santiago":
        lineas.append(VTIMEZONE_SANTIAGO)
    lineas += [
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@calendarbot",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}Z",
        f"DTSTART;TZID={tzid}:{inicio.strftime(fmt)}",
        f"DTEND;TZID={tzid}:{fin.strftime(fmt)}",
        f"SUMMARY:{_escapar_ics(evento.get('titulo') or 'Reunión')}",
    ]
    if evento.get("ubicacion"):
        lineas.append(f"LOCATION:{_escapar_ics(evento['ubicacion'])}")
    if _cuerpo(evento):
        lineas.append(f"DESCRIPTION:{_escapar_ics(_cuerpo(evento))}")

    rec = _recurrencia(evento)
    if rec:
        lineas.append(f"RRULE:{_rrule(rec, inicio, tzid)}")

    if evento.get("recordatorio_minutos") is not None:
        lineas += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Recordatorio",
                   f"TRIGGER:-PT{int(evento['recordatorio_minutos'])}M", "END:VALARM"]
    lineas += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join("\r\n".join(l.split("\n")) for l in lineas) + "\r\n"


_TOKENS = {}


def _token(client_id, tenant):
    """Login con device code flow: imprime un codigo para pegar en microsoft.com/devicelogin."""
    if (client_id, tenant) in _TOKENS:
        return _TOKENS[(client_id, tenant)]
    import msal
    app = msal.PublicClientApplication(client_id, authority=f"https://login.microsoftonline.com/{tenant}")
    flujo = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flujo:
        raise RuntimeError(flujo.get("error_description", flujo))
    print(flujo["message"])
    res = app.acquire_token_by_device_flow(flujo)
    if "access_token" not in res:
        raise RuntimeError(res.get("error_description", res))
    _TOKENS[(client_id, tenant)] = res["access_token"]
    return res["access_token"]


def _pedir(metodo, url, token=None, cuerpo=None, formulario=None):
    """HTTP con stdlib: cuerpo JSON o formulario; devuelve la respuesta JSON."""
    headers = {}
    datos = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif formulario is not None:
        datos = urllib.parse.urlencode(formulario).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=datos, method=metodo, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} en {url}: {e.read().decode('utf-8', 'replace')}") from e


def _graph(metodo, ruta, token, cuerpo=None):
    return _pedir(metodo, f"{GRAPH_URL}{ruta}", token, cuerpo)


def _respaldo_ics(evento, error, payload, destino):
    ruta = f"evento_{uuid.uuid4().hex[:8]}.ics"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(a_ics(evento))
    print(f"[AVISO] No se pudo crear en {destino} ({error}). Respaldo: {ruta}")
    return {"ics": ruta, "error": str(error), "payload": payload}


def _id_calendario(token):
    for cal in _graph("GET", "/me/calendars?$top=100", token)["value"]:
        if cal["name"] == CALENDARIO:
            return cal["id"]
    return _graph("POST", "/me/calendars", token, {"name": CALENDARIO})["id"]


def crear_en_outlook(evento, client_id=None, tenant=None, enviar=False):
    """
    Crea el evento en el calendario CALENDARIO de Outlook.
    enviar=False solo muestra el payload. Si falla el login o Graph, escribe un .ics de respaldo.
    """
    payload = a_evento_graph(evento)  # sin fecha/hora falla aqui: no hay respaldo posible
    if not enviar:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return {"payload": payload}

    client_id = client_id or os.environ.get("CALENDARBOT_CLIENT_ID")
    tenant = tenant or os.environ.get("CALENDARBOT_TENANT", "consumers")
    try:
        if not client_id:
            raise RuntimeError("falta client_id (variable CALENDARBOT_CLIENT_ID)")
        token = _token(client_id, tenant)
        creado = _graph("POST", f"/me/calendars/{_id_calendario(token)}/events", token, payload)
        print(f"Evento creado en Outlook: {creado['webLink']}")
        return {"id": creado["id"], "webLink": creado["webLink"], "payload": payload}
    except Exception as e:
        return _respaldo_ics(evento, e, payload, "Outlook")


def _token_google(credenciales, ruta_token):
    """
    Login OAuth de Google para app de escritorio. El device flow de Google no admite scopes de
    Calendar, asi que se abre un link, se autoriza y se pega la URL de localhost a la que
    redirige el navegador. El refresh_token queda en ruta_token para no repetir el login
    (en modo prueba de Google vence a los 7 dias; entonces se pide login de nuevo).
    """
    with open(credenciales, "r", encoding="utf-8") as f:
        cliente = json.load(f)["installed"]  # credentials.json de un cliente "Desktop app"
    base = {"client_id": cliente["client_id"], "client_secret": cliente["client_secret"]}

    if os.path.exists(ruta_token):
        with open(ruta_token, "r", encoding="utf-8") as f:
            refresh = json.load(f).get("refresh_token")
        if refresh:
            try:
                res = _pedir("POST", cliente["token_uri"], formulario={
                    **base, "refresh_token": refresh, "grant_type": "refresh_token"})
                return res["access_token"]
            except RuntimeError as e:
                print(f"[AVISO] Token guardado no sirve ({e}); se pide login de nuevo.")

    url = cliente["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": cliente["client_id"], "redirect_uri": GOOGLE_REDIRECT, "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES), "access_type": "offline", "prompt": "consent"})
    print("1. Abre este link e inicia sesion con tu cuenta Google:\n" + url)
    print("2. Al final el navegador muestra una pagina que no carga (localhost).")
    print("   Copia la direccion completa de la barra y pegala aqui.")
    pegado = input("URL: ").strip()
    codigo = urllib.parse.parse_qs(urllib.parse.urlparse(pegado).query).get("code", [pegado])[0]
    res = _pedir("POST", cliente["token_uri"], formulario={
        **base, "code": codigo, "redirect_uri": GOOGLE_REDIRECT, "grant_type": "authorization_code"})
    if res.get("refresh_token"):
        with open(ruta_token, "w", encoding="utf-8") as f:
            json.dump({"refresh_token": res["refresh_token"]}, f)
    return res["access_token"]


def _id_calendario_google(token):
    for cal in _pedir("GET", f"{GOOGLE_API}/users/me/calendarList", token).get("items", []):
        if cal.get("summary") == CALENDARIO:
            return cal["id"]
    return _pedir("POST", f"{GOOGLE_API}/calendars", token,
                  {"summary": CALENDARIO, "timeZone": "America/Santiago"})["id"]


def crear_en_google(evento, credenciales="credentials.json", ruta_token="token_google.json", enviar=False):
    """
    Crea el evento en el calendario CALENDARIO de Google Calendar.
    enviar=False solo muestra el payload. Si falla el login o la API, escribe un .ics de respaldo.
    """
    payload = a_evento_google(evento)  # sin fecha/hora falla aqui: no hay respaldo posible
    if not enviar:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return {"payload": payload}

    try:
        token = _token_google(credenciales, ruta_token)
        id_cal = urllib.parse.quote(_id_calendario_google(token), safe="")
        creado = _pedir("POST", f"{GOOGLE_API}/calendars/{id_cal}/events", token, payload)
        print(f"Evento creado en Google Calendar: {creado['htmlLink']}")
        return {"id": creado["id"], "htmlLink": creado["htmlLink"], "payload": payload}
    except Exception as e:
        return _respaldo_ics(evento, e, payload, "Google Calendar")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    with open(os.path.join(SCRIPT_DIR, "frases.json"), "r", encoding="utf-8") as f:
        frases = {fr["id"]: fr for fr in json.load(f)["frases"]}
    frase = frases[int(sys.argv[1])]
    print(frase["texto"])
    print("\n--- Outlook (Graph) ---")
    crear_en_outlook(frase["ground_truth"])
    print("\n--- Google Calendar ---")
    crear_en_google(frase["ground_truth"])
    ruta = f"evento_{frase['id']}.ics"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(a_ics(frase["ground_truth"]))
    print(f"Escrito: {ruta}")

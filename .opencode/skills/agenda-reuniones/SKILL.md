---
name: agenda-reuniones
description: Lee frases en español para agendar reuniones y eventos, extrae fecha y hora en America/Santiago y crea el evento en Google Calendar. Use ONLY when agendar, calendar, reunión, evento, cita, calendario.
---

# Agenda Reuniones

Optimizada para Qwen3-4B-Instruct-2507 (4B, contexto 256K, solo non-thinking). Instrucciones cortas y deterministas.

## Qué hago

- Entrada: frase libre en español con intención de agendar.
- Salida: evento creado en Google Calendar + confirmación corta.
- Zona horaria fija: `America/Santiago`. Nunca usar offset fijo.

## Cuándo usarme

Usar cuando el usuario pide agendar, calendar, reunión, evento, cita, calendario.
No usar para buscar, leer correos o tareas generales.

## Pasos (seguir en orden)

1. Extraer `titulo` y expresión temporal de la frase.
2. Normalizar a ISO-8601 con `timeZone: America/Santiago`.
   Usar fecha actual del sistema como referencia para "mañana", "próximo lunes", "en 2 horas".
3. Si falta hora, fecha o duración: hacer 1 pregunta aclaratoria. No adivinar. Default duración 60 min solo si el usuario confirma.
4. Verificar calendario con `list_calendars`. Usar `primary` si no se indica otro.
5. Opcional: usar `suggest_time` o `search_events` / `list_events` para evitar duplicados si la frase es ambigua.
6. Crear con `create_event` usando este JSON exacto:
   ```json
   {
     "calendarId": "primary",
     "summary": "título",
     "start": { "dateTime": "2026-09-26T15:00:00", "timeZone": "America/Santiago" },
     "end": { "dateTime": "2026-09-26T16:00:00", "timeZone": "America/Santiago" },
     "description": "frase original"
   }
   ```
7. Confirmar en 1 línea: título + fecha/hora Chile + ID del evento.

## Ejemplos Chile

Entrada: "Reunión con Ana mañana a las 3pm"
-> `summary: Reunión con Ana`, `start: mañana 15:00 America/Santiago`, `end: +60min`

Entrada: "Evento equipo próximo lunes 10am 1h"
-> `summary: Evento equipo`, `start: próximo lunes 10:00`, `end: 11:00`, `timeZone: America/Santiago`

Entrada: "Almuerzo pasado mañana 13:00"
-> Preguntar duración si no está. No asumir lugar.

## Reglas anti-alucinación para 4B

- No inventar año, hora o calendario. Si falta, preguntar.
- "mañana", "próximo", "en 2 horas" siempre se calculan desde hoy, nunca desde memoria.
- Chile alterna UTC-3 verano / UTC-4 invierno. Por eso siempre enviar `timeZone: America/Santiago`, nunca `-03:00` fijo.
- 1 herramienta por turno. No encadenar `search` + `create` en el mismo paso.
- Si `create_event` falla con auth, decir: "Falta autenticar Google Calendar. Ejecuta `opencode mcp auth google-calendar`".
- Responder en español, formato 24h + fecha ISO en confirmación.

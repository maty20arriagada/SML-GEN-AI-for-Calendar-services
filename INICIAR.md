# Inicializar agenda-reuniones (Qwen3-4B + Chile + Google Calendar)

Modelo: `huggingface/Qwen/Qwen3-4B-Instruct-2507` (`Qwen/Qwen3-4B-Instruct-2507` en HF).
Skill: `.opencode/skills/agenda-reuniones/SKILL.md`. Zona: `America/Santiago`.

## 1. Hugging Face (manual, 1 min)

```bash
# Opción A: TUI (recomendado)
opencode
# dentro: /connect -> Hugging Face -> pegar token con permiso inference.serverless.write
# luego: /models -> verificar que aparece Qwen/Qwen3-4B-Instruct-2507
```

Si el picker muestra otro slug, edita `opencode.json` -> `model` y `small_model`.

## 2. Google Calendar (manual, browser)

Pre-requisito en https://console.cloud.google.com/:
1. Crear proyecto, activar `Google Calendar API`.
2. Crear `OAuth Client ID` tipo `Desktop app`, copiar ID y Secret a tu `.env`.

```bash
cp .env.example .env
# edita .env con tus valores

opencode mcp auth google-calendar
opencode mcp list
opencode mcp debug google-calendar
```

## 3. Validación automática

```bash
./init-check.sh
```

## 4. Reiniciar y probar

1. Sal y reinicia `opencode` (la config no hace hot-reload).
2. Prueba: `agenda reunión con Ana mañana a las 15:00`
3. Debe listar y cargar `skill({name: "agenda-reuniones"})` y llamar `list_calendars` -> `create_event` con `timeZone: America/Santiago`.

Si `create_event` da 401: ejecuta `opencode mcp auth google-calendar` de nuevo.

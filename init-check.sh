#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "== 1. opencode.json =="
python3 -c "import json,pathlib; d=json.loads(pathlib.Path('opencode.json').read_text()); assert d['model'].startswith('huggingface/'), 'model debe ser huggingface/...'; assert 'google-calendar' in d.get('mcp',{}), 'falta mcp google-calendar'; print('OK model:', d['model']); print('OK mcp:', d['mcp']['google-calendar'].get('url'))"

echo "== 2. SKILL.md =="
python3 -c "
import re,pathlib
s=pathlib.Path('.opencode/skills/agenda-reuniones/SKILL.md').read_text()
m=re.match(r'^---\n(.*?)\n---\n', s, re.S)
assert m, 'falta frontmatter'
fm=m.group(1)
name=re.search(r'name:\s*(.+)', fm).group(1).strip()
desc=re.search(r'description:\s*(.+)', fm).group(1).strip()
assert name=='agenda-reuniones', f'name={name} debe ser agenda-reuniones'
assert re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name), 'name regex invalido'
assert 1 <= len(desc) <= 1024, 'description 1-1024 chars'
assert 'America/Santiago' in s, 'falta America/Santiago'
assert 'create_event' in s, 'falta create_event'
print(f'OK skill name={name} desc_len={len(desc)}')
"

echo "== 3. .env.example =="
test -f .env.example && echo "OK .env.example existe" || (echo "FALTA .env.example"; exit 1)

echo "== 4. opencode binario =="
if command -v opencode >/dev/null 2>&1; then
  echo "OK opencode encontrado: $(command -v opencode)"
  echo "-- sugerido (requiere tu login): opencode mcp auth google-calendar"
else
  echo "AVISO: opencode no está en PATH. Instálalo y luego corre: opencode mcp auth google-calendar"
fi

echo "TODO LISTO. Siguiente: cp .env.example .env, auth manual, reiniciar opencode."

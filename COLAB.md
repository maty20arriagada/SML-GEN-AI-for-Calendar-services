# Uso en Colab (privado)

## 1. Secrets (una vez)

Colab → 🔑 Secrets:
- `HF_TOKEN` = `hf_...` (Read)
- `GITHUB_PAT` = `ghp_...` (scope `repo`)

## 2. Abrir notebook

UI: Abrir → GitHub → autoriza → `notebooks/agenda_colab.ipynb`.
O clona: la celda 2 clona con PAT si no detecta `SKILL.md`.

## 3. Calendar token (una vez en local)

```bash
cp .env.example .env  # completa GOOGLE_CLIENT_ID/SECRET
pip install google-auth-oauthlib
python scripts/get_google_token.py
# sube token.json a Drive raíz (/MyDrive/token.json)
```

## 4. Correr

Celdas en orden: install → skill → parse Qwen (`Qwen/Qwen3-4B-Instruct-2507`) → normalizar `America/Santiago` → crear evento `primary`.

Test: `Reunión con Ana mañana a las 15:00`.

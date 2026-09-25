"""Genera token.json una vez en local para reusar en Colab sin browser.

Uso:
  cp .env.example .env  # completa GOOGLE_CLIENT_ID / SECRET
  pip install google-auth-oauthlib
  python scripts/get_google_token.py
  # sube token.json a Google Drive para que Colab lo lea
"""
import json
import os
import pathlib

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
OUT = pathlib.Path("token.json")

client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
if not client_id or not client_secret:
    # intenta leer .env simple sin dependencias
    env_path = pathlib.Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GOOGLE_CLIENT_ID="):
                client_id = line.split("=", 1)[1].strip()
            if line.startswith("GOOGLE_CLIENT_SECRET="):
                client_secret = line.split("=", 1)[1].strip()

assert client_id and client_secret, "Falta GOOGLE_CLIENT_ID/SECRET en env o .env"

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    SCOPES,
)
creds = flow.run_local_server(port=0)
OUT.write_text(creds.to_json())
print(f"OK -> {OUT.resolve()} súbelo a Drive para Colab")

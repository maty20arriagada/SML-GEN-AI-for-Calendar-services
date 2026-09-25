# Push limpio desde PowerShell (carpeta fuera de OneDrive)

Esta carpeta `C:\GENIA\D2-clean` reemplaza a `OneDrive\Escritorio\GENIA\D2`
para evitar bloqueos de OneDrive en `git rebase`.

Nuestros archivos ya están aquí exportados del commit `f388db0`.

## Pasos (en PowerShell)

```powershell
cd C:\GENIA\D2-clean
git init
git branch -M main
git add .gitattributes .opencode opencode.json notebooks requirements-colab.txt scripts README.md COLAB.md INICIAR.md .env.example init-check.sh PUSH-GUIA.md
git commit -m "skill agenda + colab Qwen 4B Chile (carpeta limpia)"
git remote add origin https://github.com/maty20arriagada/SML-GEN-AI-for-Calendar-services.git
git fetch origin
```

Si `fetch` pide login, completa la autenticación en el browser.

```powershell
# El remoto ya tiene 62 objetos (README/LICENSE inicial). Intégralos:
git rebase origin/main
# Si hay conflicto en README.md: ábrelo, deja ambas partes,
# git add .  +  git rebase --continue
git push -u origin main
```

Fuera de OneDrive el `rebase` ya no da `Deletion failed`.

## Seguir con token + Colab

```powershell
Copy-Item .env.example .env
# edita .env, luego:
python scripts/get_google_token.py
```

Sube `token.json` a Drive y abre el notebook en Colab.

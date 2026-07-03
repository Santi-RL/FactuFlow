$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$backendCmd = @'
Set-Location "{0}\backend"
if (!(Test-Path ".venv")) {{
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
}} else {{
  .\.venv\Scripts\activate
}}
if (!(Test-Path "data")) {{
  New-Item -ItemType Directory -Path "data" | Out-Null
}}
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
'@ -f $root

$frontendCmd = @'
Set-Location "{0}\frontend"
$env:VITE_API_URL = "http://127.0.0.1:8000"
if (!(Test-Path "node_modules")) {{
  npm install
}}
npm run dev -- --host 127.0.0.1 --port 8080
'@ -f $root

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

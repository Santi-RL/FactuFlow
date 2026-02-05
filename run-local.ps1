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
uvicorn app.main:app --reload --port 8000
'@ -f $root

$frontendCmd = @'
Set-Location "{0}\frontend"
if (!(Test-Path "node_modules")) {{
  npm install
}}
npm run dev
'@ -f $root

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

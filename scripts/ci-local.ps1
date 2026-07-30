$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$logDir = Join-Path $root ".tmp"
$logPath = Join-Path $logDir "ci-local.log"

if (!(Test-Path $logDir)) {
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

# Overwrite previous log on every run (Unicode for Windows PS compatibility)
Set-Content -Path $logPath -Value "" -Encoding Unicode

$script:results = @()
$script:groups = @{
  "Repository" = New-Object System.Collections.ArrayList
  "Backend"    = New-Object System.Collections.ArrayList
  "Frontend" = New-Object System.Collections.ArrayList
  "E2E"      = New-Object System.Collections.ArrayList
  "Security" = New-Object System.Collections.ArrayList
}

function Write-Log($message) {
  $line = $message
  Write-Host $line
  Add-Content -Path $logPath -Value $line -Encoding Unicode
}

function Write-Section($title) {
  Write-Log ""
  Write-Log ("=" * 80)
  Write-Log $title
  Write-Log ("=" * 80)
}

function Invoke-Step($label, [scriptblock]$block, [switch]$WarnOnly) {
  Write-Section $label
  $exitCode = 0
  try {
    & $block 2>&1 | ForEach-Object {
      $text = $_.ToString()
      if ($text -ne "") {
        $text -split "`r?`n" | ForEach-Object {
          if ($_ -ne "") {
            Write-Log $_
          }
        }
      }
    }
    $exitCode = $LASTEXITCODE
  } catch {
    $exitCode = 1
    Write-Log "ERROR: $label threw an exception: $($_.Exception.Message)"
  }

  $status = ""
  if ($exitCode -eq 0) {
    $script:results += [pscustomobject]@{ Step = $label; Status = "OK"; ExitCode = 0 }
    $status = "OK"
  } elseif ($WarnOnly) {
    Write-Log "WARN: $label failed with exit code $exitCode (ignored)."
    $script:results += [pscustomobject]@{ Step = $label; Status = "WARN"; ExitCode = $exitCode }
    $status = "WARN"
  } else {
    Write-Log "FAIL: $label failed with exit code $exitCode."
    $script:results += [pscustomobject]@{ Step = $label; Status = "FAIL"; ExitCode = $exitCode }
    $status = "FAIL"
  }

  # Group mapping for summary
  $group =
    if ($label -like "Repository:*") { "Repository" }
    elseif ($label -like "Backend:*") { "Backend" }
    elseif ($label -like "Frontend: E2E*") { "E2E" }
    elseif ($label -like "Frontend:*") { "Frontend" }
    elseif ($label -like "Security:*") { "Security" }
    else { "Otros" }

  if (-not $script:groups.ContainsKey($group)) {
    $script:groups[$group] = New-Object System.Collections.ArrayList
  }
  [void]$script:groups[$group].Add($status)
}

function Write-Summary {
  Write-Section "Resumen"
  $script:results | ForEach-Object {
    Write-Log ("{0,-6} {1}" -f $_.Status, $_.Step)
  }
  Write-Log ""
  $failures = @($script:results | Where-Object { $_.Status -eq "FAIL" })
  $warnings = @($script:results | Where-Object { $_.Status -eq "WARN" })

  $groupOrder = @("Repository", "Backend", "Frontend", "E2E", "Security")
  foreach ($groupName in $groupOrder) {
    $statuses = $script:groups[$groupName]
    if (-not $statuses -or $statuses.Count -eq 0) {
      Write-Log ("{0,-9} SIN DATOS" -f $groupName)
      continue
    }
    $groupStatus =
      if ($statuses -contains "FAIL") { "FAIL" }
      elseif ($statuses -contains "WARN") { "WARN" }
      else { "OK" }
    Write-Log ("{0,-9} {1}" -f $groupName, $groupStatus)
  }

  Write-Log ""
  Write-Log ("FAILURES: {0} | WARNINGS: {1}" -f $failures.Count, $warnings.Count)
}

# -----------------------------
# Repository scripts
# -----------------------------
Push-Location $root
Invoke-Step "Repository: documentation alignment" { npm run docs:check }
Invoke-Step "Repository: package script tests" { npm run test:scripts }
Invoke-Step "Repository: Clawpatch seed tests" { npm run clawpatch:test-seeds }
Pop-Location

# -----------------------------
# Backend
# -----------------------------
Push-Location (Join-Path $root "backend")

$python = if (Test-Path ".\\.venv\\Scripts\\python.exe") { ".\\.venv\\Scripts\\python.exe" } else { "python" }

Invoke-Step "Backend: upgrade pip" { & $python -m pip install --upgrade pip }
Invoke-Step "Backend: install requirements" { & $python -m pip install -r requirements.txt }
Invoke-Step "Backend: install dev requirements" { & $python -m pip install -r requirements-dev.txt }
Invoke-Step "Backend: ruff" { & $python -m ruff check app/ tests/ }
Invoke-Step "Backend: black --check" { & $python -m black --check app/ tests/ }
Invoke-Step "Backend: pytest" { & $python -m pytest tests/ -v --cov=app --cov-report=xml }

Pop-Location

# -----------------------------
# Frontend
# -----------------------------
Push-Location (Join-Path $root "frontend")

Invoke-Step "Frontend: npm ci" { npm ci }
Invoke-Step "Frontend: type-check" { npm run type-check }
Invoke-Step "Frontend: lint" { npm run lint }
Invoke-Step "Frontend: build" { npm run build }
Invoke-Step "Frontend: unit tests" { npm run test:unit }

# E2E (Chromium only)
if ($IsWindows) {
  Invoke-Step "Frontend: install Playwright Chromium" { npx playwright install chromium }
} else {
  Invoke-Step "Frontend: install Playwright Chromium" { npx playwright install --with-deps chromium }
}
Invoke-Step "Frontend: E2E (Chromium)" { npm run test:e2e -- --project=chromium }

Pop-Location

# -----------------------------
# Security (blocking, igual que GitHub Actions)
# -----------------------------
Push-Location (Join-Path $root "backend")
Invoke-Step "Security: install pip-audit" { & $python -m pip install --upgrade pip setuptools wheel; & $python -m pip install pip-audit }
Invoke-Step "Security: pip-audit producción" { & $python -m pip_audit -r requirements.txt }
Pop-Location

Push-Location (Join-Path $root "frontend")
Invoke-Step "Security: npm audit producción (high)" { npm audit --omit=dev --audit-level=high }
Pop-Location

Write-Summary

$hasFailures = $script:results | Where-Object { $_.Status -eq "FAIL" }
if ($hasFailures.Count -gt 0) {
  exit 1
}

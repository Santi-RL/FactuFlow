param([switch]$SelfTest)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class FactuFlowNativeMethods
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool DestroyIcon(IntPtr hIcon);
}
"@

$script:RootDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$script:BackendDir = Join-Path $script:RootDir "backend"
$script:FrontendDir = Join-Path $script:RootDir "frontend"
$script:LogDir = Join-Path $script:RootDir ".tmp\local-launcher"
$script:LauncherLog = Join-Path $script:LogDir "launcher.log"
$script:BackendLog = Join-Path $script:LogDir "backend.log"
$script:FrontendLog = Join-Path $script:LogDir "frontend.log"
$script:BackendRunner = Join-Path $script:LogDir "backend-runner.ps1"
$script:FrontendRunner = Join-Path $script:LogDir "frontend-runner.ps1"
$script:BackendUrl = "http://localhost:8000"
$script:FrontendUrl = "http://localhost:8080"
$script:BackendProcess = $null
$script:FrontendProcess = $null
$script:CurrentState = "starting"
$script:CurrentMessage = "Iniciando FactuFlow"
$script:BrowserOpened = $false
$script:FailureNotified = $false
$script:ManualStopped = $false
$script:LastBlockingError = $null
$script:TrayIconHandle = $null
$script:Mutex = $null
$script:CreatedMutex = $false

New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null

function Write-LauncherLog {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $script:LauncherLog -Value "[$timestamp] $Message"
}

function ConvertTo-PowerShellLiteral {
    param([string]$Value)

    return "'" + ($Value -replace "'", "''") + "'"
}

function Test-CommandAvailable {
    param([string]$Name)

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PortOpen {
    param(
        [int]$Port,
        [int]$TimeoutMs = 800
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $asyncResult = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $success = $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $success) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Invoke-HttpCheck {
    param(
        [string]$Url,
        [int]$TimeoutSec = 3
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return [pscustomobject]@{
            Ok = $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
            Content = [string]$response.Content
            Error = $null
        }
    } catch {
        return [pscustomobject]@{
            Ok = $false
            Content = ""
            Error = $_.Exception.Message
        }
    }
}

function Test-BackendHealth {
    $check = Invoke-HttpCheck -Url "$script:BackendUrl/api/health"
    return $check.Ok -and $check.Content -like "*FactuFlow API*"
}

function Test-BackendDbHealth {
    $check = Invoke-HttpCheck -Url "$script:BackendUrl/api/health/db"
    return $check.Ok -and $check.Content -like "*base de datos OK*"
}

function Test-FrontendHealth {
    $check = Invoke-HttpCheck -Url $script:FrontendUrl
    return $check.Ok -and $check.Content -like "*FactuFlow*"
}

function Test-OwnedProcessRunning {
    param($Process)

    return $null -ne $Process -and -not $Process.HasExited
}

function New-StatusIcon {
    param(
        [System.Drawing.Color]$Color,
        [string]$Letter
    )

    $bitmap = New-Object System.Drawing.Bitmap 32, 32
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $brush = New-Object System.Drawing.SolidBrush $Color
    $textBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $font = New-Object System.Drawing.Font "Segoe UI", 14, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $format = New-Object System.Drawing.StringFormat

    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.FillEllipse($brush, 3, 3, 26, 26)
        $format.Alignment = [System.Drawing.StringAlignment]::Center
        $format.LineAlignment = [System.Drawing.StringAlignment]::Center
        $graphics.DrawString($Letter, $font, $textBrush, ([System.Drawing.RectangleF]::new(0, 0, 32, 30)), $format)

        $hIcon = $bitmap.GetHicon()
        $icon = [System.Drawing.Icon]::FromHandle($hIcon).Clone()
        [FactuFlowNativeMethods]::DestroyIcon($hIcon) | Out-Null
        return $icon
    } finally {
        $format.Dispose()
        $font.Dispose()
        $textBrush.Dispose()
        $brush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Set-TrayState {
    param(
        [ValidateSet("ready", "starting", "error")]
        [string]$State,
        [string]$Message
    )

    $script:CurrentState = $State
    $script:CurrentMessage = $Message

    if ($State -eq "ready") {
        $icon = New-StatusIcon -Color ([System.Drawing.Color]::FromArgb(32, 156, 86)) -Letter "F"
    } elseif ($State -eq "starting") {
        $icon = New-StatusIcon -Color ([System.Drawing.Color]::FromArgb(230, 160, 40)) -Letter "F"
    } else {
        $icon = New-StatusIcon -Color ([System.Drawing.Color]::FromArgb(210, 62, 62)) -Letter "F"
    }

    $oldIcon = $script:TrayIconHandle
    $script:TrayIconHandle = $icon
    $script:NotifyIcon.Icon = $icon
    $script:NotifyIcon.Text = $Message.Substring(0, [Math]::Min(63, $Message.Length))
    if ($null -ne $oldIcon) {
        $oldIcon.Dispose()
    }
}

function New-BackendRunnerScript {
    $backendDir = ConvertTo-PowerShellLiteral $script:BackendDir
    $backendLog = ConvertTo-PowerShellLiteral $script:BackendLog

    return @"
Set-StrictMode -Version 2.0
`$ErrorActionPreference = "Stop"
`$LogPath = $backendLog

function Write-RunLog {
    param([string]`$Message)
    `$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath `$LogPath -Value "[`$timestamp] `$Message"
}

function Invoke-Checked {
    param(
        [string]`$FilePath,
        [string[]]`$Arguments
    )

    Write-RunLog ("> " + `$FilePath + " " + (`$Arguments -join " "))
    `$previousErrorActionPreference = `$ErrorActionPreference
    `$ErrorActionPreference = "Continue"
    try {
        & `$FilePath @Arguments 2>&1 | ForEach-Object { Write-RunLog (`$_.ToString()) }
        `$exitCode = `$LASTEXITCODE
    } finally {
        `$ErrorActionPreference = `$previousErrorActionPreference
    }
    if (`$exitCode -ne 0) {
        throw "El comando fallo con codigo `$(`$exitCode`): `$FilePath"
    }
}

try {
    Write-RunLog "Iniciando backend local"
    Set-Location -LiteralPath $backendDir
    if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
        Invoke-Checked "python" @("-m", "venv", ".venv")
        Invoke-Checked ".\.venv\Scripts\python.exe" @("-m", "pip", "install", "-r", "requirements.txt")
        Invoke-Checked ".\.venv\Scripts\python.exe" @("-m", "pip", "install", "-r", "requirements-dev.txt")
    }
    if (-not (Test-Path -LiteralPath "data")) {
        New-Item -ItemType Directory -Path "data" | Out-Null
    }
    Invoke-Checked ".\.venv\Scripts\python.exe" @("-m", "alembic", "upgrade", "head")
    Write-RunLog "> .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
    `$previousErrorActionPreference = `$ErrorActionPreference
    `$ErrorActionPreference = "Continue"
    try {
        & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000 2>&1 | ForEach-Object { Write-RunLog (`$_.ToString()) }
        `$exitCode = `$LASTEXITCODE
    } finally {
        `$ErrorActionPreference = `$previousErrorActionPreference
    }
    if (`$exitCode -ne 0) {
        throw "uvicorn finalizo con codigo `$exitCode"
    }
} catch {
    Write-RunLog ("ERROR: " + `$_.Exception.Message)
    exit 1
}
"@
}

function New-FrontendRunnerScript {
    $frontendDir = ConvertTo-PowerShellLiteral $script:FrontendDir
    $frontendLog = ConvertTo-PowerShellLiteral $script:FrontendLog

    return @"
Set-StrictMode -Version 2.0
`$ErrorActionPreference = "Stop"
`$LogPath = $frontendLog

function Write-RunLog {
    param([string]`$Message)
    `$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath `$LogPath -Value "[`$timestamp] `$Message"
}

function Invoke-Checked {
    param(
        [string]`$FilePath,
        [string[]]`$Arguments
    )

    Write-RunLog ("> " + `$FilePath + " " + (`$Arguments -join " "))
    `$previousErrorActionPreference = `$ErrorActionPreference
    `$ErrorActionPreference = "Continue"
    try {
        & `$FilePath @Arguments 2>&1 | ForEach-Object { Write-RunLog (`$_.ToString()) }
        `$exitCode = `$LASTEXITCODE
    } finally {
        `$ErrorActionPreference = `$previousErrorActionPreference
    }
    if (`$exitCode -ne 0) {
        throw "El comando fallo con codigo `$(`$exitCode`): `$FilePath"
    }
}

try {
    Write-RunLog "Iniciando frontend local"
    Set-Location -LiteralPath $frontendDir
    if (-not (Test-Path -LiteralPath "node_modules")) {
        Invoke-Checked "npm" @("install")
    }
    Invoke-Checked "npm" @("run", "dev")
} catch {
    Write-RunLog ("ERROR: " + `$_.Exception.Message)
    exit 1
}
"@
}

function Start-HiddenRunner {
    param(
        [string]$Path,
        [string]$Content
    )

    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
    $powerShellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $commandLine = '"{0}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{1}"' -f $powerShellPath, $Path
    $startup = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
    $startup.ShowWindow = 0
    $processClass = [wmiclass]"Win32_Process"
    $result = $processClass.Create($commandLine, $null, $startup)
    if ($result.ReturnValue -ne 0) {
        throw "No se pudo iniciar el runner oculto. Codigo WMI: $($result.ReturnValue)"
    }
    return Get-Process -Id $result.ProcessId
}

function Start-BackendService {
    if (Test-OwnedProcessRunning $script:BackendProcess) {
        return
    }

    if (-not (Test-Path -LiteralPath (Join-Path $script:BackendDir ".venv\Scripts\python.exe")) -and -not (Test-CommandAvailable "python")) {
        $script:LastBlockingError = "Falta un componente necesario para iniciar FactuFlow"
        Set-TrayState -State "error" -Message "Falta un componente necesario para iniciar FactuFlow"
        Write-LauncherLog "No se encontro Python para crear el entorno backend."
        return
    }

    Write-LauncherLog "Iniciando backend local."
    $script:BackendProcess = Start-HiddenRunner -Path $script:BackendRunner -Content (New-BackendRunnerScript)
}

function Start-FrontendService {
    if (Test-OwnedProcessRunning $script:FrontendProcess) {
        return
    }

    if (-not (Test-CommandAvailable "npm")) {
        $script:LastBlockingError = "Falta un componente necesario para iniciar FactuFlow"
        Set-TrayState -State "error" -Message "Falta un componente necesario para iniciar FactuFlow"
        Write-LauncherLog "No se encontro npm para iniciar el frontend."
        return
    }

    Write-LauncherLog "Iniciando frontend local."
    $script:FrontendProcess = Start-HiddenRunner -Path $script:FrontendRunner -Content (New-FrontendRunnerScript)
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" | ForEach-Object {
            Stop-ProcessTree -ProcessId $_.ProcessId
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
        Write-LauncherLog ("No se pudo detener el proceso " + $ProcessId + ": " + $_.Exception.Message)
    }
}

function Stop-OwnedServices {
    $stopped = $false
    if (Test-OwnedProcessRunning $script:BackendProcess) {
        Write-LauncherLog "Deteniendo backend iniciado por launcher."
        Stop-ProcessTree -ProcessId $script:BackendProcess.Id
        $stopped = $true
    }
    if (Test-OwnedProcessRunning $script:FrontendProcess) {
        Write-LauncherLog "Deteniendo frontend iniciado por launcher."
        Stop-ProcessTree -ProcessId $script:FrontendProcess.Id
        $stopped = $true
    }
    $script:BackendProcess = $null
    $script:FrontendProcess = $null
    return $stopped
}

function Ensure-ServicesStarted {
    $script:ManualStopped = $false
    $script:LastBlockingError = $null
    Set-TrayState -State "starting" -Message "Preparando FactuFlow"

    $backendOk = Test-BackendHealth
    $backendPortOpen = Test-PortOpen -Port 8000
    if (-not $backendOk) {
        if ($backendPortOpen -and -not (Test-OwnedProcessRunning $script:BackendProcess)) {
            $script:LastBlockingError = "El puerto 8000 esta ocupado por otra aplicacion"
            Set-TrayState -State "error" -Message "El puerto 8000 esta ocupado por otra aplicacion"
            Write-LauncherLog "Puerto 8000 ocupado pero /api/health no responde como FactuFlow."
        } else {
            Start-BackendService
        }
    }

    $frontendOk = Test-FrontendHealth
    $frontendPortOpen = Test-PortOpen -Port 8080
    if (-not $frontendOk) {
        if ($frontendPortOpen -and -not (Test-OwnedProcessRunning $script:FrontendProcess)) {
            $script:LastBlockingError = "El puerto 8080 esta ocupado por otra aplicacion"
            Set-TrayState -State "error" -Message "El puerto 8080 esta ocupado por otra aplicacion"
            Write-LauncherLog "Puerto 8080 ocupado pero no responde como frontend FactuFlow."
        } else {
            Start-FrontendService
        }
    }
}

function Get-StatusSnapshot {
    $backendOk = Test-BackendHealth
    $dbOk = $false
    if ($backendOk) {
        $dbOk = Test-BackendDbHealth
    }
    $frontendOk = Test-FrontendHealth
    $backendPortOpen = Test-PortOpen -Port 8000
    $frontendPortOpen = Test-PortOpen -Port 8080

    return [pscustomobject]@{
        BackendOk = $backendOk
        DbOk = $dbOk
        FrontendOk = $frontendOk
        BackendPortOpen = $backendPortOpen
        FrontendPortOpen = $frontendPortOpen
        BackendOwnedRunning = Test-OwnedProcessRunning $script:BackendProcess
        FrontendOwnedRunning = Test-OwnedProcessRunning $script:FrontendProcess
    }
}

function Update-VisualStatus {
    $status = Get-StatusSnapshot

    if ($status.BackendOk -and $status.DbOk -and $status.FrontendOk) {
        $script:LastBlockingError = $null
        Set-TrayState -State "ready" -Message "FactuFlow listo"
        if (-not $script:BrowserOpened) {
            $script:BrowserOpened = $true
            Write-LauncherLog "FactuFlow listo. Abriendo navegador."
            Start-Process $script:FrontendUrl
        }
        return
    }

    if ($status.BackendPortOpen -and -not $status.BackendOk -and -not $status.BackendOwnedRunning) {
        $script:LastBlockingError = "El puerto 8000 esta ocupado por otra aplicacion"
        Set-TrayState -State "error" -Message "El puerto 8000 esta ocupado por otra aplicacion"
        return
    }

    if ($status.FrontendPortOpen -and -not $status.FrontendOk -and -not $status.FrontendOwnedRunning) {
        $script:LastBlockingError = "El puerto 8080 esta ocupado por otra aplicacion"
        Set-TrayState -State "error" -Message "El puerto 8080 esta ocupado por otra aplicacion"
        return
    }

    if ($null -ne $script:LastBlockingError) {
        Set-TrayState -State "error" -Message $script:LastBlockingError
        return
    }

    if ($script:ManualStopped -and -not $status.BackendOk -and -not $status.FrontendOk) {
        Set-TrayState -State "error" -Message "FactuFlow detenido"
        return
    }

    if ($status.BackendOk -and -not $status.DbOk) {
        $script:LastBlockingError = "FactuFlow requiere atencion"
        Set-TrayState -State "error" -Message "FactuFlow requiere atencion"
        if (-not $script:FailureNotified) {
            $script:FailureNotified = $true
            $script:NotifyIcon.ShowBalloonTip(5000, "FactuFlow", "No se pudo conectar con la base de datos. Revisa los logs o contacta soporte.", [System.Windows.Forms.ToolTipIcon]::Error)
        }
        return
    }

    $backendExited = $null -ne $script:BackendProcess -and $script:BackendProcess.HasExited
    $frontendExited = $null -ne $script:FrontendProcess -and $script:FrontendProcess.HasExited
    if ($backendExited -or $frontendExited) {
        $script:LastBlockingError = "FactuFlow requiere atencion"
        Set-TrayState -State "error" -Message "FactuFlow requiere atencion"
        if (-not $script:FailureNotified) {
            $script:FailureNotified = $true
            $script:NotifyIcon.ShowBalloonTip(5000, "FactuFlow", "No se pudo iniciar el servidor local. Revisa los logs o contacta soporte.", [System.Windows.Forms.ToolTipIcon]::Error)
        }
        return
    }

    Set-TrayState -State "starting" -Message "Iniciando FactuFlow"
}

function Show-SystemStatus {
    $status = Get-StatusSnapshot
    $backendText = if ($status.BackendOk) { "OK" } elseif ($status.BackendOwnedRunning) { "Iniciando" } else { "Detenido o con error" }
    $dbText = if ($status.DbOk) { "OK" } elseif ($status.BackendOk) { "Error" } else { "Sin verificar" }
    $frontendText = if ($status.FrontendOk) { "OK" } elseif ($status.FrontendOwnedRunning) { "Iniciando" } else { "Detenido o con error" }
    $message = @"
Estado actual: $script:CurrentMessage

Backend: $backendText
Base de datos: $dbText
Frontend: $frontendText

Logs:
$script:LogDir
"@
    [System.Windows.Forms.MessageBox]::Show($message, "Estado de FactuFlow", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
}

function Open-FactuFlow {
    if ($script:CurrentState -eq "ready") {
        Start-Process $script:FrontendUrl
        return
    }

    Ensure-ServicesStarted
    Update-VisualStatus
    if ($script:CurrentState -eq "ready") {
        Start-Process $script:FrontendUrl
    } else {
        [System.Windows.Forms.MessageBox]::Show("FactuFlow se esta iniciando. Revisa el icono junto al reloj.", "FactuFlow", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    }
}

function Restart-Services {
    Stop-OwnedServices | Out-Null
    $script:BrowserOpened = $false
    $script:FailureNotified = $false
    $script:ManualStopped = $false
    $script:LastBlockingError = $null
    Start-Sleep -Seconds 1
    Ensure-ServicesStarted
    Update-VisualStatus
}

function Exit-Launcher {
    Stop-OwnedServices | Out-Null
    Write-LauncherLog "Cerrando launcher local."
    $script:Timer.Stop()
    $script:NotifyIcon.Visible = $false
    $script:NotifyIcon.Dispose()
    if ($null -ne $script:TrayIconHandle) {
        $script:TrayIconHandle.Dispose()
    }
    if ($null -ne $script:Mutex) {
        $script:Mutex.ReleaseMutex()
        $script:Mutex.Dispose()
    }
    [System.Windows.Forms.Application]::Exit()
}

if ($SelfTest) {
    $testIcon = New-StatusIcon -Color ([System.Drawing.Color]::FromArgb(32, 156, 86)) -Letter "F"
    if ($null -eq $testIcon) {
        throw "No se pudo generar el icono del tray."
    }
    $testIcon.Dispose()

    $backendTokens = $null
    $backendErrors = $null
    [System.Management.Automation.Language.Parser]::ParseInput((New-BackendRunnerScript), [ref]$backendTokens, [ref]$backendErrors) | Out-Null
    if ($backendErrors) {
        $backendErrors | Format-List *
        exit 1
    }

    $frontendTokens = $null
    $frontendErrors = $null
    [System.Management.Automation.Language.Parser]::ParseInput((New-FrontendRunnerScript), [ref]$frontendTokens, [ref]$frontendErrors) | Out-Null
    if ($frontendErrors) {
        $frontendErrors | Format-List *
        exit 1
    }

    "FactuFlow local tray self-test OK"
    exit 0
}

$script:Mutex = New-Object System.Threading.Mutex($true, "FactuFlowLocalTray", [ref]$script:CreatedMutex)
if (-not $script:CreatedMutex) {
    [System.Windows.Forms.MessageBox]::Show("FactuFlow local ya esta abierto. Usa el icono junto al reloj.", "FactuFlow", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    exit 0
}

Write-LauncherLog "Abriendo launcher local."

$script:NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$script:NotifyIcon.Visible = $true
$script:NotifyIcon.ContextMenuStrip = New-Object System.Windows.Forms.ContextMenuStrip
Set-TrayState -State "starting" -Message "Iniciando FactuFlow"

$openItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Abrir FactuFlow")
$statusItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Estado del sistema")
$restartItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Reiniciar servicios")
$stopItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Detener servicios")
$logsItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Abrir logs")
$script:NotifyIcon.ContextMenuStrip.Items.Add("-") | Out-Null
$exitItem = $script:NotifyIcon.ContextMenuStrip.Items.Add("Salir")

$openItem.Add_Click({ Open-FactuFlow })
$statusItem.Add_Click({ Show-SystemStatus })
$restartItem.Add_Click({ Restart-Services })
$stopItem.Add_Click({
    if (Stop-OwnedServices) {
        $script:ManualStopped = $true
        Set-TrayState -State "error" -Message "FactuFlow detenido"
    } else {
        [System.Windows.Forms.MessageBox]::Show("No hay servicios iniciados por este launcher para detener.", "FactuFlow", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    }
})
$logsItem.Add_Click({ Start-Process explorer.exe $script:LogDir })
$exitItem.Add_Click({ Exit-Launcher })
$script:NotifyIcon.Add_DoubleClick({ Open-FactuFlow })

$script:Timer = New-Object System.Windows.Forms.Timer
$script:Timer.Interval = 5000
$script:Timer.Add_Tick({ Update-VisualStatus })
$script:Timer.Start()

Ensure-ServicesStarted
Update-VisualStatus

[System.Windows.Forms.Application]::Run()

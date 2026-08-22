# Control del servidor de Giddy en Windows.
# Uso:  .\giddy.ps1 start | stop | status | log
param([Parameter(Position=0)][string]$Cmd = "status")

$Dir     = $PSScriptRoot
$Log     = Join-Path $Dir "data\server.log"
$PidFile = Join-Path $Dir "data\server.pid"
$Py      = Join-Path $Dir "venv\Scripts\python.exe"
$Config  = Join-Path $Dir "data\.config.yaml"
$ConfigureScript = Join-Path $Dir "configure-hermes.ps1"
$WarmScript = Join-Path $Dir "warm-hermes.ps1"
$WarmLocalScript = Join-Path $Dir "warm-local.ps1"
$WarmVoiceScript = Join-Path $Dir "warm-voice.py"

# Some launchers inject both Path and PATH. Start-Process treats them as a
# duplicate dictionary key on Windows, so normalize the process environment.
$pathValue = [Environment]::GetEnvironmentVariable("PATH", "Process")
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $null, "Process")
[Environment]::SetEnvironmentVariable("PATH", $pathValue, "Process")
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Get-GiddyPid {
    if (Test-Path $PidFile) {
        $p = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { return $p }
    }
    $listener = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener -and (Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue)) {
        return [string]$listener.OwningProcess
    }
    return $null
}

function Get-ConfiguredLanIp {
    if (Test-Path $Config) {
        $websocketLine = Get-Content $Config -ErrorAction SilentlyContinue |
            Where-Object { $_ -match '^\s*websocket:\s*ws://([^:/]+)' } |
            Select-Object -First 1
        if ($websocketLine -and $websocketLine -match '^\s*websocket:\s*ws://([^:/]+)') {
            return $Matches[1]
        }
    }
    return $null
}

function Test-HermesHealth {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8664/health" -TimeoutSec 2
        return $health.status -eq "ok"
    } catch {
        return $false
    }
}

function Test-LocalAiHealth {
    try {
        $version = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2
        return [bool]$version.version
    } catch {
        return $false
    }
}

function Warm-HermesSafely {
    try {
        & $WarmScript
    } catch {
        Write-Warning "Hermes no pudo precalentarse; Giddy continuara con IA local: $($_.Exception.Message)"
    }
}

function Test-GiddyHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8003/giddy" -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Warm-GiddyVoice {
    if (-not (Test-Path -LiteralPath $WarmVoiceScript)) { return }
    $result = & $Py $WarmVoiceScript 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo precalentar la voz: $result"
    }
}

function Get-PortalUrl {
    $ip = Get-ConfiguredLanIp
    if (-not $ip) { $ip = "127.0.0.1" }
    $tokenPath = Join-Path $Dir "data\giddy-setup-token.txt"
    if (Test-Path -LiteralPath $tokenPath) {
        $token = (Get-Content -Raw -LiteralPath $tokenPath).Trim()
        if ($token) { return "http://${ip}:8003/giddy?token=$token" }
    }
    return "http://${ip}:8003/giddy"
}

switch ($Cmd) {
    "start" {
        $runningPid = Get-GiddyPid
        if ($runningPid -and -not (Test-GiddyHealth)) {
            Write-Warning "Giddy conserva el proceso pero no responde; se iniciara una instancia limpia"
            Stop-Process -Id $runningPid -Force -ErrorAction SilentlyContinue
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            for ($attempt = 0; $attempt -lt 10; $attempt++) {
                $listener = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
                    Select-Object -First 1
                if (-not $listener) { break }
                Start-Sleep -Milliseconds 500
            }
            $runningPid = $null
        }
        if ($runningPid) {
            # The hourly watchdog also keeps the model resident, not just Ollama alive.
            try { & $WarmLocalScript } catch { Write-Warning $_ }
            if (-not (Test-HermesHealth)) {
                Warm-HermesSafely
            }
            try { Warm-GiddyVoice } catch { Write-Warning $_ }
            Write-Host "Ya esta corriendo (PID $runningPid)"
            break
        }
        if (-not (Test-Path $Py)) { Write-Host "No existe el venv. Ver docs/08-instalar-en-windows.md"; break }
        if (-not (Test-Path $Config)) {
            & $ConfigureScript
        }
        try { & $WarmLocalScript } catch { Write-Warning "La IA local no inicio; Giddy usara Hermes: $_" }
        Warm-HermesSafely
        try { Warm-GiddyVoice } catch { Write-Warning $_ }
        New-Item -ItemType Directory -Force -Path (Join-Path $Dir "data") | Out-Null
        $proc = Start-Process -FilePath $Py -ArgumentList "app.py" -WorkingDirectory $Dir `
                  -RedirectStandardOutput $Log -RedirectStandardError "$Log.err" `
                  -WindowStyle Hidden -PassThru
        $actualPid = $proc.Id
        $listening = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $listener = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($listener) {
                $actualPid = $listener.OwningProcess
                $listening = $true
                break
            }
            if ($proc.HasExited) { break }
            Start-Sleep -Seconds 1
        }
        if (-not $listening) {
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            throw "Giddy no abrio el puerto 8010. Revisa $Log.err"
        }
        $actualPid | Out-File -Encoding ascii $PidFile
        Write-Host "Giddy arrancando (PID $actualPid) - log: $Log"
        Write-Host "Panel: $(Get-PortalUrl)"
    }
    "stop" {
        $p = Get-GiddyPid
        if ($p) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            Write-Host "Detenido (PID $p)"
        } else {
            Get-Process python -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -like "*$Dir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            Write-Host "No estaba corriendo"
        }
    }
    "status" {
        $p = Get-GiddyPid
        if ($p) {
            $ip = Get-ConfiguredLanIp
            if (-not $ip) { $ip = "IP-LAN-NO-CONFIGURADA" }
            Write-Host "CORRIENDO (PID $p)"
            Write-Host "OTA:       http://${ip}:8003/xiaozhi/ota/"
            Write-Host "WebSocket: ws://${ip}:8010/xiaozhi/v1/"
            if (Test-HermesHealth) { Write-Host "Hermes:    ok" }
            else { Write-Host "Hermes:    no responde" }
            if (Test-LocalAiHealth) { Write-Host "IA local:  ok" }
            else { Write-Host "IA local:  no responde; se usa Hermes" }
            Write-Host "Panel:     $(Get-PortalUrl)"
        } else { Write-Host "DETENIDO" }
    }
    "portal" { Write-Host (Get-PortalUrl) }
    "log" { if (Test-Path $Log) { Get-Content $Log -Tail 40 } else { Write-Host "sin log" } }
    default { Write-Host "Uso: .\giddy.ps1 start | stop | status | log | portal" }
}

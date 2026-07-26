# Control del servidor de Giddy en Windows.
# Uso:  .\giddy.ps1 start | stop | status | log
param([Parameter(Position=0)][string]$Cmd = "status")

$Dir     = $PSScriptRoot
$Log     = Join-Path $Dir "data\server.log"
$PidFile = Join-Path $Dir "data\server.pid"
$Py      = Join-Path $Dir "venv\Scripts\python.exe"

function Get-GiddyPid {
    if (Test-Path $PidFile) {
        $p = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { return $p }
    }
    return $null
}

switch ($Cmd) {
    "start" {
        if (Get-GiddyPid) { Write-Host "Ya está corriendo (PID $(Get-GiddyPid))"; break }
        if (-not (Test-Path $Py)) { Write-Host "❌ No existe el venv. Ver docs/08-instalar-en-windows.md"; break }
        New-Item -ItemType Directory -Force -Path (Join-Path $Dir "data") | Out-Null
        $proc = Start-Process -FilePath $Py -ArgumentList "app.py" -WorkingDirectory $Dir `
                  -RedirectStandardOutput $Log -RedirectStandardError "$Log.err" `
                  -WindowStyle Hidden -PassThru
        $proc.Id | Out-File -Encoding ascii $PidFile
        Write-Host "Giddy arrancando (PID $($proc.Id)) — log: $Log"
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
            $ip = (Get-NetIPAddress -AddressFamily IPv4 |
                   Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
                   Select-Object -First 1).IPAddress
            Write-Host "CORRIENDO (PID $p)"
            Write-Host "OTA:       http://${ip}:8003/xiaozhi/ota/"
            Write-Host "WebSocket: ws://${ip}:8000/xiaozhi/v1/"
        } else { Write-Host "DETENIDO" }
    }
    "log" { if (Test-Path $Log) { Get-Content $Log -Tail 40 } else { Write-Host "sin log" } }
    default { Write-Host "Uso: .\giddy.ps1 start | stop | status | log" }
}

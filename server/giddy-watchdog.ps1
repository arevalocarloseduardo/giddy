# Idempotent hourly recovery for the Windows voice service and both AI tiers.
param([int]$Attempts = 20, [int]$RetrySeconds = 30)

$ErrorActionPreference = "Stop"
$Dir = $PSScriptRoot
$Control = Join-Path $Dir "giddy.ps1"
$Log = Join-Path $Dir "data\watchdog.log"
$mutex = [Threading.Mutex]::new($false, "Local\GiddyCommercialWatchdog")

function Write-WatchdogLog([string]$Message) {
    $parent = Split-Path -Parent $Log
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if ((Test-Path -LiteralPath $Log) -and (Get-Item -LiteralPath $Log).Length -gt 1MB) {
        Clear-Content -LiteralPath $Log
    }
    $line = "{0:o} {1}" -f (Get-Date), $Message
    Add-Content -LiteralPath $Log -Value $line -Encoding utf8
}

function Test-GiddyReady {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8003/giddy" -TimeoutSec 3
        if ($response.StatusCode -ne 200) { return $false }
        $local = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 3
        if (-not $local.version) { return $false }
        $hermes = Invoke-RestMethod -Uri "http://127.0.0.1:8664/health" -TimeoutSec 3
        return $hermes.status -eq "ok"
    } catch {
        return $false
    }
}

if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $InformationPreference = "SilentlyContinue"
            $null = & $Control start 2>&1
            if (Test-GiddyReady) {
                Write-WatchdogLog "ok attempt=$attempt"
                exit 0
            }
            throw "Los servicios todavia no estan listos"
        } catch {
            Write-WatchdogLog "retry attempt=$attempt error=$($_.Exception.Message)"
            if ($attempt -lt $Attempts) { Start-Sleep -Seconds $RetrySeconds }
        }
    }
    Write-WatchdogLog "failed attempts=$Attempts"
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

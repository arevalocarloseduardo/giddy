param(
    [string]$Model = "qwen3.5:9b",
    [string]$ApiBase = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

function Test-OllamaHealth {
    try {
        $version = Invoke-RestMethod -Uri "$ApiBase/api/version" -TimeoutSec 2
        return [bool]$version.version
    } catch {
        return $false
    }
}

if (-not (Test-OllamaHealth)) {
    if (-not (Test-Path -LiteralPath $ollamaExe)) {
        throw "Ollama no esta instalado en $ollamaExe"
    }
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 30 -and -not (Test-OllamaHealth); $attempt++) {
        Start-Sleep -Seconds 1
    }
}
if (-not (Test-OllamaHealth)) {
    throw "Ollama no respondio en $ApiBase"
}

$body = @{
    model = $Model
    stream = $false
    think = $false
    keep_alive = "2h"
    messages = @(
        @{ role = "system"; content = "Responde una palabra." }
        @{ role = "user"; content = "Deci listo." }
    )
    options = @{
        num_ctx = 4096
        num_predict = 8
    }
} | ConvertTo-Json -Depth 6

$started = Get-Date
$response = Invoke-RestMethod -Method Post -Uri "$ApiBase/api/chat" `
    -ContentType "application/json" -Body $body -TimeoutSec 180
$elapsed = ((Get-Date) - $started).TotalSeconds
if (-not $response.message.content) {
    throw "El modelo local no genero una respuesta"
}
Write-Host ("Modelo local {0} listo en {1:N1}s" -f $Model, $elapsed)

param(
    [string]$TenantEnv = "E:\HermesInstances\data\tenants\giddy\.env",
    [string]$ApiBase = "http://127.0.0.1:8664"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $TenantEnv)) {
    throw "No se encontro el entorno de Hermes Giddy: $TenantEnv"
}
$apiKeyLine = Get-Content -LiteralPath $TenantEnv |
    Where-Object { $_ -like "API_SERVER_KEY=*" } |
    Select-Object -Last 1
$apiKey = if ($apiKeyLine) { ($apiKeyLine -split "=", 2)[1].Trim() } else { "" }
if ($apiKey.Length -lt 32) {
    throw "API_SERVER_KEY ausente o invalida"
}

$headers = @{
    Authorization = "Bearer $apiKey"
    "X-Hermes-Session-Key" = "giddy-warmup"
}

function Test-HermesHealth {
    try {
        $health = Invoke-RestMethod -Uri "$ApiBase/health" -Headers $headers -TimeoutSec 2
        return $health.status -eq "ok"
    } catch {
        return $false
    }
}

$container = docker ps -a --filter "name=^/hermes-giddy$" --format "{{.Names}}"
if ($container -ne "hermes-giddy") {
    throw "No existe el contenedor aislado hermes-giddy"
}

$running = docker inspect hermes-giddy --format "{{.State.Running}}"
if ($running -ne "true") {
    docker start hermes-giddy | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar hermes-giddy" }
}

$healthy = $false
for ($attempt = 0; $attempt -lt 10; $attempt++) {
    if (Test-HermesHealth) {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $healthy) {
    docker restart hermes-giddy | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo reiniciar hermes-giddy" }
}
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if (Test-HermesHealth) {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $healthy) {
    throw "Hermes Giddy no respondio en $ApiBase"
}

$body = @{
    model = "giddy"
    messages = @(
        @{ role = "system"; content = "Calentamiento interno. Responde solo una palabra." }
        @{ role = "user"; content = "Responde listo." }
    )
    stream = $false
    max_tokens = 8
} | ConvertTo-Json -Depth 5

$started = Get-Date
Invoke-RestMethod -Method Post -Uri "$ApiBase/v1/chat/completions" `
    -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 120 | Out-Null
$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Host ("Hermes Giddy listo y caliente en {0:N1}s" -f $elapsed)

param(
    [string]$TenantEnv = "E:\HermesInstances\data\tenants\giddy\.env",
    [string]$LanIp = ""
)

$ErrorActionPreference = "Stop"
$template = Join-Path (Split-Path -Parent $PSScriptRoot) "config\hermes-giddy.yaml.example"
$dataDir = Join-Path $PSScriptRoot "data"
$target = Join-Path $dataDir ".config.yaml"

if (-not (Test-Path -LiteralPath $template)) {
    throw "No se encontro la plantilla: $template"
}
if (-not (Test-Path -LiteralPath $TenantEnv)) {
    throw "No se encontro el entorno privado de Hermes Giddy: $TenantEnv"
}

$apiKeyLine = Get-Content -LiteralPath $TenantEnv |
    Where-Object { $_ -like "API_SERVER_KEY=*" } |
    Select-Object -Last 1
$apiKey = if ($apiKeyLine) { ($apiKeyLine -split "=", 2)[1].Trim() } else { "" }
if ($apiKey.Length -lt 32) {
    throw "API_SERVER_KEY ausente o invalida en $TenantEnv"
}

if (-not $LanIp) {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if ($route) {
        $LanIp = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Sort-Object SkipAsSource |
            Select-Object -First 1 -ExpandProperty IPAddress
    }
}
if (-not $LanIp) {
    throw "No se pudo detectar la IP LAN. Ejecuta con -LanIp x.x.x.x"
}

$content = Get-Content -Raw -LiteralPath $template
$content = $content.Replace("__GIDDY_LAN_IP__", $LanIp)
$content = $content.Replace("__HERMES_API_KEY__", $apiKey)

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$temp = "$target.tmp"
[System.IO.File]::WriteAllText($temp, $content, (New-Object System.Text.UTF8Encoding($false)))
Move-Item -LiteralPath $temp -Destination $target -Force

Write-Host "Configuracion privada creada: $target"
Write-Host "WebSocket: ws://${LanIp}:8010/xiaozhi/v1/"
Write-Host "OTA: http://${LanIp}:8003/xiaozhi/ota/"

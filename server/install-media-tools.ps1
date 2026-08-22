param(
    [string]$DownloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)

$ErrorActionPreference = "Stop"
$nativeDir = Join-Path $PSScriptRoot "native"
if ((Test-Path (Join-Path $nativeDir "ffmpeg.exe")) -and
    (Test-Path (Join-Path $nativeDir "ffprobe.exe"))) {
    Write-Host "FFmpeg ya esta instalado para Giddy"
    exit 0
}

$workDir = Join-Path $env:TEMP "giddy-ffmpeg-install"
$zipPath = Join-Path $workDir "ffmpeg.zip"
$extractDir = Join-Path $workDir "extract"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
Remove-Item -Recurse -Force -LiteralPath $extractDir -ErrorAction SilentlyContinue

Invoke-WebRequest -Uri $DownloadUrl -OutFile $zipPath -UseBasicParsing
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
$packageDir = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
if (-not $packageDir) {
    throw "El paquete de FFmpeg no tiene la estructura esperada"
}

New-Item -ItemType Directory -Force -Path $nativeDir | Out-Null
Copy-Item -Force -LiteralPath (Join-Path $packageDir.FullName "bin\ffmpeg.exe") -Destination $nativeDir
Copy-Item -Force -LiteralPath (Join-Path $packageDir.FullName "bin\ffprobe.exe") -Destination $nativeDir
Write-Host "Herramientas de audio instaladas en $nativeDir"

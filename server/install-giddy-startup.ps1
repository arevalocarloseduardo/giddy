# Register Giddy recovery at sign-in and once per hour for the current user.
param([string]$TaskName = "Giddy Commercial Assistant")

$ErrorActionPreference = "Stop"
$Watchdog = Join-Path $PSScriptRoot "giddy-watchdog.ps1"
if (-not (Test-Path -LiteralPath $Watchdog)) {
    throw "No se encontro $Watchdog"
}

$argument = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Watchdog`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action `
    -Trigger @($logon, $hourly) -Settings $settings -Principal $principal `
    -Description "Mantiene Giddy, Hermes y la IA local disponibles." -Force | Out-Null

Write-Host "Inicio automatico instalado: $TaskName"
Write-Host "Se ejecuta al iniciar sesion y cada hora."

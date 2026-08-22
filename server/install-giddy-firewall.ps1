#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$rules = @(
    @{ Name = "Giddy WebSocket 8010"; Port = 8010 },
    @{ Name = "Giddy HTTP OTA 8003"; Port = 8003 }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $rule.Name -Enabled True -Direction Inbound `
            -Action Allow -Profile Any -RemoteAddress LocalSubnet | Out-Null
    } else {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol TCP `
            -LocalPort $rule.Port -Action Allow -Profile Any -RemoteAddress LocalSubnet | Out-Null
    }
}

Write-Host "Firewall listo para Giddy (puertos 8010 y 8003, solo red local)."

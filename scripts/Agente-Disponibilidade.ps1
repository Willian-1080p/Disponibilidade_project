#requires -Version 5.1

<#
Preencha a URL pública e o token exclusivo recebido no POST /api/agents.
Cada computador deve usar seu próprio token.
#>

$ApiBaseUrl = "https://SUA-URL-PUBLICA"
$AgentToken = "COLE-O-TOKEN-EXCLUSIVO-AQUI"
$LogPath = Join-Path $env:ProgramData "Disponibilidade\agente.log"

function Write-AgentLog {
    param([string]$Message)
    $directory = Split-Path -Parent $LogPath
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $line = "{0:u} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

try {
    $activeIp = Get-WmiObject Win32_NetworkAdapterConfiguration |
        Where-Object { $_.IPEnabled -and $_.DefaultIPGateway } |
        Select-Object -First 1 -ExpandProperty IPAddress |
        Select-Object -First 1

    $operatingSystem = Get-WmiObject Win32_OperatingSystem |
        Select-Object -ExpandProperty Caption

    $body = @{
        hostname         = $env:COMPUTERNAME
        local_ip         = $activeIp
        operating_system = $operatingSystem
    } | ConvertTo-Json

    $headers = @{
        "X-Agent-Token" = $AgentToken
    }

    $response = Invoke-RestMethod `
        -Uri "$($ApiBaseUrl.TrimEnd('/'))/api/heartbeat" `
        -Method POST `
        -Headers $headers `
        -Body $body `
        -ContentType "application/json; charset=utf-8" `
        -TimeoutSec 30

    Write-AgentLog "Heartbeat enviado com sucesso: $($response.status)"
}
catch {
    Write-AgentLog "Falha ao enviar heartbeat: $($_.Exception.Message)"
    exit 1
}


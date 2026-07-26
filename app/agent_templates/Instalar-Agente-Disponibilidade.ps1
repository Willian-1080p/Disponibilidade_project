#requires -Version 5.1

param(
    [ValidateSet("Install", "Heartbeat", "Remove")]
    [string]$Mode = "Install"
)

<#
Agente gerado automaticamente pelo Projeto Disponibilidade e Verificação.
A URL da API e o token abaixo já pertencem a este computador.
#>

$ApiBaseUrl = "__API_BASE_URL__"
$AgentToken = "__AGENT_TOKEN__"
$TaskName = "Projeto Disponibilidade - Heartbeat"
$InstallDirectory = Join-Path $env:ProgramData "Disponibilidade"
$InstalledScript = Join-Path $InstallDirectory "Agente-Disponibilidade.ps1"
$LogPath = Join-Path $InstallDirectory "agente.log"

function Write-AgentLog {
    param([string]$Message)
    if (-not (Test-Path $InstallDirectory)) {
        New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    }
    $line = "{0:u} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Send-Heartbeat {
    try {
        try {
            [Net.ServicePointManager]::SecurityProtocol =
                [Net.ServicePointManager]::SecurityProtocol -bor
                [Net.SecurityProtocolType]::Tls12
        }
        catch { }

        $activeIp = Get-WmiObject Win32_NetworkAdapterConfiguration |
            Where-Object { $_.IPEnabled -and $_.DefaultIPGateway } |
            Select-Object -First 1 -ExpandProperty IPAddress |
            Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' } |
            Select-Object -First 1

        $operatingSystem = Get-WmiObject Win32_OperatingSystem |
            Select-Object -ExpandProperty Caption

        $body = @{
            hostname         = $env:COMPUTERNAME
            local_ip         = $activeIp
            operating_system = $operatingSystem
        } | ConvertTo-Json

        $response = Invoke-RestMethod `
            -Uri "$($ApiBaseUrl.TrimEnd('/'))/api/heartbeat" `
            -Method POST `
            -Headers @{ "X-Agent-Token" = $AgentToken } `
            -Body $body `
            -ContentType "application/json; charset=utf-8" `
            -TimeoutSec 30 `
            -ErrorAction Stop

        Write-AgentLog "Heartbeat enviado com sucesso: $($response.status)"
        Write-Host "Heartbeat enviado com sucesso." -ForegroundColor Green
    }
    catch {
        Write-AgentLog "Falha ao enviar heartbeat: $($_.Exception.Message)"
        Write-Host "Falha ao enviar heartbeat: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

function Install-Agent {
    if (-not (Test-Administrator)) {
        throw "Abra o PowerShell como Administrador e execute o script novamente."
    }

    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    Copy-Item -Path $PSCommandPath -Destination $InstalledScript -Force

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$InstalledScript`" -Mode Heartbeat"

    $trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 1)

    $principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Description "Envia o heartbeat do computador ao Projeto Disponibilidade." `
        -Force | Out-Null

    Write-AgentLog "Agente instalado com API $ApiBaseUrl."
    Send-Heartbeat
    Write-Host "Agente instalado e tarefa '$TaskName' criada." -ForegroundColor Green
}

function Remove-Agent {
    if (-not (Test-Administrator)) {
        throw "Abra o PowerShell como Administrador para remover o agente."
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path $InstalledScript) {
        Remove-Item $InstalledScript -Force
    }
    Write-Host "Agente e tarefa agendada removidos." -ForegroundColor Yellow
}

try {
    switch ($Mode) {
        "Install" { Install-Agent }
        "Heartbeat" { Send-Heartbeat }
        "Remove" { Remove-Agent }
    }
}
catch {
    Write-AgentLog $_.Exception.Message
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

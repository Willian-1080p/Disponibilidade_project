#requires -RunAsAdministrator

$SourceScript = Join-Path $PSScriptRoot "Agente-Disponibilidade.ps1"
$DestinationDirectory = Join-Path $env:ProgramData "Disponibilidade"
$DestinationScript = Join-Path $DestinationDirectory "Agente-Disponibilidade.ps1"
$TaskName = "Projeto Disponibilidade - Heartbeat"

if (-not (Test-Path $SourceScript)) {
    throw "Arquivo Agente-Disponibilidade.ps1 não encontrado na mesma pasta."
}

New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
Copy-Item $SourceScript $DestinationScript -Force

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$DestinationScript`""

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

Start-ScheduledTask -TaskName $TaskName
Write-Host "Agente instalado e tarefa '$TaskName' iniciada." -ForegroundColor Green


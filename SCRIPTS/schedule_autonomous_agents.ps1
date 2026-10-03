# Programa el jefe (S1-JEFE) para que trabaje solo, sin que nadie abra Claude Code a mano.
#
# El jefe puede hacer cualquier tarea (investigar, escribir, editar, maquetar...), asi que basta
# con programar uno: cada vez que corre atiende el chat, revisa directrices y saca adelante las
# ideas que ya hayais puesto en marcha. Usa SCRIPTS\run_worker.ps1 (claude -p, sin supervision).
#
# Normalmente se lanza con ACTIVAR_AGENTES.bat (doble clic). A mano:
#   powershell -ExecutionPolicy Bypass -File "<ruta completa>\SCRIPTS\schedule_autonomous_agents.ps1"
# Para quitarlo: Unregister-ScheduledTask -TaskName "EBookFactory-S1-JEFE" -Confirm:$false

param([int]$IntervalHours = 2)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$taskName = "EBookFactory-S1-JEFE"
$worker = Join-Path $root "SCRIPTS\run_worker.ps1"

try {
    if (-not (Test-Path $worker)) { throw "No encuentro $worker" }

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
      -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$worker`" -AgentId S1-JEFE" `
      -WorkingDirectory $root

    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
      -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration (New-TimeSpan -Days 3650)

    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
      -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal `
      -Settings $settings -Description "E-Book Factory: S1-JEFE trabaja solo cada $IntervalHours horas" | Out-Null

    # Puente con el panel de Vercel: proceso permanente (se relanza solo cada 10 min si se cae).
    $bridgeName = "EBookFactory-Puente"
    $bridgeAction = New-ScheduledTaskAction -Execute "powershell.exe" `
      -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$root'; python factory.py bridge`"" `
      -WorkingDirectory $root
    $bridgeTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
      -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
    $bridgeSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
      -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
    Unregister-ScheduledTask -TaskName $bridgeName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $bridgeName -Action $bridgeAction -Trigger $bridgeTrigger -Principal $principal `
      -Settings $bridgeSettings -Description "E-Book Factory: mantiene al dia el panel web de Vercel" | Out-Null
    Start-ScheduledTask -TaskName $bridgeName

    Write-Host ""
    Write-Host "LISTO: tarea '$taskName' programada cada $IntervalHours horas." -ForegroundColor Green
    Write-Host "LISTO: tarea '$bridgeName' (panel web siempre al dia) en marcha." -ForegroundColor Green
    Write-Host "Trabaja mientras tu usuario de Windows tenga la sesion iniciada (el PC puede estar bloqueado)."
    Write-Host "Ver:    Get-ScheduledTask -TaskName '$taskName'"
    Write-Host "Quitar: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
}
catch {
    Write-Host ""
    Write-Host "ERROR al programar la tarea:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Message -match "denied|denegado|0x80070005") {
        Write-Host "Solucion: cierra esta ventana, haz clic derecho en ACTIVAR_AGENTES.bat y elige 'Ejecutar como administrador'." -ForegroundColor Yellow
    }
    exit 1
}

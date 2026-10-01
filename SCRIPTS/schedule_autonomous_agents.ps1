# Programa el jefe (S1-JEFE) para que trabaje solo, sin que nadie abra Claude Code a mano.
#
# El jefe puede hacer cualquier tarea (investigar, escribir, editar, maquetar...), así que basta
# con programar uno: cada vez que corre, atiende el chat, revisa directrices, y si hay capacidad
# (daily_target en CONFIG/factory.json) saca libros adelante solo. Usa SCRIPTS/run_worker.ps1,
# que ya existía pero nunca se había programado ni probado desatendido.
#
# Uso (como ADMIN, una vez): powershell -ExecutionPolicy Bypass -File SCRIPTS\schedule_autonomous_agents.ps1
# Para quitarlo: Unregister-ScheduledTask -TaskName "EBookFactory-S1-JEFE" -Confirm:$false

param([int]$IntervalHours = 2)

$root = Split-Path -Parent $PSScriptRoot
$taskName = "EBookFactory-S1-JEFE"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$root\SCRIPTS\run_worker.ps1`" -AgentId S1-JEFE" `
  -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "E-Book Factory: S1-JEFE trabaja solo cada $IntervalHours horas (claude -p, sin supervision)"

Write-Host "Tarea '$taskName' programada cada $IntervalHours horas. Primera ejecucion: ahora mismo."
Write-Host "Para verla:    Get-ScheduledTask -TaskName '$taskName'"
Write-Host "Para quitarla: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"

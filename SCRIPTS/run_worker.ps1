# Lanza una sesión autónoma de un agente (Claude Code en modo no interactivo).
# Uso:  powershell -File SCRIPTS\run_worker.ps1 -AgentId S1-CLAUDE-001
# Programable con el Programador de tareas de Windows (p. ej. cada 3 horas).
# Revisa los permisos antes de usarlo sin supervisión: el agente solo necesita leer/escribir
# en esta carpeta y ejecutar `python factory.py ...` (y búsqueda web para RESEARCH/FACT_CHECK).
param([Parameter(Mandatory = $true)][string]$AgentId)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$prompt = (Get-Content -Raw -Encoding UTF8 "PROMPTS\WORKER.md") -replace '<AGENT_ID>', $AgentId
$log = "LOGS\worker_$($AgentId)_$(Get-Date -Format 'yyyyMMdd_HHmm').log"

# NO PROBADO TODAVÍA en modo desatendido (ver FACTORY_BOOTSTRAP_REPORT.md). Si la sesión muere a mitad de una tarea,
# la tarea queda RUNNING y `recover` la devuelve a la cola cuando caduca su lock (90 min): no se pierde trabajo.
claude -p $prompt --permission-mode acceptEdits --allowedTools "Bash(python factory.py:*)" "Read" "Write" "Edit" "WebSearch" "WebFetch" *>> $log
python factory.py recover --agent $AgentId *>> $log
python factory.py report *>> $log

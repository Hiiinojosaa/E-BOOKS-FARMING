# Arquitectura

## Decisiones (y por qué)

| Decisión | Motivo |
|---|---|
| **Estado en archivos JSON dentro de un repo Git** | Persistente, legible por humanos y agentes, auditable (git log), sin servidor. Se comparte entre socios con un remoto privado. |
| **Python stdlib, sin dependencias** | Cualquier agente (de SOCIO-1 o de DANI) lo ejecuta sin instalar nada. |
| **Una carpeta por estado de tarea** (`TASKS/READY/…`) | Reclamar = `os.rename` atómico ⇒ dos agentes nunca ganan la misma tarea. Estado visible con `ls`. |
| **Un archivo por entidad** (libro, tarea, agente, decisión) | Sin archivo compartido caliente ⇒ casi sin conflictos de Git entre máquinas. |
| **Logs append-only partidos por día** + `merge=union` | Dos máquinas pueden añadir eventos a la vez sin conflicto. |
| **El motor no escribe contenido** | Los agentes LLM escriben; el motor gestiona estados, colas, locks, validación, maquetación, QC e informes. |
| **Cada edición de idioma = libro propio** | Trazable (`parent_book`, `translated_from`), con su propio QC, metadatos y paquete. |
| **JSON en vez de YAML** | Sin dependencias y sin ambigüedades de parseo. `book.json` cumple el papel de `book.yaml`. |
| **EPUB con zipfile + PDF/portada con Chrome headless** | Herramientas ya instaladas; pandoc/Calibre/epubcheck quedan como mejoras opcionales. |

## Componentes

```
                ┌──────────────── factory.py (CLI) ────────────────┐
 humanos ──────►│ approve / request-changes / reject / decide …    │
 agentes ──────►│ next / complete / fail / release / tick          │
                └──────┬───────────────┬──────────────┬────────────┘
     orchestrator.py   │   tasks.py    │  locks.py    │ validators.py  qc.py  build.py  publishing.py  reports.py
   (gates, siguiente   │ (cola, claim, │ (TTL,        │ (contrato de   (QC     (EPUB,    (revisión,      (dashboard,
    tarea, recover,    │  reintentos)  │  heartbeat)  │  salidas)      indep.)  PDF,     paquete)        informes,
    traducciones)      │               │              │                         portada)                  métricas)
                       ▼
          books.py (book.json + history.jsonl — única vía para cambiar estado)
```

## Escalabilidad (10 → 500 libros)

- Coste por libro ~40 archivos pequeños; 500 libros ≈ 20k archivos: Git lo maneja sin problema.
- Operaciones O(nº libros + nº tareas) leyendo JSON: < 1 s hasta varios miles.
- `max_active_books` (WIP) evita abrir más libros de los que los agentes pueden terminar.
- Cuando `TASKS/DONE` crezca (>5k), archivar por mes (`TASKS/DONE/2026-10/`) — pendiente, no hace falta aún.
- Si algún día hay >10 agentes simultáneos en máquinas distintas, migrar la cola a una BD (Postgres/Supabase) manteniendo el mismo protocolo (`next/complete/fail/release`). El resto del sistema no cambia.

## Multi-máquina (SOCIO-1 + DANI)

**Modo A — misma carpeta (varios agentes en un ordenador):** locks y renames atómicos del sistema de archivos. Probado con 6 procesos en carrera.

**Modo B — distintas máquinas:** un repo Git privado (GitHub) es la fuente de verdad. **Un clon por agente.**
Activar en `CONFIG/factory.json`: `"git": {"sync_enabled": true, "remote": "origin", "branch": "main"}`.
- Todos los comandos que modifican hacen `commit → pull --rebase → push` al terminar.
- `next` hace `pull` antes de reclamar y publica el claim inmediatamente. Si dos máquinas reclaman la misma tarea, Git produce conflicto en `TASKS/RUNNING/<task>.json`; la segunda máquina descarta su claim y coge otra tarea (probado en `TestGitMultiMachine`).
- Locks caducados se recuperan igual que en local (`recover`).
- Conflicto de sync no resoluble ⇒ el comando avisa y **no destruye nada** (commit local intacto); escalar a humano.

## Agentes

`AGENTS/<ID>.json`: `agent_id, owner, provider, model, capabilities, status, current_task, last_seen`.
`capabilities` = `["*"]` o roles (`RESEARCH_AGENT, WRITER_AGENT, EDITOR_AGENT, FACT_CHECK_AGENT, TRANSLATOR_AGENT,
MARKET_AGENT, DESIGN_AGENT, FORMAT_AGENT, QC_AGENT`). Un agente sólo recibe tareas de sus roles.
Recomendación: el agente que escribió un libro no debería hacer su QC (configurar capacidades distintas cuando haya ≥2 agentes).

## Especialistas ↔ pasos

| Especialista | Paso | Ejecuta |
|---|---|---|
| ORCHESTRATOR | `tick`/`orchestrate` | script (cualquier agente lo lanza) |
| RESEARCH_AGENT | RESEARCH, BRIEF | LLM |
| WRITER_AGENT | WRITE | LLM |
| EDITOR_AGENT | EDIT, FIX | LLM |
| FACT_CHECK_AGENT | FACT_CHECK | LLM |
| TRANSLATOR_AGENT | TRANSLATE | LLM |
| MARKET_AGENT + METADATA_AGENT (fusionados) | METADATA | LLM — comparten insumos y salida |
| DESIGN_AGENT | DESIGN | LLM elige plantilla/paleta → script renderiza |
| FORMAT_AGENT | FORMAT | script (automático) |
| QC_AGENT | QC | script independiente + revisión LLM |
| PUBLISHING_PREPARATION_AGENT | tras APPROVE | script (`releases/…/PUBLISHING_PACKAGE`) |
| REPORTING_AGENT | `report` | script |

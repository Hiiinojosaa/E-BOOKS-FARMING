# FACTORY BOOTSTRAP REPORT — 2026-10-01

Agente: `S1-CLAUDE-001` (Claude Code, cuenta Pro de SOCIO-1). Estado final: **infraestructura operativa, tests en verde,
EB-TEST-001 en READY_FOR_PUBLISHING**.

## 1. Entorno encontrado

| Herramienta | Estado | Uso |
|---|---|---|
| Windows 11, Python 3.14.7 | ✅ | Motor (solo librería estándar) |
| Git 2.55 | ✅ (sin usuario global configurado) | Versionado, sync multi-máquina |
| Google Chrome / Microsoft Edge | ✅ | PDF (print-to-pdf) y portadas (screenshot) en modo headless |
| Node 24, Docker 29 | ✅ (no usados) | Disponibles para futuras ampliaciones |
| pandoc | ❌ | No necesario (conversor Markdown propio) |
| epubcheck + Java | ❌ | Opcional: validador oficial de EPUB. Hoy hay un validador estructural propio |
| Calibre (ebook-convert) | ❌ | Opcional: MOBI/AZW3 (KDP ya acepta EPUB) |
| poppler / Pillow | ❌ | Opcional: previsualizar páginas del PDF y procesar imágenes |
| GitHub CLI (`gh`) | ❌ | Opcional: crear el repo remoto desde terminal |

Ubicación actual del proyecto: carpeta temporal que la app creó para esta sesión (se borra con la sesión). **Hay que moverlo a una carpeta permanente** (ver §8).

## 2. Arquitectura creada

Repositorio Git con estado en archivos JSON (un archivo por libro/tarea/agente/decisión) y un CLI (`factory.py`) que es la
única vía para cambiar estados. Detalle y justificación: `SYSTEM/architecture.md`. Cambios respecto a la propuesta inicial:

- `book.json` en lugar de `book.yaml` (sin dependencias, sin ambigüedad de parseo).
- Estados de tarea = carpetas (`TASKS/READY|RUNNING|…`): reclamar una tarea es un `rename` atómico.
- `OUTPUT/DRAFTS|REVIEWED|FINAL|READY_TO_PUBLISH` se sustituye por carpetas **dentro de cada libro** (`manuscript/`, `build/`, `releases/vX.Y/PUBLISHING_PACKAGE/`): todo lo de un libro en un sitio, imposible mezclar archivos entre libros.
- `TASKS/REVIEW` y `TASKS/APPROVED` no existen: revisión y aprobación son **estados del libro**, no de tareas.
- Añadidos: `LOCKS/`, `DECISIONS/` (preguntas a los socios), `COLLECTIONS/`, `REPORTS/`, `tests/`.
- MARKET_AGENT y METADATA_AGENT fusionados en un paso (mismos insumos, misma salida). FORMAT, PUBLISHING_PREPARATION y REPORTING son scripts, no LLM.
- Paso extra `FIX` para el bucle QC_FAILED → corrección → FORMAT → QC. Cada idioma es un libro propio enlazado (`translated_from`, `parent_book`).

## 3. Archivos creados

| Ruta | Contenido |
|---|---|
| `CLAUDE.md`, `README.md` | manual operativo de agentes · guía de socios |
| `factory.py`, `factory/` (13 módulos, ~3.600 líneas con tests) | core, states, locks, books, agents, tasks, validators, qc, build, publishing, orchestrator, decisions, reports, gitsync, cli |
| `SYSTEM/` (9) | architecture, workflow, quality_rules, writing_rules, translation_rules, publishing_rules, agent_protocol, security, escalation_rules |
| `PROMPTS/` (13) | WORKER (sesión autónoma), OPPORTUNITIES, RESEARCH, BRIEF, WRITE, EDIT, FACT_CHECK, TRANSLATE, METADATA, DESIGN, FORMAT, QC, FIX |
| `TEMPLATES/` | portadas `minimal` y `stack`, copyright y disclaimer ES/EN, estructura de libro |
| `CONFIG/factory.json`, `CONFIG/environment.json` | parámetros (reintentos, TTL de locks, WIP, aprobaciones…) · resultado de `doctor` |
| `tests/`, `SCRIPTS/simulate_agents.py`, `SCRIPTS/run_worker.ps1` | 18 tests · simulador multi-agente · lanzador de sesión autónoma |
| `.gitignore`, `.gitattributes`, `.env.example` | sin secretos; logs con `merge=union` |
| `BOOKS/EB-TEST-001/` | libro de prueba completo (ver §5) |
| `REPORTS/` | DASHBOARD.md, dashboard.html, DAILY/WEEKLY_REPORT, MEETING_PACK, `tests/` con informes de simulación |

## 4. Tests realizados

| Test | Resultado |
|---|---|
| Suite unitaria (`python -m unittest discover -s tests -t .`): máquina de estados, transiciones inválidas, historial, IDs únicos, detección de riesgo, locks exclusivos y caducados, no duplicar tareas, un agente por libro, reintentos → BLOCKED → unblock, release sin consumir reintento, RECOVER de tareas huérfanas y `.tmp`, límite WIP, detectores de QC, pipeline completo hasta READY_FOR_PUBLISHING, release inmutable, 2 libros/2 agentes sin mezcla, traducción enlazada | **18/18 PASS** |
| Carrera real: 6 procesos del SO reclaman la misma tarea | **PASS**: exactamente 1 ganador |
| Multi-máquina: remoto Git + 2 clones reclaman la misma tarea a la vez | **PASS**: Git detecta el conflicto, el segundo descarta su claim y ve el del primero |
| **Test 1** EB-TEST-001 (contenido real) RESEARCH → BRIEF → WRITE → EDIT → FACT_CHECK → METADATA → DESIGN → FORMAT → QC (FAIL) → FIX → FORMAT → QC → HUMAN_REVIEW → APPROVED → READY_FOR_PUBLISHING | **PASS** |
| **Test 2** EB-TEST-002 + EB-TEST-003 simultáneos | **PASS** (`REPORTS/tests/MULTI_AGENT_SIMULATION.md`) |
| **Test 3** AGENT-A en EB-TEST-002 mientras AGENT-B en EB-TEST-003, procesos separados | **PASS**: A hizo los 9 pasos de 002, B los 9 de 003, sin conflictos |
| Estrés: 4 agentes × 6 libros, 3 ejecuciones | **PASS** las 3: 54 tareas, 0 duplicadas, 0 mezclas, integridad OK (`REPORTS/tests/MULTI_AGENT_STRESS.md`) |

Los tests 2, 3 y de estrés usan **texto sintético** en una carpeta temporal aislada: demuestran la mecánica (estados,
locks, cola, maquetación, QC), no la calidad editorial, y no dejan libros falsos en `BOOKS/`.

## 5. EB-TEST-001 — "Productivity for Beginners" (en-US)

- Investigación con búsqueda web: 7 fuentes registradas (incluida una fuente primaria), afirmaciones etiquetadas FACT/ESTIMATE/HYPOTHESIS. Recomendación honesta: GO WITH CHANGES (nicho saturado; ángulo "sistema mínimo en un fin de semana").
- Manuscrito original de 8 capítulos y ~5.570 palabras, editado (informe con 8 cambios) y verificado: 11 afirmaciones, de las que **2 se corrigieron** (la cita de Eisenhower del discurso de 1954 estaba mal parafraseada) y **1 se eliminó** por no tener fuente.
- Portada 1600×2560 (PNG + JPG). Se corrigió un solape del aro con el título tras revisarla visualmente.
- EPUB 3 válido y PDF 6×9 de 26 páginas. El QC encontró un defecto real (página de título no centrada en el PDF) ⇒ QC_FAILED ⇒ FIX ⇒ reconstrucción ⇒ QC superado.
- Paquete: `BOOKS/EB-TEST-001/releases/v1.0/PUBLISHING_PACKAGE/` (EPUB, PDF, portada PNG/JPG, metadata.json, descripción, keywords, categorías, precio, CHECKLIST).
- ⚠️ La aprobación es **de prueba**: la ejecutó `S1-CLAUDE-001` por la instrucción del test (sección 42), no un socio. El autor sigue siendo `TBD-PEN-NAME`. **No publicar** tal cual.

## 6. Errores encontrados y corregidos durante el bootstrap

1. **Rutas virtualizadas en Windows:** `Path.resolve()` convertía la ruta en la de la caché de la app (`…\Packages\Claude_…\LocalCache\…`), invisible para Chrome. El PDF fallaba. Ahora se usa `abspath`.
2. **Reintentos quemados en un solo ciclo:** `auto` reintentaba la misma tarea fallida 3 veces seguidas. Ahora cada tarea se intenta como mucho una vez por ciclo. El sistema funcionó como se diseñó: la tarea pasó a BLOCKED, se desbloqueó con `unblock` tras arreglar la causa y continuó.
3. **Concurrencia en Windows (lo encontró la prueba de estrés):** `os.replace`/`rename` fallan con "Acceso denegado" si otro proceso lee el archivo en ese instante. Se añaden reintentos breves (`retry_io`).
4. **Archivos vacíos visibles un instante:** las tareas y los locks se creaban vacíos y se rellenaban después. Un lector podía ver un lock vacío y darlo por caducado. Ahora se crean con el contenido completo en un solo paso atómico (tmp + hard link). Un lock ilegible y reciente nunca se considera caducado.
5. Detalles: plantilla de portada (solape) y CSS de la página de título (centrado), detectados en revisión visual.

## 7. Pendiente / limitaciones conocidas

- **Sesión autónoma desatendida sin probar:** `SCRIPTS/run_worker.ps1` (`claude -p` + Programador de tareas) está escrito pero no se ha ejecutado. Hay que probarlo una vez con supervisión y ajustar los permisos de herramientas.
- **Modo multi-máquina sin activar:** el código y el test están listos, pero falta crear el repo remoto privado y poner `git.sync_enabled: true`.
- Validador EPUB propio (estructura, XHTML, enlaces, anclas, metadatos), no el oficial: instalar epubcheck (Java) antes de publicar a escala.
- Las categorías propuestas por el MARKET_AGENT son rutas plausibles, no las taxonomías oficiales de KDP: hay que confirmarlas en el formulario.
- Sin datos reales de demanda (volúmenes de búsqueda, ventas): las afirmaciones de mercado son ESTIMATE/HYPOTHESIS hasta tener una herramienta de keywords.
- PDF solo interior 6×9 sin sangrado; la portada de tapa blanda (lomo/contraportada) no está implementada.
- Métricas de coste: solo cuentan tokens si el agente los reporta (`complete --tokens`).
- Cuando haya más de 5.000 tareas terminadas conviene archivar `TASKS/DONE` por mes (no hace falta todavía).

## 8. Próximos pasos recomendados

1. **Mover el proyecto a una carpeta permanente** (ahora vive en una carpeta temporal de esta sesión).
2. Crear un **repo privado en GitHub**, añadirlo como `origin`, hacer push e invitar a Dani.
3. Decidir: **pen name**, precio por defecto, `approvals_required` (1 o 2) y el primer nicho real.
4. Probar una vez `SCRIPTS/run_worker.ps1` con supervisión y después programarlo.
5. Registrar 2–3 ideas reales (`PROMPTS/OPPORTUNITIES.md` o `book new`) con `max_active_books` bajo (3–5) hasta validar la calidad.
6. Instalar epubcheck (requiere Java) cuando vayáis a publicar.

## 9. Cómo iniciar el sistema

```bash
python factory.py doctor                     # comprobar herramientas e integridad
python factory.py status                     # qué hay en la cola
python factory.py tick --agent S1-CLAUDE-001 # recover + orquestar + tareas automáticas + informes
```
En Claude Code: *"Trabaja como agente S1-CLAUDE-001 siguiendo PROMPTS/WORKER.md"*. El agente reclama tareas una a una
hasta vaciar la cola o llegar a `max_tasks_per_session` (12).

## 10. Cómo añadir los agentes de Dani

1. Dani clona el repo privado (un clon por agente) y activa `"git": {"sync_enabled": true}` en `CONFIG/factory.json` (un solo commit compartido).
2. Registra su agente: `python factory.py agent register --id DANI-AGENT-001 --owner DANI --model <modelo> --capabilities "*"`.
   Para especializarlo: `--capabilities "EDITOR_AGENT,QC_AGENT"` (recomendado: que quien escribe no haga el QC del mismo libro).
3. Abre Claude Code en su clon: *"Trabaja como agente DANI-AGENT-001 siguiendo PROMPTS/WORKER.md"*.
   No necesita conocer ninguna conversación anterior: `CLAUDE.md` + `SYSTEM/` + el estado del repo bastan.
4. Cada comando hace commit, pull y push. Si dos máquinas reclaman la misma tarea, Git lo detecta y una de ellas cede (probado).
5. Más agentes = más registros con IDs nuevos (`DANI-AGENT-002`, …). El modelo conceptual no cambia.

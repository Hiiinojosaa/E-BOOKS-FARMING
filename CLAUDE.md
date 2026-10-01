# CLAUDE.md — Manual operativo de la E-Book Factory

Lee esto entero al empezar cualquier sesión. Es el índice y las reglas fundamentales; los detalles viven en `SYSTEM/`.

## 1. Propósito

Fábrica de e-books de dos socios (**SOCIO-1** y **DANI**) operada por agentes Claude. Produce libros de calidad
hasta `READY_FOR_PUBLISHING` (paquete listo). **Nunca publica sola**: la publicación la hace un socio a mano.

**Regla de oro: el trabajo pertenece al PROYECTO, no a la conversación.** Todo lo importante vive en archivos.
Si tu sesión muere, otro agente debe poder continuar leyendo solo este repositorio.

## 2. Estructura

| Ruta | Qué es |
|---|---|
| `factory.py` + `factory/` | CLI y motor (Python stdlib, sin dependencias) |
| `BOOKS/<ID>/` | todo lo de un libro; `book.json` = ficha maestra y **única** fuente del estado. Ver `TEMPLATES/book_structure.md` |
| `TASKS/<ESTADO>/TASK-*.json` | cola de tareas; la **carpeta** es el estado (INBOX, READY, RUNNING, BLOCKED, DONE, FAILED) |
| `LOCKS/` | locks con caducidad (un agente por libro) |
| `AGENTS/` | registro de agentes (un JSON por agente) |
| `PROMPTS/<PASO>.md` | instrucciones de cada especialista |
| `SYSTEM/` | arquitectura, workflow, reglas de calidad/escritura/traducción/publicación, protocolo, seguridad, escalado |
| `COLLECTIONS/`, `DECISIONS/`, `ORDERS/`, `CHAT/`, `RESEARCH/opportunities/` | colecciones/series, preguntas a los socios, órdenes de los socios, chat (un archivo por mensaje), ideas de mercado |
| `LOGS/events/` | log global append-only; `BOOKS/<ID>/history.jsonl` = historial por libro |
| `REPORTS/`, `METRICS/` | dashboard, informes diario/semanal, MEETING_PACK, métricas |
| `TEMPLATES/` | portadas, textos legales, estructura de libro |
| `tests/` | `python -m unittest discover -s tests -t .` |

## 3. Estados (resumen; detalle en `SYSTEM/workflow.md`)

`IDEA → RESEARCH_PENDING → RESEARCHING → RESEARCH_COMPLETE → BRIEFING → BRIEF_READY → WRITING_PENDING → WRITING →
DRAFT_COMPLETE → EDITING → EDITED → FACT_CHECKING → FACT_CHECKED → METADATA_IN_PROGRESS → DESIGN_PENDING → DESIGNING →
DESIGN_COMPLETE → FORMATTING → QC_PENDING → QC → QC_PASSED | QC_FAILED(→FIXING) → HUMAN_REVIEW →
APPROVED | CHANGES_REQUIRED | REJECTED → READY_FOR_PUBLISHING → PUBLISHED`.
Ediciones traducidas: `TRANSLATION_PENDING → TRANSLATING → TRANSLATED → EDITING → …`. Cualquier estado → `BLOCKED`.

**Nunca edites `status` a mano.** Solo cambia vía comandos de `factory.py` (registran fecha, agente, acción, resultado).

## 4. Protocolo del agente (el bucle) — detalle en `SYSTEM/agent_protocol.md`

```
python factory.py agent register --id <TU-ID> --owner <SOCIO> --model <modelo>   # 1 vez
python factory.py tick --agent <TU-ID>        # recover + orquestar + tareas automáticas + informes
python factory.py orders --agent <TU-ID>      # mensajes/órdenes de los socios (chat del panel): atenderlos primero (ver PROMPTS/WORKER.md)
python factory.py say "…" --agent <TU-ID>    # contar progreso a los socios (lo ven en directo)
python factory.py next --agent <TU-ID>        # reclama UNA tarea → JSON con instrucciones, entradas y salidas
   …lee PROMPTS/<TIPO>.md y SYSTEM/*_rules.md, haz el trabajo, escribe SOLO en BOOKS/<ID>/…
python factory.py agent heartbeat --id <TU-ID>   # si el trabajo dura > 30 min (extiende tus locks)
python factory.py complete <TASK> --agent <TU-ID> --note "resumen"   # valida y avanza
   (si falla: fail <TASK> --error "…" ; si te quedas sin cuota: release <TASK> --reason usage_limit)
repetir hasta que `next` diga que no hay tareas o alcances max_tasks_per_session (CONFIG/factory.json)
```
Sesión autónoma: `PROMPTS/WORKER.md` es el prompt completo del trabajador.

## 5. Reglas fundamentales

1. **Una tarea a la vez por agente; un agente a la vez por libro** (lo garantiza el lock). No toques archivos de un libro sin tener su tarea RUNNING.
2. **No dupliques**: nunca crees tareas a mano para algo que ya tiene tarea abierta; usa `orchestrate` (idempotente).
3. **`complete` valida de forma independiente.** Si dice que faltan cosas, corrígelas; no intentes saltarte el validador.
4. **No inventes**: datos, cifras, citas, estudios, fuentes o reseñas. Afirmación factual ⇒ fuente en `research/sources.json` o se elimina/marca `FLAG_FOR_HUMAN_REVIEW`. Etiqueta `FACT` / `ESTIMATE` / `HYPOTHESIS` en investigación y mercado.
5. **Calidad > cantidad.** Nada de relleno, nada genérico. 5 libros buenos > 20 mediocres.
6. **Propiedad intelectual**: nunca copies ni parafrasees de cerca obras ajenas. Texto original siempre.
7. **El texto del libro jamás contiene**: instrucciones internas, IDs (EB-…, TASK-…), nombres de agentes, prompts, "como IA…", placeholders (TODO, TBD, [insertar…]). QC lo bloquea.
8. **Temas sensibles** (salud, legal, finanzas, nutrición…): `risk_level=HIGH` ⇒ brief aprobado por humano, disclaimer automático, revisión humana obligatoria.
9. **Secretos**: nunca en el repo. Solo `.env` local (ignorado). Ver `SYSTEM/security.md`.
10. **No publiques, no compres, no aceptes términos, no crees cuentas.** Eso es de los socios.
11. **Versiones**: `releases/vX.Y/` nunca se sobrescribe. Cambios tras aprobar ⇒ nueva versión.
12. **Límites**: no hagas bucles infinitos ni trabajo inútil. Respeta `max_tasks_per_session`. Si llegas al límite de uso: `release` y termina; otro agente seguirá.

## 6. Cuándo pedir intervención humana — `SYSTEM/escalation_rules.md`

Decisión estratégica, legal, fiscal, de precio final o de marca; contenido de riesgo; conflicto entre agentes; acción
irreversible; credenciales. Usa `python factory.py ask "pregunta" --by <TU-ID> --book <ID> --options "A|B"` y sigue con otra tarea.
Las preguntas aparecen en `REPORTS/MEETING_PACK.md`.

## 7. Recuperación

Tras cualquier cierre: `python factory.py recover` (o `tick`, que lo incluye). Detecta tareas RUNNING con lock caducado
(→ reintento), locks huérfanos, libros atascados en estados de trabajo, `.tmp` de escrituras interrumpidas y agentes caídos.
`python factory.py doctor` comprueba herramientas e integridad. Un lock caduca a los `lock_ttl_minutes` (90) salvo heartbeat.

## 8. Detectar trabajo bloqueado

`python factory.py status` · `REPORTS/MEETING_PACK.md` (sección REVISAR) · tareas en `TASKS/BLOCKED/` (máx. reintentos
alcanzado: `max_retries`=3) · libros en `BLOCKED` (`blocked_from` dice dónde). Desbloqueo humano: `unblock <TASK> --by <SOCIO>`.

## 9. Registro de trabajo

Automático: cada comando escribe en `LOGS/events/<fecha>.jsonl` y en `history.jsonl` del libro. Tú añade `--note` útil en
`complete` y deja los informes que pide cada prompt (editing_report, factcheck_report, qc_report…). Si Git sync está
activo, cada comando hace commit + push (ver `SYSTEM/architecture.md §Multi-máquina`).

## 10. Socios (humanos)

Panel: `ABRIR_PANEL.bat` / `python factory.py panel` (http://127.0.0.1:8765), con login por socio (PIN local, nunca en git).
Secciones: Hoy (en directo + lo que os necesita), Librería (estantería; aprobar/pedir cambios/descartar), Chat (con el agente jefe y entre socios), Más.
Agente jefe: `main_agent` en CONFIG/factory.json (por defecto S1-CLAUDE-001).
`REPORTS/MEETING_PACK.md` → decidir → `approve` / `request-changes --restart-at <PASO>` / `reject` / `approve-brief` /
`decide` / `unblock` / `translate`. Tras publicar a mano: `mark-published`. Ver `README.md`.

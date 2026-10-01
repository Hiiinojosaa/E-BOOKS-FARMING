# Workflow y máquina de estados

Fuente de verdad del código: `factory/states.py`. Cada paso: `from_state --claim--> working --complete--> done`.
Si falla o se libera, el libro vuelve al `from_state`. Toda transición queda en `history.jsonl` (fecha, agente, acción, resultado).

| Paso | Desde | Trabajando | Hecho | Rol | Salidas obligatorias (BOOKS/<ID>/) |
|---|---|---|---|---|---|
| (gate) | IDEA | — | RESEARCH_PENDING | ORCHESTRATOR | respeta `max_active_books` y prioridad |
| RESEARCH | RESEARCH_PENDING | RESEARCHING | RESEARCH_COMPLETE | RESEARCH | research/research.md, research/sources.json |
| BRIEF | RESEARCH_COMPLETE | BRIEFING | BRIEF_READY | RESEARCH | brief.md |
| (gate) | BRIEF_READY | — | WRITING_PENDING | ORCHESTRATOR / socio | auto si riesgo LOW y `brief_approval=auto`; si no, `approve-brief` |
| WRITE | WRITING_PENDING | WRITING | DRAFT_COMPLETE | WRITER | manuscript/draft.md |
| TRANSLATE | TRANSLATION_PENDING | TRANSLATING | TRANSLATED | TRANSLATOR | manuscript/draft.md, reports/translation_notes.md |
| EDIT | DRAFT_COMPLETE, TRANSLATED | EDITING | EDITED | EDITOR | manuscript/edited.md, reports/editing_report.md |
| FACT_CHECK | EDITED | FACT_CHECKING | FACT_CHECKED | FACT_CHECK | manuscript/final.md, reports/factcheck_report.md |
| METADATA | FACT_CHECKED | METADATA_IN_PROGRESS | DESIGN_PENDING | MARKET | metadata/metadata.json |
| DESIGN | DESIGN_PENDING | DESIGNING | DESIGN_COMPLETE | DESIGN | design/design.json + `cover` ⇒ design/cover.png |
| FORMAT (auto) | DESIGN_COMPLETE | FORMATTING | QC_PENDING | FORMAT | build/*.epub, build/*.pdf |
| QC | QC_PENDING | QC | QC_PASSED / QC_FAILED | QC | reports/qc_report.md (+ QC automático re-ejecutado por `complete`) |
| FIX | QC_FAILED | FIXING | DESIGN_COMPLETE | EDITOR | reports/fix_report.md (+ correcciones) ⇒ vuelve a FORMAT y QC |
| (gate) | QC_PASSED | — | HUMAN_REVIEW | ORCHESTRATOR | genera review/HUMAN_REVIEW.md |
| (socio) | HUMAN_REVIEW | — | APPROVED / CHANGES_REQUIRED / REJECTED | humano | `approve` / `request-changes --restart-at PASO` / `reject` |
| (auto) | APPROVED | — | READY_FOR_PUBLISHING | PUBLISHING_PREP | releases/vX.Y/PUBLISHING_PACKAGE |
| (socio) | READY_FOR_PUBLISHING | — | PUBLISHED | humano | `mark-published` tras subirlo a mano |

**Traducciones:** si `target_languages` tiene idiomas, al pasar FACT_CHECKED el orquestador crea un libro hijo por idioma
(`translated_from`, `parent_book`) en TRANSLATION_PENDING. También a mano: `python factory.py translate <ID> --to es`.

**QC_FAILED** más de `max_qc_failures` (2) veces ⇒ BLOCKED para humanos.
**Fallo de tarea**: reintento hasta `max_retries` (3); después la tarea va a `TASKS/BLOCKED` y el libro a BLOCKED.
**Release** (cuota agotada, interrupción voluntaria) no cuenta como reintento.

## Prioridades
`CRITICAL > HIGH > NORMAL > LOW`, luego antigüedad. Cambiar: `python factory.py book set <ID> priority=HIGH`.

## Colecciones / series / bundles
`python factory.py collection create CHRISTMAS-2026 --type collection --season 2026-12 --name "Christmas 2026"`
`python factory.py collection add CHRISTMAS-2026 EB-000004`. El DESIGN_AGENT reutiliza plantilla y paleta de la colección.

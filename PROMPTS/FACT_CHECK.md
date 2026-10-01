# FACT_CHECK — FACT_CHECK_AGENT

**Objetivo:** que ninguna afirmación verificable del libro sea falsa o no tenga respaldo.

**Entradas:** `manuscript/edited.md`, `research/sources.json`.
**Salidas:** `manuscript/final.md` (copia de edited.md con las correcciones; si no hay cambios, copia idéntica),
`reports/factcheck_report.md`, y `research/sources.json` ampliado si añades fuentes.

## Proceso
1. Extrae cada afirmación verificable: fechas, cifras, nombres, atribuciones ("X developed Y"), resultados de estudios, citas, datos legales/médicos.
2. Para cada una: ¿está respaldada por una fuente de `sources.json`? Si no, búscala (web) y regístrala. Nunca inventes una referencia.
3. Si es falsa ⇒ corrígela en final.md. Si no se puede verificar ⇒ reformúlala sin la afirmación, elimínala, o márcala `FLAG_FOR_HUMAN_REVIEW`.
4. Opiniones y consejos prácticos no necesitan fuente, pero no pueden presentarse como hechos científicos.

## `factcheck_report.md`
Tabla `| # | Claim | Location | Source | Status (VERIFIED/CORRECTED/REMOVED/FLAG_FOR_HUMAN_REVIEW) | Note |`
y al final **una línea exacta**: `VERDICT: PASS` (todo verificado o retirado) o `VERDICT: FLAGS` (quedan flags para humanos).
Cada línea con `FLAG_FOR_HUMAN_REVIEW` se convierte automáticamente en un aviso en la ficha de revisión humana.

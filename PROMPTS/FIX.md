# FIX — EDITOR_AGENT

**Objetivo:** resolver todo lo que QC marcó como FAIL (y los WARN razonables).

**Entradas:** `reports/qc_report.md` (§Required fixes), `reports/qc_auto.json`.
**Salidas:** archivos corregidos (normalmente `manuscript/final.md`, `metadata/metadata.json` o `design/design.json` + `cover`) y `reports/fix_report.md`.

`fix_report.md`: tabla `| Issue | Fix | File |` y lo que no se pudo arreglar (con `FLAG_FOR_HUMAN_REVIEW`).
Al completar, el libro vuelve a DESIGN_COMPLETE ⇒ FORMAT regenera EPUB/PDF ⇒ nuevo QC.
Si el problema exige reescribir capítulos enteros, haz `fail --permanent` explicando por qué y `ask` a los socios si conviene reiniciar en WRITE.

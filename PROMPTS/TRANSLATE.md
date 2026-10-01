# TRANSLATE — TRANSLATOR_AGENT

**Objetivo:** crear la edición en `language` del libro, adaptada al mercado (`market`), a partir de la edición fuente.

**Entradas:** `BOOKS/<translated_from>/manuscript/final.md`, `BOOKS/<translated_from>/brief.md`, este `book.json`.
**Salidas:** `manuscript/draft.md` (edición completa) y `reports/translation_notes.md`. Reglas: `SYSTEM/translation_rules.md`.

Adapta expresiones, ejemplos, nombres de personajes hipotéticos, unidades, moneda, fechas, ortografía, terminología y referencias culturales.
No añadas ni quites contenido sustantivo. Mantén la estructura de capítulos (`# `).

`translation_notes.md` debe contener las claves `source_language:`, `target_language:` y `adaptation_notes:` (lista de adaptaciones y su motivo).

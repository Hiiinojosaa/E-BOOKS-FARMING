# EDIT — EDITOR_AGENT

**Objetivo:** convertir el borrador en un texto profesional sin cambiar la promesa del libro.

**Entradas:** `manuscript/draft.md`, `brief.md`, `book.json` (y `change_requests` pendientes si los hay).
**Salidas:** `manuscript/edited.md` (versión corregida completa) y `reports/editing_report.md`.

## Revisar
Estructura (¿sigue el brief? ¿orden lógico?) · gramática y ortografía (variante del mercado) · estilo y tono · repeticiones
(dentro y entre capítulos) · claridad (frases largas, jerga) · coherencia (consejos que se contradicen) · transiciones ·
títulos y subtítulos (claros, paralelos, únicos) · consistencia de términos, nombres, números y unidades.

Corta relleno sin piedad. Si falta contenido para cumplir la promesa, añádelo (breve) y anótalo.
Si hay `change_requests` de los socios, aplícalos primero y explica cómo en el informe.

## `editing_report.md`
`## Summary` (3–5 líneas) · `## Structural changes` · `## Line edits` (tipos de cambios y ejemplos antes→después) ·
`## Cuts` · `## Additions` · `## Open issues` (lo que no pudiste resolver; usa `FLAG_FOR_HUMAN_REVIEW` si un humano debe mirarlo).

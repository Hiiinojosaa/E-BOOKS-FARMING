# QC Report — EB-000005 v1.0
**Fecha:** 2026-10-09 · **Agente:** S1-JEFE · **Tarea:** TASK-000076

---

## Automatic checks

24/24 PASS tras dos correcciones aplicadas en este ciclo de QC:
1. El manuscrito tenía el título del libro como `# H1` (primera línea), lo que generaba un "capítulo" de 9 palabras. Se eliminó ese H1 — el EPUB ya genera la página de título desde los metadatos.
2. La conclusión tenía ~137 palabras (umbral 150). Se añadió un párrafo de cierre natural (aconseja anotar aprendizajes post-evento). Ahora tiene ~200 palabras.

Rebuild ejecutado tras cada corrección. Resultado final: 27 páginas, 9 capítulos, 4231 palabras.

---

## Content

**PASS** — La promesa del título se cumple: el libro entrega el método del cronograma inverso, checklists por tipo de evento y sistema de delegación. Los 7 tipos de evento cubiertos (bodas, fiestas familiares, grupos, mudanzas, viajes, el día del evento, conclusión) coinciden con la descripción del producto.

Cada capítulo aporta algo accionable (checklists con plazos concretos, reglas de decisión, ejemplos prácticos). Sin capítulos puente ni relleno genérico.

El nivel de detalle es apropiado para 4231 palabras: formato planner/checklist con tablas y listas ocupa menos palabras que prosa narrativa. No hay `word_count_target` fijado en el brief; la longitud es coherente con el género.

---

## Language

**PASS** — Idioma detectado: es. Español neutro con referencias específicas al mercado español (AEAT, DGT, Seguridad Social en el capítulo de mudanzas). El tono es directo, práctico y consistente en todos los capítulos. Sin repeticiones de palabras, sin dobles espacios.

---

## Format

**PASS** — EPUB válido: 13 documentos, 26 enlaces internos, sin advertencias. PDF: 27 páginas. Portada: 1600×2560 px. Todos los formatos correctos.

---

## Metadata

**PASS** — Título, subtítulo, autor, idioma (es-ES), 7 keywords (≤50 caracteres c/u), 3 categorías de Kindle ES correctas. Descripción: 1673 caracteres. Sin texto interno.

---

## Consistency

**PASS** — Título EPUB coincide con metadatos y book.json. Sin fact-check flags abiertos. Sin IDs internos, placeholders ni referencias a agentes en el texto. Los claims factuales son de nivel ESTIMATE (plazos de reserva, distribución presupuestaria) sin cifras precisas que requieran fuente.

La nota sobre DGT en el capítulo de mudanzas incluye correctamente la advertencia de variabilidad normativa.

---

## Required fixes

Ninguno. Las dos correcciones de este ciclo ya están aplicadas y el QC automático pasa 24/24.

---

VERDICT: PASS

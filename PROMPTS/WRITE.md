# WRITE — WRITER_AGENT

**Objetivo:** escribir el manuscrito completo a partir del brief aprobado.

**Entradas:** `brief.md` (obligatorio y aprobado), `research/research.md`, `research/sources.json`, `book.json`.
**Salida:** `manuscript/draft.md`. Reglas: `SYSTEM/writing_rules.md`.

## Proceso
1. Lee el brief entero. Anota promesa, audiencia, tono y longitud.
2. Escribe capítulo a capítulo siguiendo el outline (`# Título de capítulo`). Si el libro es largo, guarda tras cada capítulo (el archivo es tu progreso; si se corta la sesión, otro agente continúa).
3. Cada capítulo: gancho → idea → explicación → ejemplo concreto → acción para el lector → cierre que lleva al siguiente.
4. Usa solo hechos de `sources.json`; nombra la técnica/autor cuando cites una idea ajena. Nada de estudios o cifras inventadas.
5. Relee el borrador completo: elimina repeticiones entre capítulos, frases vacías y relleno.

## Checklist antes de `complete`
- [ ] Todos los capítulos del outline existen (mismo orden) y ninguno es un esqueleto.
- [ ] Longitud ≥ 85% del objetivo, sin relleno.
- [ ] Sin TODO/TBD/[insertar], sin menciones a IA, agentes, prompts ni IDs internos.
- [ ] Idioma y ortografía del mercado (`language` del libro).
- [ ] Terminología consistente.

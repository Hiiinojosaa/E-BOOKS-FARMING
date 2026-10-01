# Cuándo escalar a los socios

Escalar con `python factory.py ask "pregunta concreta" --by <AGENTE> --book <ID> --options "A|B|C"` y **seguir con otra tarea**
(no esperar). La pregunta aparece en `REPORTS/MEETING_PACK.md`; el socio responde con `decide`.

| Situación | Acción |
|---|---|
| Decisión estratégica (nicho nuevo, colección, precio final, pen name, idiomas) | `ask` |
| Tema legal, fiscal, médico, financiero, nutricional | `risk_level=HIGH`; el brief requiere `approve-brief`; HUMAN_REVIEW obligatorio |
| Afirmación factual no verificable | `FLAG_FOR_HUMAN_REVIEW` en factcheck_report (o eliminarla) |
| Riesgo de copyright o marca registrada en el título | `ask` antes de seguir con ese libro |
| Conflicto entre agentes / sync Git sin resolver | `fail --permanent` + `ask` |
| Falta herramienta o credencial | `fail --permanent` explicando qué falta; nunca fingir que existe |
| Tarea fallida 3 veces | automático ⇒ BLOCKED |
| QC_FAILED 3 veces | automático ⇒ BLOCKED |
| Acción irreversible (borrar libros, publicar, reescribir una release) | solo socios |

No escalar lo que se puede decidir con las reglas: sinónimos, orden de secciones, erratas, paleta de color.

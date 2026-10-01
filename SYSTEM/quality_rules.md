# Reglas de calidad

Principio: **VELOCIDAD + CALIDAD + CONSISTENCIA**. Si hay que elegir, calidad.

## Controles automáticos (no se pueden saltar)
- `complete` valida el contrato de salidas de cada paso (`factory/validators.py`): archivos, secciones, longitud, sin placeholders, sin referencias internas.
- QC automático (`factory/qc.py`), re-ejecutado por `complete` del paso QC aunque el agente diga PASS:

| Categoría | Controles |
|---|---|
| CONTENIDO | nº capítulos ≥ outline del brief · capítulos ≥150 palabras · longitud ≥60% objetivo (WARN <85%) · sin placeholders (TODO, TBD, [insert…], {{…}}) · sin instrucciones/prompts/agentes/IDs internos · sin párrafos duplicados · títulos de capítulo únicos |
| IDIOMA | idioma detectado = idioma del libro · palabras repetidas ("the the") · ortografía US vs UK · dobles espacios |
| FORMATO | EPUB válido (estructura, XHTML bien formado, manifest, spine, nav, enlaces y anclas) · PDF y nº páginas · portada ≥1600×2560, ratio 1.6 · JPG de portada · numeración de capítulos |
| METADATOS | título, subtítulo, autor (provisional ⇒ HUMAN_REVIEW), idioma, 1–7 keywords ≤50 caracteres, 1–3 categorías, descripción 300–4000 caracteres, sin texto interno |
| CONSISTENCIA | título EPUB = metadatos = book.json · flags abiertos del fact-check ⇒ HUMAN_REVIEW |
| RIESGO | `risk_level=HIGH` ⇒ HUMAN_REVIEW siempre |

Resultado: `FAIL` > `HUMAN_REVIEW` > `WARN` > `PASS`. FAIL ⇒ QC_FAILED ⇒ tarea FIX.

## Revisión del QC_AGENT (LLM), además del script
Leer el libro entero buscando lo que un script no ve: promesa del título cumplida, consejos contradictorios, tono,
claridad, errores factuales obvios, ejemplos irreales, frases genéricas de relleno, sesgos, contenido inapropiado,
coherencia de nombres/fechas/números/unidades entre capítulos.

## Umbrales de contenido
- Cada capítulo debe aportar algo accionable o una idea nueva; nada de capítulos "puente".
- Ejemplos concretos > generalidades. Ninguna cifra sin fuente.
- Longitud objetivo por defecto 6.000 palabras (ebook corto); el brief puede fijar otra.

# Reglas de traducción / adaptación

- Cada edición es un **libro propio** (ID nuevo) con `translated_from` y `parent_book`. Fuente: `BOOKS/<translated_from>/manuscript/final.md`.
- **Adaptar, no calcar**: expresiones idiomáticas, ejemplos culturales (nombres, fiestas, deportes, instituciones), unidades, moneda, formatos de fecha, ortografía, terminología del sector en ese mercado.
- en-US ⇒ inglés estadounidense. en-GB ⇒ inglés británico. es-ES ⇒ español de España (es-MX si se pide México).
- No añadir ni quitar contenido sustantivo. Si algo no tiene sentido en el mercado destino, adaptarlo y anotarlo.
- Títulos y keywords **no se traducen literalmente**: los rehace el MARKET_AGENT en el paso METADATA de la edición.
- `reports/translation_notes.md` obligatorio con:

```
source_language: en-US
target_language: es-ES
adaptation_notes:
- ejemplo "Thanksgiving" → "Navidad", porque…
- unidades: millas → km
```

- Después de TRANSLATE la edición pasa por EDIT (editor nativo del idioma), FACT_CHECK, METADATA, DESIGN, FORMAT y QC como cualquier libro.

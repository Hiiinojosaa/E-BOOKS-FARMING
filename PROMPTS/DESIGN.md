# DESIGN — DESIGN_AGENT

**Objetivo:** portada legible en miniatura y coherente con la colección; interior limpio (el interior lo genera FORMAT con estilos comunes).

**Entradas:** `metadata/metadata.json`, `book.json` (collections), `COLLECTIONS/<id>.json` (si tiene diseño fijado), `TEMPLATES/covers/*.html`.
**Salidas:** `design/design.json` y `design/cover.png` (+ `cover.jpg`) generados con `python factory.py cover <BOOK_ID>`.

```json
{
  "template": "minimal",            // minimal | stack (añadir plantillas nuevas en TEMPLATES/covers/)
  "title_line1": "Productivity",    // reparte el título en 1–2 líneas cortas (≤ 12 caracteres por línea si es posible)
  "title_line2": "for Beginners",
  "tagline": "A starter guide",     // ≤ 30 caracteres, opcional
  "badge": "",                      // solo plantilla stack
  "palette": {"bg": "#…", "fg": "#…", "accent": "#…", "muted": "#…"},
  "rationale": "por qué esta paleta/plantilla para este público"
}
```

Reglas: contraste alto (texto legible en miniatura de 150 px de ancho), máximo 2 colores + neutros, sin imágenes de stock
de terceros ni marcas ajenas. Si el libro pertenece a una colección con diseño fijado, usa su plantilla y paleta.
Tras ejecutar `cover`, **abre `design/cover.png` y míralo**: si el título se corta o solapa, ajusta líneas/tamaños y repite.

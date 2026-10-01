# Imágenes reales en el interior de un libro

Cualquier libro puede llevar fotos/ilustraciones reales (pasos de receta, posturas de fitness,
diagramas...), no placeholders ni descripciones en texto de "aquí iría una foto". El pipeline de
maquetación (`build.py`) ya soporta imágenes embebidas tanto en EPUB como en PDF: una línea de
markdown sola en su propio párrafo,

```
![Paso 1: sofríe la cebolla a fuego medio](design/photos/receta-01-paso-01.png)
```

se embebe automáticamente (ver `build.md_to_xhtml`'s `img_resolver`) — en el EPUB se empaqueta
dentro del zip, en el PDF se referencia relativo a `build/interior.html`. Es exactamente el mismo
mecanismo que usan los libros de puzzles (`SYSTEM/puzzle_books.md`), así que no hace falta nada
especial en `build.py`/`validators.py` para usarlo en un libro de texto normal.

## Generar la imagen

```
python factory.py image "descripción detallada y específica de la escena" BOOKS/<ID>/design/photos/<nombre>.png --aspect 4:3
```

Usa Google Imagen (vía Gemini API). Necesita `GEMINI_API_KEY` en `.env` (nunca en el repo).
`--aspect` acepta `1:1`, `16:9`, `9:16`, `4:3`, `3:4` — para fotos de recetas en un libro
apaisado-ish usa `4:3` o `3:4`, para ilustraciones de portada-ish usa lo que pida el diseño.

## Reglas al escribir el prompt (paso WRITE)

- Describe la escena concreta y específica del paso/sección del libro (qué se ve, ángulo, luz),
  nunca una persona real identificable ni una marca. Fotorrealista para recetas/fitness,
  ilustración para libros infantiles/de coloring, según pida el brief.
- Una imagen por paso/concepto real del contenido — nunca como relleno decorativo. Si un capítulo
  no tiene nada que mostrar, no le metas una imagen porque sí.
- Genera primero, mira el resultado (el agente puede leer el PNG igual que cualquier archivo) y
  solo entonces referencia la ruta en el manuscrito — nunca inventes una ruta de archivo que no
  has generado.
- Guarda las imágenes en `design/photos/` dentro del libro (`design/puzzles/` ya está reservado
  para los libros de puzzles).

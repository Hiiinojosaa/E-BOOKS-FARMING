# Checklist de publicación manual — EB-TEST-001 v1.0

> La fábrica NO publica automáticamente. Un socio sube estos archivos a mano.

- [ ] Revisar `description.md`, `keywords.txt`, `categories.txt` y `metadata.json`
- [ ] Confirmar nombre de autor / pen name: **TBD-PEN-NAME**
- [ ] Confirmar precio: **2.99 USD**
- [ ] Ebook: subir `EB-TEST-001_productivity-for-beginners_v1.0.epub` (el marketplace lo convertirá) y `cover.jpg`/`cover.png`
- [ ] Revisar la previsualización del marketplace (índice, portada, saltos de capítulo)
- [ ] Marcar contenido generado con IA si el marketplace lo pide (KDP lo pregunta en el formulario)
- [ ] Derechos territoriales, DRM, royalties: decisión de los socios
- [ ] Tras publicar: `python factory.py mark-published EB-TEST-001 --by <SOCIO> --platform KDP --url <URL>`

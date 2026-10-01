# FORMAT — FORMAT_AGENT (automático)

Lo ejecuta el script en `tick`/`auto`: `python factory.py build <BOOK_ID>`.

Genera en `build/`: EPUB 3 (portada, página de título, copyright, índice navegable, capítulos, metadatos OPF) validado
estructuralmente, y PDF 6×9 in (Chrome headless) con numeración de páginas. Un agente solo interviene si la tarea falla:
leer el error, corregir la causa en el manuscrito/metadatos/diseño (con una tarea FIX o pidiéndolo con `ask`) y no tocar el código salvo que sea un bug.

Pendiente (opcional): epubcheck oficial (requiere Java), MOBI/AZW3 vía Calibre (KDP ya acepta EPUB), PDF de tapa blanda con sangrado.

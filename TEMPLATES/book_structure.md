# Estructura de carpetas de un libro (BOOKS/<ID>/)

```
book.json                 ficha maestra (único sitio con el estado)
history.jsonl             transiciones de estado (append-only)
brief.md                  brief aprobado (BRIEF)
research/research.md      investigación con etiquetas FACT / ESTIMATE / HYPOTHESIS
research/sources.json     fuentes [{id,title,url|citation,accessed,used_for}]
manuscript/draft.md       WRITE o TRANSLATE
manuscript/edited.md      EDIT
manuscript/final.md       FACT_CHECK (texto que se maqueta)
reports/                  editing_report.md, factcheck_report.md, translation_notes.md,
                          qc_auto.json/.md, qc_report.md, fix_report.md
metadata/metadata.json    título, subtítulo, descripción, keywords, categorías, precio
design/design.json        plantilla + paleta + líneas de título → design/cover.png/.jpg
build/                    EPUB + PDF generados (FORMAT, automático)
review/HUMAN_REVIEW.md    ficha para los socios
releases/vX.Y/            snapshot inmutable + PUBLISHING_PACKAGE/
```

Formato del manuscrito: Markdown. `# ` = capítulo (incluye Introducción y Conclusión).
`##`/`###` = secciones. Listas `-`/`1.`, checklists `- [ ]`, citas `>`, separador `---`.
Sin portada/créditos/índice: los genera FORMAT.

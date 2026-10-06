# MEETING PACK — 2026-10-06

> Solo lo que requiere decisión de los socios.

## APROBAR (listos, QC superado)

- **EB-000001** — The One-Page System (en-US) · QC WARN · 21 págs · precio sugerido 3.99 → `BOOKS/EB-000001/review/HUMAN_REVIEW.md`
- **EB-000009** — Navidad en la Mesa: 50 Recetas Españolas y 5 Menús Completos para Toda la Temporada (es-ES) · QC PASS · 51 págs · precio sugerido 2.99 → `BOOKS/EB-000009/review/HUMAN_REVIEW.md`
- **EB-000015** — Large Print Sudoku for Seniors (en-US) · QC PASS · 27 págs · precio sugerido 6.99 → `BOOKS/EB-000015/review/HUMAN_REVIEW.md`

## REVISAR (bloqueados o esperando a un humano)

- **EB-000002** — Los 200 Mejores Prompts de IA para Trabajar Menos y Rendir Más: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000003** — Tu Primer Año de Orden Financiero: Guía y Planner Completo: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000004** — Diario de Autoconocimiento: 100 Preguntas para Conocerte y Reordenar tu Vida: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000005** — El Planner Definitivo de Eventos: Organiza Cualquier Celebracion sin Estres: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)

## DESCARTAR (candidatos)

- Nada

## DECISIONES

- EB-000001: ¿crear versiones es-ES, en-GB? (`python factory.py translate EB-000001 --to <lang>`)
- EB-000009: ¿crear versiones en-US, en-GB? (`python factory.py translate EB-000009 --to <lang>`)
- EB-000015: ¿crear versiones es-ES, en-GB? (`python factory.py translate EB-000015 --to <lang>`)
- EB-TEST-001: ¿crear versiones es-ES, en-GB? (`python factory.py translate EB-TEST-001 --to <lang>`)
- DEC-00001: Te recomiendo «New Year 2027 Goal Planner & Annual Review Journal» (en-US). Q4 pico: los planners anuales dominan el top de ventas KDP en noviembre-diciembre. Nicho validado con el Sudoku y la productividad en inglés. Bajo riesgo, alta demanda recurrente. Complementa EB-TEST-001 (productividad) y diversifica hacia inglés. Opciones: Adelante, Descartar (`python factory.py decide DEC-00001 --by <SOCIO> --answer "..."`)
- DEC-00002: Te recomiendo «Thanksgiving Recipes & Holiday Menu Planner» (en-US). Nicho estacional de alta conversión en KDP (octubre-noviembre). El recetario navideño español (EB-000009) ya pasó QC con éxito — mismo formato probado aplicado al mercado anglófono para Thanksgiving. Ventana corta pero pico de ventas muy alto. Opciones: Adelante, Descartar (`python factory.py decide DEC-00002 --by <SOCIO> --answer "..."`)
- DEC-00003: Te recomiendo «Large Print Word Search for Seniors: 100 Puzzles» (en-US). Mismo nicho que EB-000015 (Sudoku seniors, QC PASS). Los libros de puzzles para mayores son un bestseller perenne en KDP, con poca escritura requerida y alta cadencia de ventas. Diversifica el catálogo de puzzles en inglés. Opciones: Adelante, Descartar (`python factory.py decide DEC-00003 --by <SOCIO> --answer "..."`)
- DEC-00004: Te recomiendo «30-Day Morning Routine Challenge: Journal & Tracker» (en-US). Nicho evergreen de journals/hábitos que complementa la productividad (EB-TEST-001, EB-000001) y los diarios (EB-000004). Alta demanda constante en KDP, bajo coste de producción. Formato probado: tracker diario + reflexiones. Opciones: Adelante, Descartar (`python factory.py decide DEC-00004 --by <SOCIO> --answer "..."`)
- DEC-00005: Te recomiendo «Guía Completa de ChatGPT y IA Generativa para No Técnicos» (es-ES). Complementa EB-000002 (prompts de IA) con un enfoque tutorial/guía práctica. Demanda altísima en español: muchos lectores quieren entender y usar la IA sin conocimientos técnicos. Nicho en expansión rápida, baja competencia de calidad en es-ES. Opciones: Adelante, Descartar (`python factory.py decide DEC-00005 --by <SOCIO> --answer "..."`)

## Estado de la fábrica

TOTAL BOOKS: 21 · IDEAS: 13 · RESEARCH: 4 · HUMAN REVIEW: 3 · READY TO PUBLISH: 1


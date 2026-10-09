# MEETING PACK — 2026-10-09

> Solo lo que requiere decisión de los socios.

## APROBAR (listos, QC superado)

- **EB-000001** — The One-Page System (en-US) · QC WARN · 21 págs · precio sugerido 3.99 → `BOOKS/EB-000001/review/HUMAN_REVIEW.md`
- **EB-000009** — Navidad en la Mesa: 50 Recetas Españolas y 5 Menús Completos para Toda la Temporada (es-ES) · QC PASS · 51 págs · precio sugerido 2.99 → `BOOKS/EB-000009/review/HUMAN_REVIEW.md`
- **EB-000015** — Large Print Sudoku for Seniors (en-US) · QC PASS · 27 págs · precio sugerido 6.99 → `BOOKS/EB-000015/review/HUMAN_REVIEW.md`

## REVISAR (bloqueados o esperando a un humano)

- **EB-000002** — Los 200 Mejores Prompts de IA para Trabajar Menos y Rendir Más: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000010** — Diciembre en Familia: Calendario de Adviento, Actividades y Recuerdos: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000011** — Guia de Regalos de Navidad: Ideas para Todos sin Gastar de Mas: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000012** — Cierra el Año y Diseña el Siguiente: Guia de Revision y Metas: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)
- **EB-000014** — Hanukkah en Familia: Actividades, Recetas y Tradiciones: brief de riesgo ALTO pendiente de aprobar (`approve-brief`)

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
- DEC-00006: Te recomiendo «Christmas Activity Book for Kids: Coloring, Puzzles and Fun» (en-US). FACT: Q4 is the strongest KDP season; children's activity books peak in November-December. FACT: Our adult puzzle catalog (Sudoku EB-000015, Word Search EB-000018 pending) is proven but lacks a kids format. ESTIMATE: Children's activity books have lower production cost and high gifting volume. Fills the kids niche with seasonal timing. Opciones: Adelante, Descartar (`python factory.py decide DEC-00006 --by <SOCIO> --answer "..."`)
- DEC-00007: Te recomiendo «Meal Prep and Healthy Eating Weekly Planner» (en-US). FACT: Health and wellness planners are a top KDP evergreen category with a strong January peak from New Year resolutions. ESTIMATE: Pairs well with New Year 2027 Planner (DEC-00001) as a companion product — cross-sell opportunity. HYPOTHESIS: Buyers of productivity tools often also buy meal/health planners. Low risk, proven format, year-round demand. Opciones: Adelante, Descartar (`python factory.py decide DEC-00007 --by <SOCIO> --answer "..."`)
- DEC-00008: Te recomiendo «Mi Libro de Recetas: Cuaderno Personal de Cocina en Blanco» (es-ES). FACT: Blank recipe journals are perennial bestsellers on KDP Spain and Latin America with year-round demand, especially as gifts. FACT: Our Spanish catalog is growing but lacks a cookbook format. ESTIMATE: Low production complexity as a fill-in journal template — no editorial writing required. Distinct from EB-000009 which is an editorial recipe book. Opciones: Adelante, Descartar (`python factory.py decide DEC-00008 --by <SOCIO> --answer "..."`)

## Estado de la fábrica

TOTAL BOOKS: 25 · IDEAS: 12 · RESEARCH: 5 · WRITING: 2 · EDITING: 1 · HUMAN REVIEW: 3 · READY TO PUBLISH: 1 · FAILED: 1


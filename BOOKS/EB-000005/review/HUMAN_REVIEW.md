# Revisión humana — EB-000005

![cover](../design/cover.png)

| Campo | Valor |
|---|---|
| Título | El Planner Definitivo de Eventos: Organiza Cualquier Celebración sin Estrés |
| Subtítulo | El método paso a paso para bodas, fiestas, viajes y más |
| Autor | E-Book Factory |
| Idioma / Mercado | es-ES / ES |
| Versión | 1.0 |
| Páginas (PDF 6x9) | 27 |
| Formatos | EPUB, PDF |
| QC | **PASS** (auto: PASS, {'PASS': 24}) |
| Riesgo | LOW  |
| Precio sugerido | 3.99 EUR (ESTIMATE) — Precio de compra impulsiva para el perfil que organiza una boda o evento importante. En línea con guías prácticas de organización en Kindle ES (3,49–4,99 EUR típico). La investigación sugiere 3,99 EUR como punto óptimo: accesible como compra sin pensar pero superior al umbral de 0,99–2,99 que genera dudas de calidad. Rango validado: 3,49–4,49 EUR. |
| Colecciones | - |

## Descripción

¿Has organizado alguna vez un evento y llegado al día con la sensación de que algo importante se te había pasado por alto? Llevas semanas coordinando proveedores, confirmando asistentes y tomando decisiones, pero sin un sistema claro, los detalles se escapan y el estrés se acumula.

El Planner Definitivo de Eventos te da ese sistema.

El método central del libro es el cronograma inverso: empezar desde la fecha del evento y trabajar hacia atrás, asignando cada tarea a la semana exacta en que debe estar hecha. Es la misma lógica que usan los organizadores profesionales, y funciona igual de bien para una boda de doscientas personas que para una escapada de fin de semana con amigos.

Qué encontrarás en el libro:
- Un método reutilizable para cualquier evento, con una sola curva de aprendizaje
- Cronograma completo de 12 meses para bodas, con checklists por etapa
- Guía para fiestas familiares: cumpleaños redondos, comuniones y graduaciones
- Cómo coordinar eventos de grupo sin perder la amistad en el intento
- Checklist de mudanza y trámites administrativos paso a paso
- Organización de viajes y escapadas en grupo, de las fechas al reparto de gastos
- Cómo disfrutar tú también del evento que has organizado — delegando con claridad

Este libro es para ti si:
- Estás organizando una boda y no sabes por dónde empezar
- Te toca siempre organizar los eventos del grupo y quieres un sistema fiable
- Quieres llegar al día de tu evento sabiendo que todo está controlado
- Buscas una guía práctica con checklists integrados, sin relleno — solo herramientas

No hacen falta apps ni materiales adicionales. Los checklists y cronogramas están integrados en el libro.

## Keywords

- checklist boda completo
- cómo organizar fiesta familiar
- planner fiesta cumpleaños
- guía mudanza checklist
- organizar viaje grupo
- cronograma boda 12 meses
- sistema organización eventos

## Categorías

- Tienda Kindle > No Ficción > Hogar, familia y estilo de vida > Planificación de eventos
- Tienda Kindle > No Ficción > Hogar, familia y estilo de vida > Bodas
- Tienda Kindle > No Ficción > Autoayuda y superación personal > Gestión del tiempo

## Warnings / puntos a revisar

- Ninguno

## Archivos

- cover: `design/cover.png`
- cover_jpg: `design/cover.jpg`
- epub: `build/EB-000005_el-planner-definitivo-de-eventos-organiz_v1.0.epub`
- pdf: `build/EB-000005_el-planner-definitivo-de-eventos-organiz_v1.0.pdf`
- Informe QC: `reports/qc_report.md`, `reports/qc_auto.md`
- Informe edición: `reports/editing_report.md`; fact-check: `reports/factcheck_report.md`

## Decisión

```
python factory.py approve EB-000005 --by <SOCIO> [--author "Pen Name"] [--notes "..."]
python factory.py request-changes EB-000005 --by <SOCIO> --restart-at EDIT --notes "qué cambiar"
python factory.py reject EB-000005 --by <SOCIO> --notes "motivo"
```

# Reglas de publicación

1. **La fábrica no publica.** Solo prepara `releases/vX.Y/PUBLISHING_PACKAGE/` (EPUB, PDF, portada PNG/JPG, metadata.json, description.md, keywords.txt, categories.txt, price.json, CHECKLIST.md).
2. Un socio sube el paquete al marketplace a mano y después ejecuta `mark-published`.
3. Aprobación: `approvals_required` (1 por defecto; poned 2 si queréis que aprueben ambos socios).
4. Un `releases/vX.Y/` nunca se sobrescribe. Cambios tras aprobar ⇒ `request-changes` y la siguiente versión.
5. Precio: el MARKET_AGENT sugiere (etiquetado ESTIMATE); el socio decide (`approve --price 4.99`).
6. Autor/pen name: **Addless Motions** (decidido por los socios el 2026-10-01; `default_author` en CONFIG/factory.json). Otro nombre para un libro concreto: `approve --author "Nombre"`. Si un libro tiene `TBD-PEN-NAME`, QC marca HUMAN_REVIEW.
7. Declarar contenido generado o asistido por IA cuando el marketplace lo pregunte (KDP lo pregunta en el alta).
8. Requisitos KDP de referencia (verificar en la ayuda de KDP antes de subir; pueden cambiar): ebook en EPUB; portada JPG/TIFF con ratio ideal 1.6:1 (recomendado 2560×1600 px); hasta 7 keywords; categorías elegidas en el formulario; regalía del 70% solo dentro de una franja de precios (comprobar la franja vigente).
9. Automatizar la publicación (APIs) queda para una fase posterior y requiere decisión de los socios.

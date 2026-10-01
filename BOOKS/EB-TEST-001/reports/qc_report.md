# QC report — EB-TEST-001 v1.0 (round 2)

Round 1 (FAIL: title page alignment) was fixed by TASK-000010 (see `reports/fix_report.md`). Files rebuilt by FORMAT and re-checked independently.

## Automatic checks
`reports/qc_auto.md`: 25 PASS, 1 HUMAN_REVIEW (provisional author). EPUB valid, PDF 26 pages 6×9 in, cover PNG + JPG 1600×2560.

## Content
- PASS — 8/8 chapters from the brief, exercises present, promise fulfilled, no filler, no internal text.

## Language
- PASS — US English, consistent terminology, research claims stated modestly.

## Format
- PASS — Title page now centered (verified visually on the rendered interior). Chapter breaks, TOC, lists and checklist correct.

## Metadata
- PASS — Title, subtitle, description, keywords, categories, price (ESTIMATE).
- HUMAN_REVIEW — Author is `TBD-PEN-NAME`: partners must choose a pen name (`approve --author "…"` rebuilds the files with it).

## Consistency
- PASS — Title consistent across book.json, metadata, EPUB and cover; facts match fact-check report (11 claims: 8 verified, 2 corrected, 1 removed).

## Required fixes
None for the factory. One partner decision: pen name.

VERDICT: HUMAN_REVIEW

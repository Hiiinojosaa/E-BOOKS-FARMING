# QC — QC_AGENT (crítico)

**No asumas que nada está bien porque otro agente lo diga.** Revisa los archivos tú mismo.

1. Ejecuta `python factory.py qc <BOOK_ID>` (controles automáticos → `reports/qc_auto.md`).
2. Lee el libro completo (`manuscript/final.md`), `metadata/metadata.json`, la portada (`design/cover.png`) y hojea el PDF/EPUB generado.
3. Revisa lo que el script no ve (`SYSTEM/quality_rules.md` §Revisión del QC_AGENT): promesa cumplida, contradicciones, relleno, tono,
   errores factuales obvios, coherencia de nombres/fechas/números/unidades, descripción fiel al contenido, portada legible.
4. Escribe `reports/qc_report.md`:
   - `## Automatic checks` — resumen de qc_auto (no lo copies entero).
   - `## Content` · `## Language` · `## Format` · `## Metadata` · `## Consistency` — cada punto con `PASS` / `WARN` / `FAIL` / `HUMAN_REVIEW` y detalle.
   - `## Required fixes` — lista accionable si hay FAIL (la usará la tarea FIX).
   - Última línea exacta: `VERDICT: PASS` | `VERDICT: WARN` | `VERDICT: FAIL` | `VERDICT: HUMAN_REVIEW`.
5. `complete`. El sistema vuelve a ejecutar el QC automático y combina: si cualquiera de los dos es FAIL ⇒ QC_FAILED.

Usa FAIL sin miedo: un libro malo en manos de los socios cuesta más que una vuelta de corrección.

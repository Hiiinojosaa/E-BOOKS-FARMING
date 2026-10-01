# Fix report — EB-TEST-001 (QC round 1)

| Issue | Fix | File |
|---|---|---|
| Title page subtitle/author not centered in PDF (QC FAIL, Format) | Added `.titlepage p { text-align: center }` to the print stylesheet and the EPUB stylesheet (same latent issue in some e-readers). Shared template fix: applies to all future books. | factory/build.py (PRINT_CSS, CSS) |

Manuscript, metadata and cover unchanged. The book returns to DESIGN_COMPLETE so FORMAT rebuilds EPUB/PDF and QC runs again.
Nothing left for human review from this round (the pen name decision remains open, see QC report).

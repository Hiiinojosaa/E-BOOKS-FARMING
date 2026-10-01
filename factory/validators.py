"""Per-step output contracts. `complete` refuses to advance a book unless these pass.

validate(step, book) -> (errors, warnings)      pure checks, no side effects
apply(step, book, agent) -> (done_state, output) side effects after a valid completion
"""
import re

from . import books
from .build import split_chapters
from .core import read_json, read_text, word_count, write_json, write_text
from .qc import qc_markdown, run_auto_qc, text_issues

REQUIRED_BRIEF_SECTIONS = {
    "title": ["working title", "título provisional", "titulo provisional"],
    "audience": ["audience", "público", "publico"],
    "promise": ["promise", "promesa"],
    "outline": ["outline", "estructura", "índice", "indice"],
    "tone": ["tone", "tono"],
    "length": ["length", "extensión", "extension"],
    "risk": ["risk", "riesgo"],
}


def _f(book, *parts):
    return books.book_dir(book["id"]).joinpath(*parts)


def _sections(md):
    """{lowercased heading: body} for '## ' headings."""
    out, cur = {}, None
    for ln in md.splitlines():
        m = re.match(r"^##\s+(.+)$", ln)
        if m:
            cur = m.group(1).strip().lower()
            out[cur] = ""
        elif cur is not None:
            out[cur] += ln + "\n"
    return out


def _find_section(secs, aliases):
    for h, body in secs.items():
        if any(a in h for a in aliases):
            return body
    return None


def outline_chapters(brief_md):
    body = _find_section(_sections(brief_md), REQUIRED_BRIEF_SECTIONS["outline"]) or ""
    return [m.group(1) for m in re.finditer(r"^\s*(?:\d+[.)]|###)\s+(.+)$", body, re.MULTILINE)]


def _need(errors, p, min_words=1, label=None):
    if not p.exists():
        errors.append(f"falta {label or p.name}")
        return ""
    txt = read_text(p)
    if word_count(txt) < min_words:
        errors.append(f"{label or p.name} demasiado corto ({word_count(txt)} < {min_words} palabras)")
    return txt


def _manuscript_checks(errors, warnings, book, txt, min_ratio):
    chs = split_chapters(txt)
    exp = book.get("brief_chapters") or 0
    if not chs:
        errors.append("el manuscrito no tiene capítulos con '# '")
    elif exp and len(chs) < exp:
        errors.append(f"{len(chs)} capítulos < {exp} del brief")
    target = book.get("word_count_target") or 0
    wc = word_count(txt)
    if target and wc < min_ratio * target:
        errors.append(f"{wc} palabras < {int(min_ratio * 100)}% del objetivo ({target})")
    for kind, snip in text_issues(txt)[:5]:
        errors.append(f"{kind}: …{snip}…")


def validate(step, book):
    e, w = [], []
    if step == "RESEARCH":
        txt = _need(e, _f(book, "research", "research.md"), 400, "research/research.md")
        if txt:
            if len(_sections(txt)) < 6:
                e.append("research.md necesita ≥6 secciones '## '")
            if not re.search(r"\b(FACT|ESTIMATE|HYPOTHESIS)\b", txt):
                e.append("research.md debe etiquetar afirmaciones como FACT / ESTIMATE / HYPOTHESIS")
        src = read_json(_f(book, "research", "sources.json"), default=[])
        if not isinstance(src, list):
            e.append("sources.json debe ser una lista")
        else:
            for i, s in enumerate(src):
                if not s.get("title") or not (s.get("url") or s.get("citation")):
                    e.append(f"fuente #{i} sin title y url/citation")
            if not src:
                w.append("sin fuentes registradas")
            if txt and "FACT" in txt and not src:
                e.append("hay afirmaciones FACT pero ninguna fuente en sources.json")
    elif step == "BRIEF":
        txt = _need(e, _f(book, "brief.md"), 200, "brief.md")
        if txt:
            secs = _sections(txt)
            for key, aliases in REQUIRED_BRIEF_SECTIONS.items():
                if _find_section(secs, aliases) is None:
                    e.append(f"brief.md sin sección '{aliases[0]}'")
            n = len(outline_chapters(txt))
            if n < 3:
                e.append(f"outline con {n} capítulos (mínimo 3, formato '1. Título' o '### Título')")
    elif step in ("WRITE", "TRANSLATE"):
        txt = _need(e, _f(book, "manuscript", "draft.md"), 300, "manuscript/draft.md")
        if txt:
            _manuscript_checks(e, w, book, txt, 0.6)
        if step == "TRANSLATE":
            notes = _need(e, _f(book, "reports", "translation_notes.md"), 50, "reports/translation_notes.md")
            for key in ("source_language", "target_language", "adaptation_notes"):
                if notes and key not in notes:
                    e.append(f"translation_notes.md sin '{key}'")
    elif step == "EDIT":
        txt = _need(e, _f(book, "manuscript", "edited.md"), 300, "manuscript/edited.md")
        if txt:
            _manuscript_checks(e, w, book, txt, 0.6)
        _need(e, _f(book, "reports", "editing_report.md"), 80, "reports/editing_report.md")
    elif step == "FACT_CHECK":
        txt = _need(e, _f(book, "manuscript", "final.md"), 300, "manuscript/final.md")
        if txt:
            _manuscript_checks(e, w, book, txt, 0.6)
        rep = _need(e, _f(book, "reports", "factcheck_report.md"), 50, "reports/factcheck_report.md")
        if rep and not re.search(r"^VERDICT:\s*(PASS|FLAGS)\s*$", rep, re.MULTILINE):
            e.append("factcheck_report.md necesita una línea 'VERDICT: PASS' o 'VERDICT: FLAGS'")
    elif step == "METADATA":
        meta = read_json(_f(book, "metadata", "metadata.json"), default={})
        if not meta:
            e.append("falta metadata/metadata.json")
        else:
            for k in ("title", "subtitle", "description", "keywords", "categories", "price", "target_audience", "positioning"):
                if not meta.get(k):
                    e.append(f"metadata.json sin '{k}'")
            if meta.get("keywords") and not (1 <= len(meta["keywords"]) <= 7):
                e.append("keywords: entre 1 y 7")
            if any(len(k) > 50 for k in meta.get("keywords", [])):
                e.append("cada keyword ≤ 50 caracteres")
            if meta.get("categories") and len(meta["categories"]) > 3:
                e.append("máximo 3 categorías")
            if meta.get("description") and not (300 <= len(meta["description"]) <= 4000):
                e.append("description entre 300 y 4000 caracteres")
            price = meta.get("price") or {}
            if price and (price.get("basis") not in ("FACT", "ESTIMATE", "HYPOTHESIS") or not price.get("amount")):
                e.append("price necesita amount, currency y basis FACT/ESTIMATE/HYPOTHESIS")
            for kind, snip in text_issues(" ".join([meta.get("title", ""), meta.get("subtitle", ""), meta.get("description", "")])):
                e.append(f"metadata {kind}: {snip}")
    elif step == "DESIGN":
        d = read_json(_f(book, "design", "design.json"), default={})
        if not d:
            e.append("falta design/design.json")
        png = _f(book, "design", "cover.png")
        if not png.exists():
            e.append("falta design/cover.png (ejecuta: python factory.py cover <BOOK>)")
        elif d and png.stat().st_mtime < _f(book, "design", "design.json").stat().st_mtime:
            e.append("cover.png es más antigua que design.json: vuelve a ejecutar 'cover'")
    elif step == "FORMAT":
        b = books.load(book["id"])
        for k in ("epub", "pdf"):
            if not b["files"].get(k) or not _f(b, b["files"][k]).exists():
                e.append(f"falta {k}")
    elif step == "QC":
        rep = _need(e, _f(book, "reports", "qc_report.md"), 80, "reports/qc_report.md")
        if rep and not re.search(r"^VERDICT:\s*(PASS|WARN|FAIL|HUMAN_REVIEW)\s*$", rep, re.MULTILINE):
            e.append("qc_report.md necesita 'VERDICT: PASS|WARN|FAIL|HUMAN_REVIEW'")
    elif step == "FIX":
        _need(e, _f(book, "reports", "fix_report.md"), 30, "reports/fix_report.md")
    return e, w


def apply(step, book, agent):
    """Side effects after valid completion. May override the done state (QC)."""
    book = books.load(book["id"])
    if step == "BRIEF":
        txt = read_text(_f(book, "brief.md"))
        book["brief_chapters"] = len(outline_chapters(txt))
        risk = _find_section(_sections(txt), REQUIRED_BRIEF_SECTIONS["risk"]) or ""
        if re.search(r"\bHIGH\b|\bALTO\b", risk) and book["risk_level"] != "HIGH":
            book["risk_level"] = "HIGH"
            book["risk_reasons"].append("brief")
        m = re.search(r"(\d[\d.,]*)\s*(words|palabras)", _find_section(_sections(txt), REQUIRED_BRIEF_SECTIONS["length"]) or "")
        if m:
            book["word_count_target"] = int(re.sub(r"[.,]", "", m.group(1)))
        books.save(book)
        return None, {"brief_chapters": book["brief_chapters"], "word_count_target": book["word_count_target"]}
    if step == "FACT_CHECK":
        rep = read_text(_f(book, "reports", "factcheck_report.md"))
        flags = [ln.strip() for ln in rep.splitlines() if "FLAG_FOR_HUMAN_REVIEW" in ln and not ln.strip().startswith("VERDICT")]
        for fl in flags:
            books.add_flag(book, "FLAG_FOR_HUMAN_REVIEW", fl[:300], "FACT_CHECK")
        books.save(book)
        return None, {"flags": len(flags)}
    if step == "METADATA":
        meta = read_json(_f(book, "metadata", "metadata.json"))
        meta.setdefault("author", book["author"])
        meta.setdefault("language", book["language"])
        write_json(_f(book, "metadata", "metadata.json"), meta)
        for k in ("title", "subtitle", "keywords", "categories", "description", "target_audience"):
            book[k] = meta[k]
        book["price_suggested"] = meta["price"]
        books.save(book)
        return None, {"title": book["title"]}
    if step == "DESIGN":
        book["files"]["cover"] = "design/cover.png"
        if _f(book, "design", "cover.jpg").exists():
            book["files"]["cover_jpg"] = "design/cover.jpg"
        books.save(book)
        return None, {"cover": "design/cover.png"}
    if step == "QC":
        auto = run_auto_qc(book["id"])  # independent re-check, never trust the report alone
        rep = read_text(_f(book, "reports", "qc_report.md"))
        verdict = re.search(r"^VERDICT:\s*(PASS|WARN|FAIL|HUMAN_REVIEW)\s*$", rep, re.MULTILINE).group(1)
        final = "FAIL" if "FAIL" in (verdict, auto["overall"]) else \
            "HUMAN_REVIEW" if "HUMAN_REVIEW" in (verdict, auto["overall"]) else \
            "WARN" if "WARN" in (verdict, auto["overall"]) else "PASS"
        write_text(_f(book, "reports", "qc_auto.md"), qc_markdown(auto))
        book = books.load(book["id"])
        book["qc_status"] = final
        if final == "FAIL":
            book["qc_fail_count"] = book.get("qc_fail_count", 0) + 1
        books.save(book)
        return ("QC_FAILED" if final == "FAIL" else "QC_PASSED"), {"agent_verdict": verdict, "auto": auto["overall"], "final": final}
    return None, None

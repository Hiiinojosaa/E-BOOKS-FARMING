"""Independent automatic QC. Never trusts what other agents claim: it re-reads the files."""
import re
from collections import Counter
from . import books
from .build import jpeg_size, manuscript_path, pdf_page_count, png_size, split_chapters, validate_epub
from .core import PLACEHOLDER_AUTHOR, load_config, now_iso, read_json, read_text, word_count, write_json

# Case-sensitive on purpose: "todo" is a normal Spanish word, "TODO" is a placeholder.
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX+)\b|\{\{[^}]*\}\}|<placeholder>|\?\?\?")
PLACEHOLDER_CI_RE = re.compile(r"lorem ipsum|\[(?:insert|placeholder|añadir|insertar|pendiente)[^\]]*\]", re.IGNORECASE)
AGENT_RE = re.compile(
    r"as an ai\b|language model|modelo de lenguaje|como (una )?ia\b|\b[A-Z]+_AGENT\b|\bORCHESTRATOR\b"
    r"|PROMPTS/|system prompt|claude code|anthropic|\bEB-\d{6}\b|\bTASK-\d{6}\b|\bbook\.json\b"
    r"|here is (the|your) (chapter|draft|book)|aquí tienes (el|tu) (capítulo|borrador|libro)"
    r"|i hope this helps|espero que (esto|te) (te )?(sirva|ayude)", re.IGNORECASE)
UK_SPELLINGS = ["colour", "favour", "behaviour", "organise", "organisation", "prioritise", "realise",
                "recognise", "analyse", "centre", "programme", "travelled", "labour", "honour", "licence"]
US_SPELLINGS = ["color", "favor", "behavior", "organize", "organization", "prioritize", "realize",
                "recognize", "analyze", "center", "program", "traveled", "labor", "honor", "license"]
EN_STOP = {"the", "and", "of", "to", "is", "you", "that", "it", "for", "with", "your", "this", "are"}
ES_STOP = {"el", "la", "de", "que", "y", "en", "los", "las", "es", "por", "para", "con", "una", "tu"}


def text_issues(text):
    """Content defects that must never reach a reader. Returns list of (kind, snippet)."""
    issues = []
    for rx in (PLACEHOLDER_RE, PLACEHOLDER_CI_RE):
        for m in rx.finditer(text):
            issues.append(("placeholder", text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")))
    for m in AGENT_RE.finditer(text):
        issues.append(("internal_reference", text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")))
    return issues


def detect_language(text):
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    en = sum(1 for w in words if w in EN_STOP)
    es = sum(1 for w in words if w in ES_STOP)
    if en + es < 20:
        return None
    return "en" if en > es else "es"


def repeated_paragraphs(text, min_len=80):
    paras = [re.sub(r"\s+", " ", p.strip()).lower() for p in re.split(r"\n\s*\n", text)]
    c = Counter(p for p in paras if len(p) >= min_len)
    return [p[:80] for p, n in c.items() if n > 1]


def repeated_words(text):
    return sorted({m.group(0) for m in re.finditer(r"\b(\w{2,})\s+\1\b", text, re.IGNORECASE)
                   if m.group(1).lower() not in {"had", "that", "very", "bye", "no", "muy"}})


def brief_chapter_count(book):
    return book.get("brief_chapters") or 0


class Report:
    def __init__(self):
        self.checks = []

    def add(self, category, name, result, detail=""):
        self.checks.append({"category": category, "check": name, "result": result, "detail": detail})

    def overall(self):
        res = {c["result"] for c in self.checks}
        for level in ("FAIL", "HUMAN_REVIEW", "WARN"):
            if level in res:
                return level
        return "PASS"


def run_auto_qc(book_id, require_build=True):
    cfg = load_config()
    book = books.load(book_id)
    bdir = books.book_dir(book_id)
    meta = read_json(bdir / "metadata" / "metadata.json", default={}) or {}
    r = Report()

    # ---------------- CONTENT
    try:
        mpath = manuscript_path(book)
        text = read_text(mpath)
        r.add("CONTENT", "manuscript_exists", "PASS", mpath.name)
    except Exception as e:  # noqa: BLE001
        r.add("CONTENT", "manuscript_exists", "FAIL", str(e))
        text = ""
    chapters = split_chapters(text)
    expected = brief_chapter_count(book)
    if not chapters:
        r.add("CONTENT", "chapters", "FAIL", "0 capítulos")
    elif expected and len(chapters) < expected:
        r.add("CONTENT", "chapters", "FAIL", f"{len(chapters)} capítulos < {expected} del brief")
    else:
        r.add("CONTENT", "chapters", "PASS", f"{len(chapters)} capítulos")
    short = [t for t, b in chapters if word_count(b) < 150]
    r.add("CONTENT", "chapters_complete", "FAIL" if short else "PASS", ", ".join(short) or "todos ≥150 palabras")
    words = word_count(text)
    target = book.get("word_count_target") or 0
    if target and words < 0.6 * target:
        r.add("CONTENT", "length", "FAIL", f"{words} palabras < 60% del objetivo {target}")
    elif target and words < 0.85 * target:
        r.add("CONTENT", "length", "WARN", f"{words} palabras (objetivo {target})")
    else:
        r.add("CONTENT", "length", "PASS", f"{words} palabras")
    issues = text_issues(text)
    ph = [s for k, s in issues if k == "placeholder"]
    ag = [s for k, s in issues if k == "internal_reference"]
    r.add("CONTENT", "no_placeholders", "FAIL" if ph else "PASS", " | ".join(ph[:5]))
    r.add("CONTENT", "no_internal_instructions", "FAIL" if ag else "PASS", " | ".join(ag[:5]))
    rep = repeated_paragraphs(text)
    r.add("CONTENT", "no_duplicate_paragraphs", "FAIL" if rep else "PASS", " | ".join(rep[:3]))
    titles = [t.lower() for t, _ in chapters]
    dup_t = [t for t, n in Counter(titles).items() if n > 1]
    r.add("CONTENT", "unique_chapter_titles", "FAIL" if dup_t else "PASS", ", ".join(dup_t))

    # ---------------- LANGUAGE
    lang = detect_language(text)
    want = book["language"][:2]
    r.add("LANGUAGE", "language_matches", "PASS" if lang == want else "FAIL", f"detectado={lang} esperado={want}")
    rw = repeated_words(text)
    r.add("LANGUAGE", "repeated_words", "WARN" if rw else "PASS", ", ".join(rw[:10]))
    low = text.lower()
    if book["language"] == "en-US":
        uk = [w for w in UK_SPELLINGS if re.search(rf"\b{w}\b", low)]
        r.add("LANGUAGE", "us_spelling", "WARN" if uk else "PASS", ", ".join(uk))
    elif book["language"] == "en-GB":
        us = [w for w in US_SPELLINGS if re.search(rf"\b{w}\b", low)]
        r.add("LANGUAGE", "uk_spelling", "WARN" if us else "PASS", ", ".join(us))
    dbl = len(re.findall(r"[^\s.] {2,}\S", text))
    r.add("LANGUAGE", "spacing", "WARN" if dbl else "PASS", f"{dbl} dobles espacios" if dbl else "")

    # ---------------- FORMAT
    epub = bdir / book["files"].get("epub", "build/__none__.epub")
    pdf = bdir / book["files"].get("pdf", "build/__none__.pdf")
    if require_build:
        if epub.exists():
            errs, warns, info = validate_epub(epub)
            r.add("FORMAT", "epub_valid", "FAIL" if errs else ("WARN" if warns else "PASS"),
                  "; ".join(errs[:5] + warns[:5]) or f"{info.get('documents')} docs, {info.get('internal_links')} enlaces")
            if info.get("title") and info["title"] != (meta.get("title") or book["title"]):
                r.add("CONSISTENCY", "epub_title_matches", "FAIL", f"EPUB '{info['title']}'")
            elif info.get("title"):
                r.add("CONSISTENCY", "epub_title_matches", "PASS")
        else:
            r.add("FORMAT", "epub_valid", "FAIL", "no existe EPUB")
        if pdf.exists():
            pages = pdf_page_count(pdf)
            r.add("FORMAT", "pdf_pages", "PASS" if pages >= 24 else "WARN", f"{pages} páginas" + (" (KDP print exige ≥24)" if pages < 24 else ""))
        else:
            r.add("FORMAT", "pdf_pages", "FAIL", "no existe PDF")
    cover = bdir / "design" / "cover.png"
    if cover.exists():
        w, h = png_size(cover)
        need = cfg["cover_size_px"]
        ok = w >= need["width"] and h >= need["height"] and abs(h / w - 1.6) < 0.05
        r.add("FORMAT", "cover", "PASS" if ok else "FAIL", f"{w}x{h}px")
        jpg = bdir / "design" / "cover.jpg"
        if jpg.exists():
            r.add("FORMAT", "cover_jpg", "PASS", "%dx%d" % jpeg_size(jpg))
        else:
            r.add("FORMAT", "cover_jpg", "WARN", "sin JPG (KDP pide JPG/TIFF para la portada)")
    else:
        r.add("FORMAT", "cover", "FAIL", "no existe design/cover.png")
    num = [re.match(r"^(chapter|capítulo)\s+(\d+)", t, re.IGNORECASE) for t, _ in chapters]
    nums = [int(m.group(2)) for m in num if m]
    if nums:
        ok = nums == list(range(nums[0], nums[0] + len(nums)))
        r.add("FORMAT", "chapter_numbering", "PASS" if ok else "FAIL", str(nums))

    # ---------------- METADATA
    title = meta.get("title") or ""
    r.add("METADATA", "title", "PASS" if title else "FAIL", title)
    r.add("METADATA", "subtitle", "PASS" if meta.get("subtitle") else "WARN", meta.get("subtitle", ""))
    author = meta.get("author") or book.get("author")
    if not author:
        r.add("METADATA", "author", "FAIL", "vacío")
    elif author == PLACEHOLDER_AUTHOR:
        r.add("METADATA", "author", "HUMAN_REVIEW", f"'{author}' es provisional: los socios deben decidir el pen name")
    else:
        r.add("METADATA", "author", "PASS", author)
    r.add("METADATA", "language", "PASS" if meta.get("language", book["language"]) == book["language"] else "FAIL",
          book["language"])
    kws = meta.get("keywords", [])
    bad_kw = [k for k in kws if len(k) > 50]
    r.add("METADATA", "keywords", "PASS" if 1 <= len(kws) <= 7 and not bad_kw else "FAIL",
          f"{len(kws)} keywords" + (f"; >50 chars: {bad_kw}" if bad_kw else ""))
    cats = meta.get("categories", [])
    r.add("METADATA", "categories", "PASS" if 1 <= len(cats) <= 3 else "FAIL", f"{len(cats)}")
    desc = meta.get("description", "")
    r.add("METADATA", "description", "PASS" if 300 <= len(desc) <= 4000 else "FAIL", f"{len(desc)} caracteres")
    d_issues = text_issues(desc + " " + title + " " + meta.get("subtitle", ""))
    r.add("METADATA", "metadata_clean", "FAIL" if d_issues else "PASS", " | ".join(s for _, s in d_issues[:3]))

    # ---------------- CONSISTENCY / RISK
    if title and title != book["title"]:
        r.add("CONSISTENCY", "title_sync", "FAIL", f"book.json '{book['title']}' vs metadata '{title}'")
    if book.get("risk_level") == "HIGH":
        r.add("RISK", "sensitive_topic", "HUMAN_REVIEW", "Tema sensible: " + ", ".join(book.get("risk_reasons", [])))
    open_flags = [f for f in book.get("flags", []) if f["level"] in ("HUMAN_REVIEW", "FLAG_FOR_HUMAN_REVIEW")]
    if open_flags:
        r.add("CONSISTENCY", "open_flags", "HUMAN_REVIEW", " | ".join(f["message"][:100] for f in open_flags[:5]))

    result = {"book_id": book_id, "version": book["version"], "at": now_iso(), "overall": r.overall(),
              "counts": dict(Counter(c["result"] for c in r.checks)), "checks": r.checks}
    write_json(bdir / "reports" / "qc_auto.json", result)
    return result


def qc_markdown(result):
    lines = [f"# QC automático — {result['book_id']} v{result['version']}", "",
             f"**Resultado global: {result['overall']}** · {result['counts']} · {result['at']}", "",
             "| Categoría | Control | Resultado | Detalle |", "|---|---|---|---|"]
    for c in result["checks"]:
        lines.append(f"| {c['category']} | {c['check']} | {c['result']} | {str(c['detail']).replace('|', '/')[:160]} |")
    return "\n".join(lines) + "\n"

"""Synthetic step outputs for infrastructure tests. NOT real book content — never used for products."""
import json
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

WORDS = ("focus habit plan task energy calendar list review goal morning system priority deadline "
         "routine break note project inbox choice week").split()


def sandbox():
    """Fresh factory root in a temp dir with the real templates/config/prompts."""
    d = Path(tempfile.mkdtemp(prefix="ebf-test-"))
    for sub in ("TEMPLATES", "CONFIG", "PROMPTS", "SYSTEM"):
        if (REPO / sub).exists():
            shutil.copytree(REPO / sub, d / sub)
    (d / "CONFIG").mkdir(exist_ok=True)
    cfg = json.loads((REPO / "CONFIG" / "factory.json").read_text(encoding="utf-8")) if (REPO / "CONFIG" / "factory.json").exists() else {}
    cfg["git"] = {"sync_enabled": False, "remote": "origin", "branch": "main"}
    (d / "CONFIG" / "factory.json").write_text(json.dumps(cfg), encoding="utf-8")
    return d


def _para(seed, n=60):
    out = []
    for i in range(n):
        out.append(WORDS[(seed * 7 + i * 3) % len(WORDS)])
    s = " ".join(out)
    return f"In section {seed} the reader learns that the {s}. This is why it is useful for you and for the team, and it is also simple to apply each day."


def manuscript(tag, chapters=4, paras=6):
    parts = []
    for c in range(1, chapters + 1):
        parts.append(f"# Chapter {c}: {tag} topic {c}\n")
        for p in range(paras):
            parts.append(_para(c * 100 + p + hash(tag) % 997) + f" ({tag} c{c} p{p})\n")
        parts.append(f"## Practice {c}\n\n- Write the {tag} list {c}\n- Review it on day {c}\n")
    return "\n".join(parts)


def marker(book_id):
    """Per-book text marker (internal IDs like EB-000001 are banned from reader text by QC)."""
    return "Marker" + "".join(ch for ch in book_id if ch.isalnum())


def write_step(root, book_id, step, tag=None):
    b = Path(root) / "BOOKS" / book_id
    tag = tag or marker(book_id)
    w = lambda rel, txt: ((b / rel).parent.mkdir(parents=True, exist_ok=True), (b / rel).write_text(txt, encoding="utf-8"))
    if step == "RESEARCH":
        secs = "\n".join(f"## Section {i}\n\nFACT: the {tag} market has data point {i} [S1]. ESTIMATE: demand is medium. HYPOTHESIS: angle {i} works.\n" + _para(i, 70)
                         for i in range(1, 8))
        w("research/research.md", f"# Research {tag}\n\n{secs}\n")
        w("research/sources.json", json.dumps([{"id": "S1", "title": "Test source", "url": "https://example.org", "accessed": "2026-10-01", "used_for": "test"}]))
    elif step == "BRIEF":
        w("brief.md", f"""# Brief {tag}

## Working title
{tag} Made Simple

## Audience
Beginners who want a calm, practical start. {_para(1, 40)}

## Promise
The reader will finish with a working weekly system. {_para(2, 40)}

## Outline
1. Chapter one
2. Chapter two
3. Chapter three
4. Chapter four

## Tone
Warm, direct, practical. {_para(3, 30)}

## Length
1200 words

## Risk
LOW
""")
    elif step == "WRITE":
        w("manuscript/draft.md", manuscript(tag))
    elif step == "EDIT":
        w("manuscript/edited.md", manuscript(tag))
        w("reports/editing_report.md", "# Editing report\n\n" + _para(9, 90))
    elif step == "FACT_CHECK":
        w("manuscript/final.md", manuscript(tag))
        w("reports/factcheck_report.md", "# Fact check\n\nNo verifiable claims in synthetic text. " + _para(5, 30) + "\n\nVERDICT: PASS\n")
    elif step == "METADATA":
        w("metadata/metadata.json", json.dumps({
            "title": f"{tag} Made Simple", "subtitle": "A Calm Starter Guide",
            "description": ("A practical starter guide. " + _para(4, 70))[:900],
            "keywords": ["productivity for beginners", "time management", "focus"], "categories": ["Self-Help / Time Management"],
            "price": {"amount": 2.99, "currency": "USD", "basis": "ESTIMATE", "rationale": "test"},
            "target_audience": "beginners", "positioning": "simple starter"}))
    elif step == "DESIGN":
        w("design/design.json", json.dumps({"template": "minimal", "tagline": "Starter guide", "title_line1": tag, "title_line2": "Simple",
                                            "palette": {"bg": "#f4f1ea", "fg": "#1d1d1b", "accent": "#2f5d50", "muted": "#6b6b66"}}))
    elif step == "QC":
        w("reports/qc_report.md", "# QC report\n\nSynthetic test content reviewed by the test harness. " + _para(6, 60) + "\n\nVERDICT: PASS\n")
    elif step == "FIX":
        w("reports/fix_report.md", "# Fix report\n\nFixed the issues reported by QC in the test harness run.\n")

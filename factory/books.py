"""Books: master record (book.json), unique IDs, state transitions + history."""
import re

from . import states
from .core import (FactoryError, append_jsonl, load_config, log_event, now_iso, path, read_json,
                   read_jsonl, write_json)

BOOK_SUBDIRS = ["research", "manuscript", "reports", "metadata", "design", "build", "review", "releases"]
ID_RE = re.compile(r"^EB-(\d{6})$")
LANGS = {"es": "es-ES", "es-es": "es-ES", "es-mx": "es-MX", "en": "en-US", "en-us": "en-US", "en-gb": "en-GB"}


def norm_lang(lang):
    key = (lang or "").strip().lower()
    if key not in LANGS:
        raise FactoryError(f"Idioma no soportado: {lang}. Usa: es-ES, es-MX, en-US, en-GB")
    return LANGS[key]


def book_dir(book_id):
    return path("BOOKS", book_id)


def book_file(book_id):
    return book_dir(book_id) / "book.json"


def exists(book_id):
    return book_file(book_id).exists()


def load(book_id):
    if not exists(book_id):
        raise FactoryError(f"Libro no encontrado: {book_id}")
    return read_json(book_file(book_id))


def save(book):
    book["updated_at"] = now_iso()
    write_json(book_file(book["id"]), book)


def all_books():
    d = path("BOOKS")
    out = []
    if d.exists():
        for sub in sorted(d.iterdir()):
            f = sub / "book.json"
            if f.exists():
                out.append(read_json(f))
    return out


def history(book_id):
    return read_jsonl(book_dir(book_id) / "history.jsonl")


def _allocate_id():
    """Next EB-NNNNNN. mkdir is atomic, so two local agents can't get the same id."""
    d = path("BOOKS")
    d.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for m in (ID_RE.match(p.name) for p in d.iterdir()) if m]
    n = max(nums, default=0) + 1
    while True:
        bid = f"EB-{n:06d}"
        try:
            (d / bid).mkdir()
            return bid
        except FileExistsError:
            n += 1


def detect_risk(*texts):
    blob = " ".join(t for t in texts if t).lower()
    hits = [k for k in load_config()["high_risk_keywords"] if k in blob]
    return ("HIGH", hits) if hits else ("LOW", [])


def create(topic, language="en-US", market=None, *, book_id=None, agent="HUMAN", priority="NORMAL",
           niche="", genre="non-fiction", target_audience="", target_languages=None, collection=None,
           parent_book=None, translated_from=None, state="IDEA", word_count_target=6000, notes="", recommended=False,
           rationale=""):
    cfg = load_config()
    language = norm_lang(language)
    if priority not in states.PRIORITIES:
        raise FactoryError(f"Prioridad inválida: {priority}")
    if book_id:
        if exists(book_id):
            raise FactoryError(f"Ya existe {book_id}")
        book_dir(book_id).mkdir(parents=True, exist_ok=True)
    else:
        book_id = _allocate_id()
    for sub in BOOK_SUBDIRS:
        (book_dir(book_id) / sub).mkdir(parents=True, exist_ok=True)
    risk, hits = detect_risk(topic, niche, genre)
    ts = now_iso()
    book = {
        "id": book_id,
        "topic": topic,
        "title": topic,
        "subtitle": "",
        "author": cfg["default_author"],
        "language": language,
        "market": market or {"en-US": "US", "en-GB": "UK", "es-ES": "ES", "es-MX": "MX"}[language],
        "genre": genre,
        "niche": niche,
        "target_audience": target_audience,
        "status": state,
        "blocked_from": None,
        "priority": priority,
        "assigned_agent": None,
        "owner_partner": None,
        "created_at": ts,
        "updated_at": ts,
        "version": "1.0",
        "parent_book": parent_book,
        "translated_from": translated_from,
        "related_books": [],
        "source_language": None,
        "target_languages": [norm_lang(l) for l in (target_languages or [])],
        "collections": [collection] if collection else [],
        "series": None,
        "keywords": [],
        "categories": [],
        "description": "",
        "price_suggested": None,
        "risk_level": risk,
        "risk_reasons": hits,
        "word_count_target": word_count_target,
        "brief_approved": False,
        "brief_approved_by": None,
        "human_approval": {"decision": None, "by": [], "at": None, "notes": ""},
        "change_requests": [],
        "flags": [],
        "qc_status": None,
        "qc_fail_count": 0,
        "page_count": None,
        "formats": [],
        "files": {},
        "publication_status": "NOT_PUBLISHED",
        "published": [],
        "notes": notes,
        "recommended_by": agent if recommended else None,
        "recommendation": rationale,
        "idea_approved": not recommended,  # partner ideas go straight in; agent recommendations wait for a yes
        "idea_approved_by": None if recommended else agent,
    }
    if translated_from:
        src = load(translated_from)
        book["source_language"] = src["language"]
    write_json(book_file(book_id), book)
    _history(book_id, None, state, agent, "CREATE", "OK", note=topic)
    log_event("BOOK_CREATED", book_id=book_id, agent=agent, topic=topic, language=language)
    return book


def _history(book_id, frm, to, agent, action, result, task_id=None, note=None):
    rec = {"ts": now_iso(), "from": frm, "to": to, "agent": agent, "action": action,
           "result": result}
    if task_id:
        rec["task_id"] = task_id
    if note:
        rec["note"] = note
    append_jsonl(book_dir(book_id) / "history.jsonl", rec)


def transition(book_id, to, agent, action, result="OK", task_id=None, note=None, book=None):
    """The ONLY way to change a book's status. Always records history."""
    book = book or load(book_id)
    frm = book["status"]
    if frm == to:
        return book
    if to not in states.STATES:
        raise FactoryError(f"Estado desconocido: {to}")
    if not states.can_transition(frm, to):
        raise FactoryError(f"Transición no permitida {book_id}: {frm} -> {to}")
    if to == "BLOCKED":
        book["blocked_from"] = frm
    elif frm == "BLOCKED":
        book["blocked_from"] = None
    book["status"] = to
    save(book)
    _history(book_id, frm, to, agent, action, result, task_id, note)
    log_event("STATE_CHANGE", book_id=book_id, frm=frm, to=to, agent=agent, action=action,
              result=result, task_id=task_id)
    return book


def add_flag(book, level, message, source):
    flag = {"level": level, "message": message, "source": source, "at": now_iso()}
    if not any(f["message"] == message and f["source"] == source for f in book["flags"]):
        book["flags"].append(flag)
    return book


def bump_version(book, major=False):
    maj, mnr = (int(x) for x in book["version"].split("."))
    book["version"] = f"{maj + 1}.0" if major else f"{maj}.{mnr + 1}"
    return book["version"]

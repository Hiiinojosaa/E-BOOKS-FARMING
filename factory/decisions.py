"""Escalation queue: questions that only the partners can answer (one file each, no git conflicts)."""
import re

from .core import FactoryError, log_event, now_iso, path, read_json, write_json

D_RE = re.compile(r"^DEC-(\d{5})\.json$")


def _dir():
    return path("DECISIONS")


def ask(question, by, book_id=None, options=None, urgency="NORMAL"):
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for m in (D_RE.match(p.name) for p in d.iterdir()) if m]
    n = max(nums, default=0) + 1
    did = f"DEC-{n:05d}"
    rec = {"id": did, "book_id": book_id, "question": question, "options": options or [], "asked_by": by,
           "asked_at": now_iso(), "urgency": urgency, "status": "OPEN", "answer": None, "answered_by": None}
    write_json(d / f"{did}.json", rec)
    log_event("DECISION_ASKED", decision=did, book_id=book_id, by=by)
    from . import chat
    chat.post(by, "agent", question, kind="question", decision_id=did, options=options or [], book_id=book_id)
    return rec


def answer(did, by, text):
    p = _dir() / f"{did}.json"
    if not p.exists():
        raise FactoryError(f"No existe {did}")
    rec = read_json(p)
    if rec["status"] != "OPEN":
        raise FactoryError(f"{did} ya fue respondida por {rec.get('answered_by')}: {rec.get('answer')}")
    rec.update(status="ANSWERED", answer=text, answered_by=by, answered_at=now_iso())
    write_json(p, rec)
    log_event("DECISION_ANSWERED", decision=did, by=by)
    from . import chat
    chat.post(by, "partner", text, kind="answer", decision_id=did, book_id=rec.get("book_id"))
    return rec


def all_decisions(status=None):
    d = _dir()
    out = [read_json(p) for p in sorted(d.glob("DEC-*.json"))] if d.exists() else []
    return [r for r in out if not status or r["status"] == status]

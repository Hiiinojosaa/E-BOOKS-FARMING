"""DIRECTIVES: standing guidelines the partners give the chief agent (usually in their meetings).

Unlike a chat message (one request, one answer), a directive stays in force until the partners remove it:
"this week 70% en-US", "max price 3.99", "no health topics". Every agent reads them at the start of a session.
One file per directive in DIRECTIVES/ (no git conflicts).
"""
import secrets
import time

from .core import FactoryError, create_exclusive_json, log_event, now_iso, path, read_json, write_json


def _dir():
    d = path("DIRECTIVES")
    d.mkdir(parents=True, exist_ok=True)
    return d


def add(text, by):
    text = (text or "").strip()
    if len(text) < 4:
        raise FactoryError("La directriz está vacía")
    did = f"DIR-{time.time_ns()}-{secrets.token_hex(2)}"
    rec = {"id": did, "text": text[:600], "by": by, "created_at": now_iso(), "active": True, "removed_by": None}
    create_exclusive_json(_dir() / f"{did}.json", rec)
    log_event("DIRECTIVE_ADDED", by=by, directive=did)
    from . import chat
    chat.post(by, "partner", text, kind="directive")
    return rec


def remove(did, by):
    p = _dir() / f"{did}.json"
    if not p.exists():
        raise FactoryError(f"No existe {did}")
    rec = read_json(p)
    rec.update(active=False, removed_by=by, removed_at=now_iso())
    write_json(p, rec)
    log_event("DIRECTIVE_REMOVED", by=by, directive=did)
    return rec


def active():
    return sorted((r for r in (read_json(p, default={}) for p in _dir().glob("DIR-*.json")) if r and r.get("active")),
                  key=lambda r: r["id"])

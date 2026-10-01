"""CHAT: shared conversation between the partners and the agents.

One file per message (CHAT/<YYYY-MM>/<timestamp>_<random>.json) so two machines can write at the same
time without git conflicts. A partner message addressed to the factory also creates an ORDER, so agents
pick it up through the normal protocol; closing that order posts the agent's answer back into the chat.
Agent questions (DECISIONS) and their answers also appear here.
"""
import secrets
import time

from .core import create_exclusive_json, log_event, now_iso, path, read_json, utcnow

ROLES = ("partner", "agent", "system")
KINDS = ("message", "progress", "question", "answer", "note")


def _dir():
    d = path("CHAT", utcnow().strftime("%Y-%m"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def post(sender, role, text, kind="message", to=None, book_id=None, order_id=None, decision_id=None,
         options=None, reply_to=None):
    text = (text or "").strip()
    if not text:
        raise ValueError("mensaje vacío")
    ts = now_iso()
    # nanosecond prefix keeps messages written in the same second in the right order
    mid = f"MSG-{time.time_ns()}-{secrets.token_hex(3)}"
    msg = {"id": mid, "ts": ts, "from": sender, "role": role, "kind": kind, "to": to, "text": text[:4000],
           "book_id": book_id, "order_id": order_id, "decision_id": decision_id, "options": options or [],
           "reply_to": reply_to}
    create_exclusive_json(_dir() / f"{mid}.json", msg)
    if role != "system":
        log_event("CHAT", by=sender, role=role, kind=kind, msg=mid)
    return msg


def all_messages(limit=400):
    root = path("CHAT")
    if not root.exists():
        return []
    files = sorted(root.glob("*/MSG-*.json"), key=lambda p: p.name)[-limit:]
    out = [read_json(f, default={}) for f in files]
    return sorted((m for m in out if m), key=lambda m: m["id"])


def latest_marker():
    """Cheap change detector for the live panel."""
    root = path("CHAT")
    if not root.exists():
        return ""
    names = sorted(p.name for p in root.glob("*/MSG-*.json"))
    return f"{len(names)}:{names[-1] if names else ''}"

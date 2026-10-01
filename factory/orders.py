"""ORDERS: instructions from the partners to the agents (written from the panel or the CLI).

One file per order in ORDERS/ (no git conflicts). Lifecycle: OPEN -> IN_PROGRESS -> DONE | REJECTED | CANCELLED.
Agents read open orders at the start of every session (PROMPTS/WORKER.md). An order can never override the
hard rules in CLAUDE.md (no publishing, no purchases, no secrets, no invented facts).
"""
import re

from .core import FactoryError, create_exclusive_json, log_event, now_iso, path, read_json, write_json

O_RE = re.compile(r"^ORD-(\d{5})\.json$")
KINDS = ["CHAT", "GENERAL", "NEW_BOOK", "RESEARCH_IDEAS", "CHANGE", "PRIORITY", "REPORT"]
STATUSES = ["OPEN", "IN_PROGRESS", "DONE", "REJECTED", "CANCELLED"]


def _dir():
    d = path("ORDERS")
    d.mkdir(parents=True, exist_ok=True)
    return d


def create(text, by, kind="GENERAL", target_agent=None, book_id=None, priority="NORMAL", chat_msg=None):
    text = (text or "").strip()
    if len(text) < 5:
        raise FactoryError("La orden está vacía o es demasiado corta")
    if kind not in KINDS:
        raise FactoryError(f"Tipo de orden inválido: {kind}")
    d = _dir()
    n = max([int(m.group(1)) for m in (O_RE.match(p.name) for p in d.iterdir()) if m], default=0) + 1
    while True:
        oid = f"ORD-{n:05d}"
        rec = {"id": oid, "kind": kind, "text": text, "by": by, "created_at": now_iso(), "priority": priority,
               "target_agent": target_agent or None, "book_id": book_id or None, "status": "OPEN",
               "taken_by": None, "updated_at": now_iso(), "result": None, "history": [], "chat_msg": chat_msg}
        try:
            create_exclusive_json(d / f"{oid}.json", rec)
            break
        except FileExistsError:
            n += 1
    log_event("ORDER_CREATED", order=oid, by=by, kind=kind)
    return rec


def get(oid):
    p = _dir() / f"{oid}.json"
    if not p.exists():
        raise FactoryError(f"No existe {oid}")
    return read_json(p)


def update(oid, status, who, note=""):
    if status not in STATUSES:
        raise FactoryError(f"Estado inválido: {status}")
    rec = get(oid)
    if rec["status"] in ("DONE", "REJECTED", "CANCELLED"):
        raise FactoryError(f"{oid} ya está cerrada ({rec['status']})")
    rec["history"].append({"at": now_iso(), "by": who, "from": rec["status"], "to": status, "note": note})
    rec["status"] = status
    rec["updated_at"] = now_iso()
    if status == "IN_PROGRESS":
        rec["taken_by"] = who
    if note and status in ("DONE", "REJECTED"):
        rec["result"] = note
    write_json(_dir() / f"{oid}.json", rec)
    log_event("ORDER_UPDATED", order=oid, by=who, status=status)
    if status in ("DONE", "REJECTED") and note:
        from . import chat  # the answer goes back to whoever asked, in the chat
        chat.post(who, "agent", note, kind="answer", order_id=oid, reply_to=rec.get("chat_msg"), book_id=rec.get("book_id"))
    return rec


def all_orders(status=None):
    out = [read_json(p, default={}) for p in sorted(_dir().glob("ORD-*.json"))]
    out = [o for o in out if o]
    return [o for o in out if not status or o["status"] in (status if isinstance(status, (list, tuple)) else [status])]


def for_agent(agent_id):
    """Open orders this agent may take: untargeted ones or those addressed to it."""
    return [o for o in all_orders(["OPEN", "IN_PROGRESS"])
            if (not o["target_agent"] or o["target_agent"] == agent_id)
            and (o["status"] == "OPEN" or o["taken_by"] == agent_id)]

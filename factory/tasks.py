"""Task queue. A task's status IS the folder it lives in (TASKS/<STATUS>/TASK-xxxxxx.json).

Claiming = os.rename(READY -> RUNNING). Rename is atomic, so if two agents race
for the same task exactly one succeeds. A book lock is taken first so that no
two agents ever work on the same book at the same time.
"""
import os
import re

from . import agents, books, locks, states, validators
from .core import FactoryError, load_config, log_event, now_iso, path, read_json, write_json

TASK_STATUSES = ["INBOX", "READY", "RUNNING", "BLOCKED", "DONE", "FAILED"]
OPEN_STATUSES = ["INBOX", "READY", "RUNNING", "BLOCKED"]
TASK_RE = re.compile(r"^TASK-(\d{6})\.json$")


def task_path(status, task_id):
    d = path("TASKS", status)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
    return d / f"{task_id}.json"


def find(task_id):
    for st in TASK_STATUSES:
        p = task_path(st, task_id)
        if p.exists():
            return st, read_json(p)
    raise FactoryError(f"Tarea no encontrada: {task_id}")


def all_tasks(statuses=None):
    out = []
    for st in statuses or TASK_STATUSES:
        d = path("TASKS", st)
        if d.exists():
            for f in sorted(d.glob("TASK-*.json")):
                t = read_json(f)
                t["status"] = st  # folder wins over field
                out.append(t)
    return out


def open_tasks_for_book(book_id):
    return [t for t in all_tasks(OPEN_STATUSES) if t["book_id"] == book_id]


def _next_number():
    n = 0
    for st in TASK_STATUSES:
        d = path("TASKS", st)
        if d.exists():
            for f in d.iterdir():
                m = TASK_RE.match(f.name)
                if m:
                    n = max(n, int(m.group(1)))
    return n + 1


def _move(task, frm, to):
    os.rename(task_path(frm, task["task_id"]), task_path(to, task["task_id"]))
    task["status"] = to
    write_json(task_path(to, task["task_id"]), task)


def create(book_id, step, priority="NORMAL", dependencies=None, notes="", assigned_agent=None,
           agent="ORCHESTRATOR"):
    if step not in states.STEPS:
        raise FactoryError(f"Tipo de tarea desconocido: {step}")
    status = "INBOX" if dependencies else "READY"
    n = _next_number()
    while True:
        task_id = f"TASK-{n:06d}"
        p = task_path(status, task_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            n += 1
    st = states.STEPS[step]
    task = {
        "task_id": task_id, "book_id": book_id, "type": step, "role": st["role"],
        "auto": st["auto"], "priority": priority, "status": status,
        "assigned_agent": assigned_agent, "created_by": agent, "created_at": now_iso(),
        "started_at": None, "completed_at": None, "claimed_from_state": None,
        "dependencies": dependencies or [], "prompt": f"PROMPTS/{step}.md", "notes": notes,
        "output": None, "error": None, "errors": [], "retry_count": 0, "last_attempt": None,
        "attempts": [],
    }
    write_json(p, task)
    log_event("TASK_CREATED", task_id=task_id, book_id=book_id, step=step, priority=priority)
    return task


def _deps_done(task):
    return all(task_path("DONE", d).exists() for d in task.get("dependencies", []))


def promote_inbox():
    moved = []
    for t in all_tasks(["INBOX"]):
        if _deps_done(t):
            _move(t, "INBOX", "READY")
            moved.append(t["task_id"])
    return moved


def claim_next(agent_id, types=None, book_id=None, include_auto=False):
    """Claim the highest-priority READY task this agent can do. Returns task or None."""
    agent = agents.get(agent_id)
    if agent.get("current_task"):
        try:
            st, cur = find(agent["current_task"])
            if st == "RUNNING" and cur.get("assigned_agent") == agent_id:
                raise FactoryError(f"{agent_id} ya tiene {cur['task_id']} en curso. Complétala, falla o libérala primero.")
        except FactoryError as e:
            if "en curso" in str(e):
                raise
    promote_inbox()
    cands = all_tasks(["READY"])
    cands.sort(key=lambda t: (states.PRIORITIES.get(t["priority"], 9), t["created_at"], t["task_id"]))
    for t in cands:
        if types and t["type"] not in types:
            continue
        if book_id and t["book_id"] != book_id:
            continue
        if t["auto"] and not include_auto:
            continue
        if t.get("assigned_agent") and t["assigned_agent"] != agent_id:
            continue
        if not agents.can_do(agent, t["role"]):
            continue
        if not _deps_done(t):
            continue
        book = books.load(t["book_id"])
        step = states.STEPS[t["type"]]
        if book["status"] not in step["from"]:
            # Obsolete task (book moved on). Never execute it.
            try:
                t["error"] = f"obsoleta: libro en {book['status']}"
                _move(t, "READY", "FAILED")
                log_event("TASK_OBSOLETE", task_id=t["task_id"], book_id=t["book_id"], state=book["status"])
            except FileNotFoundError:
                pass
            continue
        res = locks.book_resource(t["book_id"])
        if not locks.acquire(res, agent_id, t["task_id"]):
            continue  # another agent is working on this book
        try:
            os.rename(task_path("READY", t["task_id"]), task_path("RUNNING", t["task_id"]))
        except (FileNotFoundError, FileExistsError, PermissionError):
            locks.release(res, agent_id)
            continue  # lost the race
        t.update(status="RUNNING", assigned_agent=agent_id, started_at=now_iso(),
                 last_attempt=now_iso(), claimed_from_state=book["status"], error=None)
        t["attempts"].append({"agent": agent_id, "started_at": t["started_at"]})
        write_json(task_path("RUNNING", t["task_id"]), t)
        books.transition(t["book_id"], step["working"], agent_id, f"CLAIM {t['type']}", task_id=t["task_id"])
        b = books.load(t["book_id"])
        b["assigned_agent"] = agent_id
        books.save(b)
        agents.update(agent_id, status="BUSY", current_task=t["task_id"])
        log_event("TASK_CLAIMED", task_id=t["task_id"], book_id=t["book_id"], agent=agent_id, step=t["type"])
        return t
    agents.update(agent_id, status="IDLE", current_task=None)
    return None


def _require_running(task_id, agent_id):
    st, t = find(task_id)
    if st != "RUNNING":
        raise FactoryError(f"{task_id} no está RUNNING (está {st})")
    if t.get("assigned_agent") != agent_id:
        raise FactoryError(f"{task_id} está asignada a {t.get('assigned_agent')}, no a {agent_id}")
    lk = locks.read_lock(locks.book_resource(t["book_id"]))
    if not lk or lk.get("agent") != agent_id:
        raise FactoryError(f"{agent_id} ya no tiene el lock de {t['book_id']} (¿expiró? ejecuta recover)")
    return t


def _finish(t, agent_id, to_status):
    _move(t, "RUNNING", to_status)
    locks.release(locks.book_resource(t["book_id"]), agent_id, force=True)
    b = books.load(t["book_id"])
    b["assigned_agent"] = None
    books.save(b)
    try:
        agents.update(agent_id, status="IDLE", current_task=None)
    except FactoryError:
        pass


def complete(task_id, agent_id, note="", usage=None):
    """Validate outputs independently, then advance the book. Invalid output = failed attempt."""
    t = _require_running(task_id, agent_id)
    book = books.load(t["book_id"])
    step = states.STEPS[t["type"]]
    errors, warnings = validators.validate(t["type"], book)
    if errors:
        return fail(task_id, agent_id, "Validación fallida: " + " | ".join(errors))
    done_state, out = validators.apply(t["type"], book, agent_id)
    done_state = done_state or step["done"]
    t.update(completed_at=now_iso(), output=out, error=None)
    t["warnings"] = warnings
    t["attempts"][-1].update(ended_at=t["completed_at"], result="DONE", note=note, usage=usage)
    write_json(task_path("RUNNING", task_id), t)
    books.transition(t["book_id"], done_state, agent_id, f"COMPLETE {t['type']}", "OK", task_id, note or None)
    _finish(t, agent_id, "DONE")
    log_event("TASK_DONE", task_id=task_id, book_id=t["book_id"], agent=agent_id, step=t["type"],
              warnings=len(warnings), usage=usage)
    return {"task": task_id, "result": "DONE", "book_state": done_state, "warnings": warnings}


def fail(task_id, agent_id, error, permanent=False):
    t = _require_running(task_id, agent_id)
    cfg = load_config()
    t["retry_count"] += 1
    t["error"] = error
    t["errors"].append({"at": now_iso(), "agent": agent_id, "error": error})
    t["attempts"][-1].update(ended_at=now_iso(), result="FAILED", error=error)
    write_json(task_path("RUNNING", task_id), t)
    back = t["claimed_from_state"]
    if permanent or t["retry_count"] >= cfg["max_retries"]:
        books.transition(t["book_id"], back, agent_id, f"FAIL {t['type']}", "FAILED", task_id, error)
        books.transition(t["book_id"], "BLOCKED", agent_id, f"BLOCK {t['type']}", "MAX_RETRIES" if not permanent else "PERMANENT", task_id, error)
        _finish(t, agent_id, "BLOCKED")
        log_event("TASK_BLOCKED", task_id=task_id, book_id=t["book_id"], agent=agent_id, error=error)
        return {"task": task_id, "result": "BLOCKED", "retry_count": t["retry_count"], "error": error}
    books.transition(t["book_id"], back, agent_id, f"FAIL {t['type']}", "RETRY", task_id, error)
    _finish(t, agent_id, "READY")
    log_event("TASK_FAILED", task_id=task_id, book_id=t["book_id"], agent=agent_id, error=error,
              retry_count=t["retry_count"])
    return {"task": task_id, "result": "RETRY", "retry_count": t["retry_count"], "error": error}


def release(task_id, agent_id, reason="released"):
    """Give a task back WITHOUT counting a retry (e.g. usage limit reached). Work files are kept."""
    t = _require_running(task_id, agent_id)
    t["attempts"][-1].update(ended_at=now_iso(), result="RELEASED", note=reason)
    write_json(task_path("RUNNING", task_id), t)
    books.transition(t["book_id"], t["claimed_from_state"], agent_id, f"RELEASE {t['type']}", "RELEASED", task_id, reason)
    _finish(t, agent_id, "READY")
    log_event("TASK_RELEASED", task_id=task_id, book_id=t["book_id"], agent=agent_id, reason=reason)
    return {"task": task_id, "result": "RELEASED"}


def unblock(task_id, by, note=""):
    """Human action: put a BLOCKED task back in READY with a fresh retry budget."""
    st, t = find(task_id)
    if st != "BLOCKED":
        raise FactoryError(f"{task_id} no está BLOCKED")
    book = books.load(t["book_id"])
    if book["status"] == "BLOCKED":
        books.transition(t["book_id"], book["blocked_from"], by, "UNBLOCK", "OK", task_id, note)
    t["retry_count"] = 0
    t["notes"] = (t.get("notes", "") + f"\n[UNBLOCK {by}] {note}").strip()
    _move(t, "BLOCKED", "READY")
    log_event("TASK_UNBLOCKED", task_id=task_id, by=by, note=note)
    return t


def heartbeat(agent_id):
    a = agents.update(agent_id)
    n = 0
    for lk in locks.all_locks():
        if lk.get("agent") == agent_id and locks.heartbeat(lk["resource"], agent_id):
            n += 1
    return {"agent": agent_id, "locks_extended": n, "current_task": a.get("current_task")}

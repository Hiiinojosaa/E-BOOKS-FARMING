"""File locks with TTL.

acquire  -> atomic exclusive create (tmp + hard link): only one process can win, never a half-written lock.
check    -> read lock, see owner and expiry.
release  -> only the owner may release (or recover, for expired locks).
recover  -> expired locks are removed so they never block the project forever.
heartbeat-> owner extends expiry while doing long work.
"""
import json
import os
import time

from .core import (FactoryError, create_exclusive_json, iso_plus_minutes, load_config, log_event, now_iso, parse_iso,
                   path, utcnow, write_json)


def _lock_path(resource):
    safe = resource.replace("/", "__").replace(":", "_")
    return path("LOCKS", safe + ".lock")


def read_lock(resource):
    p = _lock_path(resource)
    if not p.exists():
        return None
    for _ in range(20):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, OSError):
            time.sleep(0.02)  # being written/replaced right now
    # Still unreadable after ~0.4 s: corrupt. Treat as expired only if it is old, never a fresh one.
    try:
        age = time.time() - p.stat().st_mtime
    except FileNotFoundError:
        return None
    exp = "1970-01-01T00:00:00Z" if age > 60 else iso_plus_minutes(1)
    return {"resource": resource, "agent": "?", "expires_at": exp}


def is_expired(lock):
    exp = parse_iso(lock.get("expires_at"))
    return exp is None or exp < utcnow()


def acquire(resource, agent, task_id=None, ttl_minutes=None):
    """Return True if acquired. Expired locks are reclaimed transparently."""
    ttl = ttl_minutes or load_config()["lock_ttl_minutes"]
    p = _lock_path(resource)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "resource": resource, "agent": agent, "task_id": task_id,
        "acquired_at": now_iso(), "expires_at": iso_plus_minutes(ttl), "pid": os.getpid(),
    }
    for _ in range(2):
        try:
            create_exclusive_json(p, data)
        except FileExistsError:
            cur = read_lock(resource)
            if cur and cur.get("agent") == agent and cur.get("task_id") == task_id:
                heartbeat(resource, agent, ttl)  # re-entrant for same owner+task
                return True
            if cur and is_expired(cur):
                _break(resource, cur, reason="expired on acquire")
                continue
            return False
        return True
    return False


def release(resource, agent, force=False):
    cur = read_lock(resource)
    if cur is None:
        return False
    if cur.get("agent") != agent and not force:
        raise FactoryError(f"Lock {resource} pertenece a {cur.get('agent')}, no a {agent}")
    try:
        os.remove(_lock_path(resource))
    except FileNotFoundError:
        return False
    return True


def heartbeat(resource, agent, ttl_minutes=None):
    cur = read_lock(resource)
    if not cur or cur.get("agent") != agent:
        return False
    cur["expires_at"] = iso_plus_minutes(ttl_minutes or load_config()["lock_ttl_minutes"])
    cur["heartbeat_at"] = now_iso()
    write_json(_lock_path(resource), cur)
    return True


def _break(resource, cur, reason):
    try:
        os.remove(_lock_path(resource))
    except FileNotFoundError:
        return
    log_event("LOCK_BROKEN", resource=resource, previous_agent=cur.get("agent"),
              task_id=cur.get("task_id"), reason=reason)


def all_locks():
    d = path("LOCKS")
    out = []
    if d.exists():
        for f in sorted(d.glob("*.lock")):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                out.append({"resource": f.stem, "agent": "?", "expires_at": "1970-01-01T00:00:00Z"})
    return out


def recover_expired():
    broken = []
    for lk in all_locks():
        if is_expired(lk):
            _break(lk["resource"], lk, reason="expired (recover)")
            broken.append(lk["resource"])
    return broken


def book_resource(book_id):
    return f"book-{book_id}"

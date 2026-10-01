"""AGENT_REGISTRY: one JSON file per agent in AGENTS/ (no shared file -> no git conflicts)."""
import re

from . import states
from .core import FactoryError, load_config, log_event, now_iso, parse_iso, path, read_json, utcnow, write_json

ALL_ROLES = sorted({s["role"] for s in states.STEPS.values()} | {"ORCHESTRATOR", "METADATA_AGENT",
                   "PUBLISHING_PREPARATION_AGENT", "REPORTING_AGENT"})
AGENT_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,40}$")


def agent_file(agent_id):
    return path("AGENTS", f"{agent_id}.json")


def register(agent_id, owner, provider="anthropic", model="", capabilities=None, notes=""):
    if not AGENT_ID_RE.match(agent_id):
        raise FactoryError("agent_id debe ser MAYÚSCULAS/números/guiones, p.ej. S1-CLAUDE-001 o DANI-AGENT-001")
    caps = capabilities or ["*"]
    bad = [c for c in caps if c != "*" and c not in ALL_ROLES]
    if bad:
        raise FactoryError(f"Capacidades desconocidas: {bad}. Válidas: * o {ALL_ROLES}")
    f = agent_file(agent_id)
    data = read_json(f, default={}) or {}
    data.update({
        "agent_id": agent_id, "owner": owner, "provider": provider, "model": model,
        "capabilities": caps, "status": data.get("status", "IDLE"),
        "current_task": data.get("current_task"), "last_seen": now_iso(),
        "registered_at": data.get("registered_at", now_iso()), "notes": notes,
    })
    write_json(f, data)
    log_event("AGENT_REGISTERED", agent=agent_id, owner=owner, model=model)
    return data


def get(agent_id):
    f = agent_file(agent_id)
    if not f.exists():
        raise FactoryError(f"Agente no registrado: {agent_id}. Ejecuta: python factory.py agent register ...")
    return read_json(f)


def update(agent_id, **fields):
    data = get(agent_id)
    data.update(fields)
    data["last_seen"] = now_iso()
    write_json(agent_file(agent_id), data)
    return data


def all_agents():
    d = path("AGENTS")
    return [read_json(f) for f in sorted(d.glob("*.json"))] if d.exists() else []


def can_do(agent, role):
    caps = agent.get("capabilities", ["*"])
    return "*" in caps or role in caps


def mark_offline_stale():
    limit = load_config()["agent_offline_minutes"] * 60
    changed = []
    for a in all_agents():
        seen = parse_iso(a.get("last_seen"))
        if a.get("status") != "OFFLINE" and seen and (utcnow() - seen).total_seconds() > limit:
            a["status"] = "OFFLINE"
            write_json(agent_file(a["agent_id"]), a)
            changed.append(a["agent_id"])
    return changed

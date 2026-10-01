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
        "role": data.get("role"), "label": data.get("label"), "prompt": data.get("prompt", "PROMPTS/WORKER.md"),
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


# The specialist team. Each role only receives the tasks of its capabilities; the chief can do anything
# (so a single session still moves the whole pipeline) but its first job is talking to the partners.
TEAM = [
    {"role": "JEFE", "label": "Jefe", "caps": ["*"], "prompt": "PROMPTS/CHIEF.md",
     "desc": "Habla con vosotros en el chat, os recomienda temas, sigue vuestras directrices y coordina al equipo."},
    {"role": "INVESTIGADOR", "label": "Investigador", "caps": ["RESEARCH_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Estudia el nicho y la competencia y prepara el plan de cada libro."},
    {"role": "ESCRITOR", "label": "Escritor", "caps": ["WRITER_AGENT", "TRANSLATOR_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Escribe los libros y las ediciones en otros idiomas."},
    {"role": "EDITOR", "label": "Editor", "caps": ["EDITOR_AGENT", "FACT_CHECK_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Corrige el texto, comprueba los datos y arregla lo que falle."},
    {"role": "DISENADOR", "label": "Diseñador", "caps": ["DESIGN_AGENT", "FORMAT_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Hace la portada y maqueta el EPUB y el PDF."},
    {"role": "EMPAQUETADOR", "label": "Empaquetador", "caps": ["MARKET_AGENT", "METADATA_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Pone título, descripción, palabras clave, categorías y precio."},
    {"role": "CALIDAD", "label": "Calidad", "caps": ["QC_AGENT"], "prompt": "PROMPTS/WORKER.md",
     "desc": "Revisa cada libro antes de que os llegue."},
]


def setup_team(owner, prefix, model="claude"):
    out = []
    for m in TEAM:
        aid = f"{prefix}-{m['role']}"
        a = register(aid, owner, "anthropic", model, m["caps"], notes=m["desc"])
        a.update(role=m["role"], label=m["label"], prompt=m["prompt"])
        write_json(agent_file(aid), a)
        out.append(aid)
    return out


def ensure_system(agent_id):
    """Register a script agent (for automatic FORMAT tasks) if it does not exist yet."""
    try:
        return get(agent_id)
    except FactoryError:
        return register(agent_id, "SYSTEM", provider="script", model="factory", capabilities=["FORMAT_AGENT"],
                        notes="Agente de sistema para tareas automáticas (maquetación)")


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

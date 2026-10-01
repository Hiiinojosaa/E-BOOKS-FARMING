"""Core utilities: project root, JSON I/O (atomic), time, events log, config.

Everything is stdlib-only so any agent on any machine can run the factory
without installing packages.
"""
import datetime
import json
import os
import re
import time
from pathlib import Path

# abspath, NOT resolve(): on Windows resolve() can follow app-container redirections (e.g. MSIX
# LocalCache) to paths that external programs like Chrome cannot see.
_ROOT = Path(os.path.abspath(os.environ.get("EBF_ROOT") or Path(__file__).parent.parent))


class FactoryError(Exception):
    """Expected, user-facing error (bad state, missing file, lock held...)."""


def set_root(p):
    global _ROOT
    _ROOT = Path(os.path.abspath(p))


def root():
    return _ROOT


def path(*parts):
    return _ROOT.joinpath(*parts)


def rel(p):
    try:
        return Path(os.path.abspath(p)).relative_to(_ROOT).as_posix()
    except ValueError:
        return str(p)


# ---------------------------------------------------------------- time
def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def now_iso():
    return utcnow().isoformat().replace("+00:00", "Z")


def parse_iso(s):
    if not s:
        return None
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso_plus_minutes(minutes):
    return (utcnow() + datetime.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- json io
def retry_io(fn, *args, attempts=40, delay=0.025):
    """Windows: rename/replace/open fail with PermissionError while another process has the
    file open for a moment. Retry briefly instead of crashing (no effect on POSIX)."""
    for i in range(attempts):
        try:
            return fn(*args)
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay * (1 + i % 5))


def _load_json(p):
    for i in range(20):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            if i == 19:
                raise
            time.sleep(0.02)  # file being replaced right now; read again


def create_exclusive_json(p, data):
    """Create p with its full content, failing with FileExistsError if it already exists.
    tmp + os.link is atomic on NTFS and POSIX, so readers never see an empty or partial file."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        os.link(tmp, p)
    finally:
        os.remove(tmp)


def read_json(p, default=None):
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        raise FactoryError(f"Archivo no encontrado: {rel(p)}")
    try:
        return retry_io(_load_json, p)
    except FileNotFoundError:
        # moved by another agent between exists() and open()
        if default is not None:
            return default
        raise FactoryError(f"Archivo no encontrado: {rel(p)}")


def write_json(p, data):
    """Atomic write: tmp file in same dir + os.replace (never leaves half files)."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    retry_io(os.replace, tmp, p)


def write_text(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    retry_io(os.replace, tmp, p)


def read_text(p, default=None):
    p = Path(p)
    if not p.exists():
        if default is not None:
            return default
        raise FactoryError(f"Archivo no encontrado: {rel(p)}")
    return p.read_text(encoding="utf-8")


def append_jsonl(p, record):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)


def read_jsonl(p):
    p = Path(p)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # tolerate a torn line rather than crash reporting
    return out


# ---------------------------------------------------------------- events
def log_event(etype, **fields):
    """Global append-only event log, one file per UTC day (merge=union in git)."""
    rec = {"ts": now_iso(), "type": etype}
    rec.update({k: v for k, v in fields.items() if v is not None})
    append_jsonl(path("LOGS", "events", utcnow().strftime("%Y-%m-%d") + ".jsonl"), rec)
    return rec


def all_events():
    d = path("LOGS", "events")
    out = []
    if d.exists():
        for f in sorted(d.glob("*.jsonl")):
            out.extend(read_jsonl(f))
    return out


# ---------------------------------------------------------------- config
DEFAULT_CONFIG = {
    "project_name": "E-Book Factory",
    "default_author": "TBD-PEN-NAME",
    "publisher": "",
    "partners": ["SOCIO-1", "DANI"],
    "approvals_required": 1,
    "lock_ttl_minutes": 90,
    "agent_offline_minutes": 180,
    "max_retries": 3,
    "max_qc_failures": 2,
    "max_active_books": 5,
    "auto_promote_ideas": True,
    "brief_approval": "auto",
    "max_tasks_per_session": 12,
    "trim_size": {"width_in": 6, "height_in": 9},
    "cover_size_px": {"width": 1600, "height": 2560},
    "chrome_path": "",
    "git": {"sync_enabled": False, "remote": "origin", "branch": "main"},
    "high_risk_keywords": [
        "medic", "health", "salud", "diet", "nutri", "supplement", "suplement",
        "legal", "law", "ley", "tax", "impuesto", "fiscal", "invest", "inver",
        "crypto", "finanz", "financ", "mental illness", "therapy", "terapia",
        "pregnan", "embaraz", "drug", "fármaco", "farmac",
    ],
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = read_json(path("CONFIG", "factory.json"), default={})
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def slugify(text, maxlen=60):
    text = text.lower()
    repl = str.maketrans("áéíóúüñàèìòùç", "aeiouunaeiouc")
    text = text.translate(repl)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:maxlen].strip("-") or "book"


def word_count(text):
    return len(re.findall(r"\b[\w'’-]+\b", text))

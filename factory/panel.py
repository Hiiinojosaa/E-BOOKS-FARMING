"""Partners' panel: `python factory.py panel` (or ABRIR_PANEL.bat) -> http://127.0.0.1:8765

- Login per partner with a PIN that each partner creates on first use. PINs are stored hashed in
  CONFIG/local_users.json, which is git-ignored: they never leave the computer.
- Live updates via Server-Sent Events (/api/stream): the page refreshes the moment something changes.
- Chat with the factory: a partner message creates an ORDER; the agent's answer comes back in the chat.
The panel never starts agents; it writes to the same files they read (and syncs them through git).
"""
import hashlib
import json
import mimetypes
import os
import secrets
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import agents, books, chat, decisions, directives, gitsync, orchestrator, orders, pg_sync, publishing, reports, states, tasks
from .core import (FactoryError, all_events, load_config, log_event, now_iso, parse_iso, path, read_json, read_text, utcnow,
                   word_count, write_json)

ACTION_LOCK = threading.Lock()
SYNC = {"at": None, "result": "nunca", "enabled": False}
SESSIONS = {}  # token -> {"partner", "expires"}
FAILS = {}     # partner -> [count, locked_until]
SERVE_ROOTS = ("BOOKS", "REPORTS")
SESSION_HOURS = 12

# Book journey shown to the partners (plain language), in order.
JOURNEY = [("Idea", ["IDEA", "RESEARCH_PENDING"]),
           ("Investigación", ["RESEARCHING", "RESEARCH_COMPLETE", "BRIEFING", "BRIEF_READY", "WRITING_PENDING", "TRANSLATION_PENDING"]),
           ("Escritura", ["WRITING", "DRAFT_COMPLETE", "TRANSLATING", "TRANSLATED"]),
           ("Edición", ["EDITING", "EDITED", "FACT_CHECKING", "FACT_CHECKED"]),
           ("Portada", ["METADATA_IN_PROGRESS", "DESIGN_PENDING", "DESIGNING", "DESIGN_COMPLETE"]),
           ("Maquetación y control", ["FORMATTING", "QC_PENDING", "QC", "QC_FAILED", "FIXING", "QC_PASSED"]),
           ("Vuestra revisión", ["HUMAN_REVIEW", "CHANGES_REQUIRED", "APPROVED"]),
           ("Listo", ["READY_FOR_PUBLISHING"]),
           ("Publicado", ["PUBLISHED"])]
OUTPUT_FILE = {"WRITE": "manuscript/draft.md", "TRANSLATE": "manuscript/draft.md", "EDIT": "manuscript/edited.md",
               "FACT_CHECK": "manuscript/final.md"}


# ------------------------------------------------------------------ auth
def _users_file():
    return path("CONFIG", "local_users.json")


def _users():
    return read_json(_users_file(), default={}) or {}


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()


def partner_names():
    cfg = load_config()
    names = cfg.get("partner_names") or {}
    return {p: names.get(p) or p for p in cfg["partners"]}


def login(partner, pin, name=None):
    if partner not in load_config()["partners"]:
        raise FactoryError("Perfil desconocido")
    pin = str(pin or "").strip()
    cnt, until = FAILS.get(partner, [0, 0])
    if until > time.time():
        raise FactoryError(f"Demasiados intentos. Espera {int(until - time.time())} s")
    users = _users()
    if partner not in users:  # first time on this computer: create the password
        if not 4 <= len(pin) <= 40:
            raise FactoryError("La contraseña debe tener entre 4 y 40 caracteres")
        salt = secrets.token_hex(16)
        users[partner] = {"salt": salt, "pin": _hash(pin, salt), "created_at": now_iso()}
        write_json(_users_file(), users)
        if name and name.strip():
            set_name(partner, name.strip())
    elif not secrets.compare_digest(users[partner]["pin"], _hash(pin, users[partner]["salt"])):
        cnt += 1
        FAILS[partner] = [cnt, time.time() + 30 if cnt >= 5 else 0]
        raise FactoryError("PIN incorrecto")
    FAILS.pop(partner, None)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"partner": partner, "expires": time.time() + SESSION_HOURS * 3600}
    return token


def set_name(partner, name):
    p = path("CONFIG", "factory.json")
    cfg = read_json(p, default={})
    cfg.setdefault("partner_names", {})[partner] = name[:40]
    write_json(p, cfg)


def change_pin(partner, old, new):
    users = _users()
    u = users.get(partner)
    if not u or not secrets.compare_digest(u["pin"], _hash(str(old), u["salt"])):
        raise FactoryError("Contraseña actual incorrecta")
    if not 4 <= len(str(new)) <= 40:
        raise FactoryError("La contraseña nueva debe tener entre 4 y 40 caracteres")
    salt = secrets.token_hex(16)
    users[partner] = {"salt": salt, "pin": _hash(str(new), salt), "created_at": u["created_at"], "changed_at": now_iso()}
    write_json(_users_file(), users)


# ------------------------------------------------------------------ state
def _stage(status):
    for i, (_, sts) in enumerate(JOURNEY):
        if status in sts:
            return i
    return None


def _shelf(b):
    s = b["status"]
    if s == "HUMAN_REVIEW" or (s == "BRIEF_READY" and not b.get("brief_approved")):
        return "review"
    if s == "READY_FOR_PUBLISHING":
        return "ready"
    if s == "PUBLISHED":
        return "published"
    if s in ("IDEA",):
        return "ideas"
    if s == "REJECTED":
        return "discarded"
    if s == "BLOCKED":
        return "stopped"
    return "production"


def _book_summary(b):
    return {k: b.get(k) for k in ("id", "title", "subtitle", "language", "status", "priority", "assigned_agent", "risk_level",
                                   "qc_status", "page_count", "updated_at", "created_at", "author", "translated_from",
                                   "brief_approved", "word_count_target", "blocked_from", "topic")} | {
        "has_cover": (books.book_dir(b["id"]) / "design" / "cover.png").exists(),
        "stage": _stage(b["status"]), "shelf": _shelf(b), "flags": len(b.get("flags", [])),
        "price": (b.get("price_suggested") or {}).get("amount"),
    }


def _live():
    out = []
    for t in tasks.all_tasks(["RUNNING"]):
        try:
            b = books.load(t["book_id"])
        except FactoryError:
            continue
        item = {"task_id": t["task_id"], "agent": t.get("assigned_agent"), "book_id": t["book_id"], "title": b["title"],
                "step": t["type"], "started_at": t.get("started_at"), "words": None, "target": b.get("word_count_target")}
        rel = OUTPUT_FILE.get(t["type"])
        if rel:
            f = books.book_dir(t["book_id"]) / rel
            if f.exists():
                item["words"] = word_count(read_text(f))
        out.append(item)
    return out


def _attention(all_b):
    items = []
    for b in all_b:
        if b["status"] == "HUMAN_REVIEW":
            items.append({"kind": "review", "book_id": b["id"], "title": b["title"]})
        elif b["status"] == "BRIEF_READY" and not b.get("brief_approved"):
            items.append({"kind": "brief", "book_id": b["id"], "title": b["title"]})
        elif b["status"] == "IDEA" and b.get("idea_approved", True):
            items.append({"kind": "start", "book_id": b["id"], "title": b["title"]})
    for t in tasks.all_tasks(["BLOCKED"]):
        items.append({"kind": "blocked", "task_id": t["task_id"], "book_id": t["book_id"], "step": t["type"],
                      "error": (t.get("error") or "")[:200]})
    for d in decisions.all_decisions("OPEN"):
        act = d.get("action") or {}
        if act.get("type") == "approve_idea":
            try:
                b = books.load(act["book_id"])
            except FactoryError:
                continue
            items.append({"kind": "recommendation", "decision_id": d["id"], "book_id": b["id"], "title": b["title"],
                          "language": b["language"], "why": b.get("recommendation") or "", "by": d["asked_by"],
                          "options": d.get("options", [])})
        else:
            items.append({"kind": "question", "decision_id": d["id"], "question": d["question"], "options": d.get("options", []),
                          "by": d["asked_by"]})
    return items


def _team(ags):
    by_role = {}
    for a in ags:
        if a.get("role"):
            by_role.setdefault(a["role"], []).append(a["agent_id"])
    return [{"role": m["role"], "label": m["label"], "desc": m["desc"], "prompt": m["prompt"], "agents": by_role.get(m["role"], [])}
            for m in agents.TEAM]


def state(partner):
    from .cli import capacity
    all_b = books.all_books()
    cfg = load_config()
    ags = [a for a in agents.all_agents() if a.get("owner") not in ("SYSTEM", "test")]
    now = utcnow()
    for a in ags:
        seen = parse_iso(a.get("last_seen"))
        a["minutes_ago"] = int((now - seen).total_seconds() // 60) if seen else None
    dec_open = {d["id"] for d in decisions.all_decisions("OPEN")}
    msgs = chat.all_messages(300)
    for m in msgs:
        m["open"] = bool(m.get("decision_id") in dec_open and m["kind"] == "question")
    open_orders = orders.all_orders(["OPEN", "IN_PROGRESS"])
    return {
        "now": now_iso(), "me": partner, "names": partner_names(), "default_author": cfg["default_author"],
        "main_agent": cfg.get("main_agent") or "S1-CLAUDE-001",
        "books": [_book_summary(b) for b in sorted(all_b, key=lambda b: b["updated_at"], reverse=True)],
        "journey": [j[0] for j in JOURNEY],
        "live": _live(), "agents": ags, "attention": _attention(all_b),
        "chat": msgs, "pending_orders": [{k: o[k] for k in ("id", "status", "taken_by", "chat_msg", "text")} for o in open_orders],
        "events": list(reversed(all_events()[-80:])),
        "queue": len(tasks.all_tasks(["READY"])),
        "capacity": capacity(), "directives": directives.active(), "team": _team(ags),
        "week": reports._week_stats(all_b),
        "sync": SYNC, "steps": list(states.STEPS), "languages": ["en-US", "en-GB", "es-ES", "es-MX"],
    }


def book_detail(bid):
    b = books.load(bid)
    bdir = books.book_dir(bid)
    files = sorted(str(p.relative_to(bdir)).replace("\\", "/") for p in bdir.rglob("*")
                   if p.is_file() and not p.name.endswith((".tmp", "cover.html", "interior.html")))
    return {"book": b, "stage": _stage(b["status"]), "history": books.history(bid)[-60:], "files": files,
            "review": read_text(bdir / "review" / "HUMAN_REVIEW.md", default=""),
            "description": (read_json(bdir / "metadata" / "metadata.json", default={}) or {}).get("description", "")}


def signature():
    """Changes whenever something the partners should see changes (used by the live stream)."""
    parts = [chat.latest_marker()]
    ev = path("LOGS", "events", utcnow().strftime("%Y-%m-%d") + ".jsonl")
    parts.append(str(ev.stat().st_size) if ev.exists() else "0")
    for t in tasks.all_tasks(["RUNNING"]):
        rel = OUTPUT_FILE.get(t["type"])
        f = books.book_dir(t["book_id"]) / rel if rel else None
        parts.append(f"{t['task_id']}:{f.stat().st_size if f and f.exists() else 0}")
    parts.append(str(SYNC.get("at")))
    return "|".join(parts)


# ------------------------------------------------------------------ actions
def _sync(by, msg):
    if not gitsync.enabled():
        SYNC.update(at=now_iso(), result="desactivado", enabled=False)
        return SYNC
    r = gitsync.sync(by, msg)
    SYNC.update(at=now_iso(), result=r.get("sync"), error=r.get("error"), enabled=True)
    return SYNC


def _agents_working():
    return [a for a in agents.all_agents() if a.get("status") == "BUSY" and a.get("owner") not in ("SYSTEM",)]


def do_action(a, by):
    """`by` comes from the logged-in session, never from the browser payload."""
    if not by:
        raise FactoryError("Sesión no válida")
    act = a.get("action")
    res = None
    if act == "directive_add":
        res = directives.add(a.get("text"), by)["id"]
    elif act == "directive_remove":
        res = directives.remove(a["id"], by)["id"]
    elif act == "chat_send":
        text = (a.get("text") or "").strip()
        if not text:
            raise FactoryError("Escribe un mensaje")
        to = a.get("to") or "factory"
        target_agent = to if to != "factory" else None
        msg = chat.post(by, "partner", text, to=to, book_id=a.get("book") or None)
        o = orders.create(text, by, "CHAT", target_agent=target_agent, book_id=a.get("book") or None, chat_msg=msg["id"])
        working = _agents_working()
        target_working = [x for x in working if not target_agent or x["agent_id"] == target_agent]
        if target_working:
            ack = f"Recibido. {', '.join(x['agent_id'] for x in target_working)} está trabajando ahora y te responderá aquí al terminar su tarea actual."
        elif target_agent:
            label = next((x.get("label") or x["agent_id"] for x in agents.all_agents() if x["agent_id"] == target_agent), target_agent)
            ack = f"Recibido. {label} no está encendido ahora mismo: tu mensaje queda en cola para cuando arranque."
        else:
            ack = "Recibido. Ahora mismo no hay ningún agente encendido: tu mensaje queda en cola y el primero que arranque lo atenderá y te responderá aquí."
        chat.post("Fábrica", "system", ack, kind="note", order_id=o["id"], reply_to=msg["id"])
        res = msg["id"]
    elif act == "set_target":
        n = int(a.get("target") or 0)
        if not 1 <= n <= 100:
            raise FactoryError("El objetivo debe estar entre 1 y 100 libros al día")
        p = path("CONFIG", "factory.json")
        cfg = read_json(p, default={})
        cfg["daily_target"] = n
        write_json(p, cfg)
        chat.post("Fábrica", "system", f"{partner_names().get(by, by)} ha fijado el objetivo en {n} libros al día.", kind="note")
        res = n
    elif act == "answer_question":
        res = decisions.answer(a["id"], by, a["answer"])["id"]
        orchestrator.orchestrate(by)  # an approved recommendation enters the queue right away
    elif act == "start_production":
        b = books.load(a["id"])
        if b["status"] != "IDEA" or not b.get("idea_approved", True):
            raise FactoryError("Esta idea todavía no se puede producir")
        books.transition(a["id"], "RESEARCH_PENDING", by, "PROMOTE_IDEA", note=f"Producción iniciada por {by}")
        chat.post("Fábrica", "system", f"{partner_names().get(by, by)} ha puesto a producir «{b['title']}».", kind="note", book_id=a["id"])
        res = orchestrator.orchestrate(by)
    elif act == "new_book":
        langs = [l for l in (a.get("target_languages") or []) if l]
        b = books.create(a["topic"], a.get("language", "en-US"), agent=by, priority=a.get("priority", "NORMAL"),
                         niche=a.get("niche", ""), target_audience=a.get("audience", ""), target_languages=langs,
                         word_count_target=int(a.get("words") or 6000), notes=a.get("notes", ""))
        chat.post("Fábrica", "system", f"{partner_names().get(by, by)} ha añadido la idea «{b['title']}».", kind="note", book_id=b["id"])
        res = {"id": b["id"]}
    elif act == "approve":
        price = float(str(a["price"]).replace(",", ".")) if str(a.get("price") or "").strip() else None
        res = publishing.approve(a["id"], by, a.get("notes", ""), (a.get("author") or "").strip() or None, price)
    elif act == "request_changes":
        if not (a.get("notes") or "").strip():
            raise FactoryError("Explica qué hay que cambiar")
        publishing.request_changes(a["id"], by, a["notes"], a.get("restart_at", "EDIT"))
        res = orchestrator.orchestrate(by)
    elif act == "reject":
        res = publishing.reject(a["id"], by, a.get("notes", ""))["status"]
    elif act == "approve_brief":
        publishing.approve_brief(a["id"], by)
        res = orchestrator.orchestrate(by)
    elif act == "set_priority":
        if a["priority"] not in states.PRIORITIES:
            raise FactoryError("Prioridad inválida")
        b = books.load(a["id"]); b["priority"] = a["priority"]; books.save(b)
        for t in tasks.all_tasks(["READY", "INBOX"]):
            if t["book_id"] == a["id"]:
                t["priority"] = a["priority"]
                write_json(tasks.task_path(t["status"], t["task_id"]), t)
        log_event("BOOK_UPDATED", book_id=a["id"], by=by, fields=[f"priority={a['priority']}"])
        res = a["priority"]
    elif act == "translate":
        b = books.load(a["id"]); lang = books.norm_lang(a["to"])
        if lang not in b["target_languages"]:
            b["target_languages"].append(lang); books.save(b)
        log_event("TRANSLATION_REQUESTED", book_id=a["id"], language=lang, by=by)
        res = orchestrator.spawn_translations(books.load(a["id"]), by) \
            if states.STATES.index(b["status"]) >= states.STATES.index("FACT_CHECKED") and b["status"] not in ("REJECTED", "BLOCKED") \
            else f"Se creará cuando {a['id']} termine la edición"
    elif act == "unblock":
        res = tasks.unblock(a["task"], by, a.get("note", ""))["task_id"]
    elif act == "mark_published":
        res = publishing.mark_published(a["id"], by, a.get("platform") or "KDP", a.get("url", ""))["status"]
    elif act == "tick":
        agent = "PANEL-AUTO"
        agents.ensure_system(agent)
        rec = orchestrator.recover(agent)
        orch = orchestrator.orchestrate(agent)
        from .cli import _run_auto
        auto = _run_auto(agent)
        orch += orchestrator.orchestrate(agent)
        reports.all_reports()
        res = {"recover": {k: len(v) for k, v in rec.items()}, "orchestrate": orch, "auto": auto}
    elif act == "set_name":
        set_name(by, (a.get("name") or "").strip() or by)
        res = "ok"
    elif act == "change_pin":
        change_pin(by, a.get("old"), a.get("new"))
        return {"ok": True, "result": "PIN cambiado"}  # local only: nothing to sync
    elif act == "sync":
        return {"ok": True, "result": _sync(by, "panel sync")}
    else:
        raise FactoryError(f"Acción desconocida: {act}")
    sync = _sync(by, f"panel: {act} {a.get('id') or a.get('task') or ''}".strip())
    _pg_push_state(by)
    return {"ok": True, "result": res, "sync": sync}


# ------------------------------------------------------------------ remote panel bridge (Postgres)
def _pg_push_state(by):
    if not pg_sync.enabled():
        return
    try:
        pg_sync.push_state(state(by))
    except Exception as e:  # noqa: BLE001 - never let the remote bridge break a local action
        print(f"[pg_sync] push_state fallo: {e}")


def _pg_tick(agent):
    if not pg_sync.enabled():
        return
    try:
        pg_sync.push_users()
        for row in pg_sync.pull_pending_actions():
            try:
                result = do_action(row["payload"], row["partner"])
                pg_sync.mark_action_done(row["id"], result)
            except FactoryError as e:
                pg_sync.mark_action_error(row["id"], str(e))
            except Exception as e:  # noqa: BLE001
                pg_sync.mark_action_error(row["id"], f"{type(e).__name__}: {e}")
        _pg_push_state(agent)
        for b in books.all_books():
            try:
                pg_sync.push_book_details(b["id"], book_detail(b["id"]))
            except Exception as e:  # noqa: BLE001
                print(f"[pg_sync] push_book_details({b['id']}) fallo: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[pg_sync] tick fallo: {e}")


def _background_pg_bridge(interval=6):
    agents.ensure_system("PG-BRIDGE")
    while True:
        time.sleep(interval)
        with ACTION_LOCK:
            _pg_tick("PG-BRIDGE")


# ------------------------------------------------------------------ http
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, default=str)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _partner(self):
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "ebf_session":
                s = SESSIONS.get(v)
                if s and s["expires"] > time.time():
                    return s["partner"], v
        return None, None

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (Path(__file__).parent / "panel.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            if u.path == "/api/me":
                p, _ = self._partner()
                users = _users()
                names = partner_names()
                return self._send(200, {"partner": p, "name": names.get(p) if p else None,
                                        "profiles": [{"id": x, "name": names[x], "has_pin": x in users} for x in load_config()["partners"]]})
            partner, _ = self._partner()
            if not partner:
                return self._send(401, {"error": "Inicia sesión"})
            if u.path == "/api/state":
                return self._send(200, state(partner))
            if u.path.startswith("/api/book/"):
                return self._send(200, book_detail(unquote(u.path.split("/")[-1])))
            if u.path == "/api/stream":
                return self._stream()
            if u.path.startswith("/files/"):
                rel = unquote(u.path[len("/files/"):])
                p = Path(os.path.abspath(path() / rel))
                if ".." in Path(rel).parts or rel.split("/")[0] not in SERVE_ROOTS or not p.is_file():
                    return self._send(404, {"error": "no encontrado"})
                ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                if p.suffix in (".md", ".json", ".txt", ".jsonl"):
                    ctype = "text/plain; charset=utf-8"
                return self._send(200, p.read_bytes(), ctype)
            return self._send(404, {"error": "no encontrado"})
        except FactoryError as e:
            return self._send(400, {"error": str(e)})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last, beat = None, time.time()
        try:
            while True:
                try:
                    sig = signature()
                except Exception:  # noqa: BLE001 - files moving under us; try again next tick
                    sig = last
                if sig != last:
                    self.wfile.write(b"data: changed\n\n")
                    self.wfile.flush()
                    last = sig
                elif time.time() - beat > 15:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    beat = time.time()
                time.sleep(1.5)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def do_POST(self):
        u = urlparse(self.path)
        if self.headers.get("X-EBF") != "1":  # cross-site forms cannot send custom headers
            return self._send(403, {"error": "petición rechazada"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            if u.path == "/api/login":
                token = login(payload.get("partner"), payload.get("pin"), payload.get("name"))
                return self._send(200, {"ok": True}, headers={
                    "Set-Cookie": f"ebf_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}"})
            if u.path == "/api/logout":
                _, tok = self._partner()
                SESSIONS.pop(tok, None)
                return self._send(200, {"ok": True}, headers={"Set-Cookie": "ebf_session=; Max-Age=0; Path=/"})
            if u.path != "/api/action":
                return self._send(404, {"error": "no encontrado"})
            partner, _ = self._partner()
            if not partner:
                return self._send(401, {"error": "Inicia sesión"})
            with ACTION_LOCK:
                return self._send(200, do_action(payload, partner))
        except FactoryError as e:
            return self._send(400, {"error": str(e)})
        except KeyError as e:
            return self._send(400, {"error": f"Falta el campo {e}"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})


def _background_sync(interval):
    while True:
        time.sleep(interval)
        if gitsync.enabled():
            with ACTION_LOCK:
                try:
                    _sync("PANEL", "panel auto-sync")
                except Exception as e:  # noqa: BLE001
                    SYNC.update(at=now_iso(), result="ERROR", error=str(e))


def serve(port=8765, open_browser=True, sync_every=60):
    SYNC["enabled"] = gitsync.enabled()
    if SYNC["enabled"]:
        _sync("PANEL", "panel start")
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=_background_sync, args=(sync_every,), daemon=True).start()
    if pg_sync.enabled():
        threading.Thread(target=_background_pg_bridge, daemon=True).start()
        print("Puente con el panel remoto (Postgres) activo.")
    url = f"http://127.0.0.1:{port}/"
    print(f"Panel en {url}  (deja esta ventana abierta; Ctrl+C para cerrar). Sincroniza con GitHub cada {sync_every}s.")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

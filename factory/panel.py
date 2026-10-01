"""Control panel for the partners: `python factory.py panel` -> http://127.0.0.1:8765

Local-only web UI over the same library functions the CLI uses. Every action is written to the repo
and (if git sync is on) pushed, so the other partner sees it after their panel syncs. Agents read the
same files: the panel never talks to agents directly.
"""
import json
import mimetypes
import secrets
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import agents, books, decisions, gitsync, orchestrator, orders, publishing, reports, states, tasks
from .core import FactoryError, all_events, load_config, log_event, now_iso, path, read_text, write_json

TOKEN = secrets.token_urlsafe(24)
ACTION_LOCK = threading.Lock()
SYNC = {"at": None, "result": "nunca", "enabled": False}
SERVE_ROOTS = ("BOOKS", "REPORTS")


# ------------------------------------------------------------------ state
def _book_summary(b):
    return {k: b.get(k) for k in ("id", "title", "subtitle", "language", "market", "status", "priority", "assigned_agent",
                                   "risk_level", "qc_status", "page_count", "updated_at", "created_at", "author",
                                   "collections", "translated_from", "brief_approved", "price_suggested", "blocked_from")} | {
        "has_cover": (books.book_dir(b["id"]) / "design" / "cover.png").exists(),
        "flags": len(b.get("flags", [])),
        "group": next((g for g, sts in states.DASHBOARD_GROUPS.items() if b["status"] in sts), "?"),
    }


def state():
    all_b = books.all_books()
    t_all = tasks.all_tasks(["READY", "RUNNING", "BLOCKED", "INBOX"])
    ev = all_events()[-60:]
    cfg = load_config()
    return {
        "now": now_iso(),
        "project": cfg["project_name"],
        "partners": cfg["partners"],
        "default_author": cfg["default_author"],
        "groups": reports._group_counts(all_b),
        "week": reports._week_stats(all_b),
        "books": [_book_summary(b) for b in sorted(all_b, key=lambda b: b["updated_at"], reverse=True)],
        "tasks": [{k: t.get(k) for k in ("task_id", "book_id", "type", "status", "priority", "assigned_agent", "retry_count", "error", "created_at", "started_at")}
                  for t in t_all],
        "agents": agents.all_agents(),
        "decisions": decisions.all_decisions("OPEN"),
        "orders": sorted(orders.all_orders(), key=lambda o: o["created_at"], reverse=True)[:100],
        "events": list(reversed(ev)),
        "sync": SYNC,
        "steps": list(states.STEPS),
        "order_kinds": orders.KINDS,
        "languages": ["en-US", "en-GB", "es-ES", "es-MX"],
    }


def book_detail(bid):
    b = books.load(bid)
    bdir = books.book_dir(bid)
    files = sorted(str(p.relative_to(bdir)).replace("\\", "/") for p in bdir.rglob("*")
                   if p.is_file() and not p.name.endswith((".tmp", "cover.html", "interior.html")))
    review = read_text(bdir / "review" / "HUMAN_REVIEW.md", default="")
    return {"book": b, "history": books.history(bid)[-40:], "files": files, "review": review,
            "open_tasks": tasks.open_tasks_for_book(bid)}


# ------------------------------------------------------------------ actions
def _sync(by, msg):
    if not gitsync.enabled():
        SYNC.update(at=now_iso(), result="desactivado", enabled=False)
        return SYNC
    r = gitsync.sync(by, msg)
    SYNC.update(at=now_iso(), result=r.get("sync"), error=r.get("error"), enabled=True)
    return SYNC


def do_action(a):
    by = (a.get("by") or "").strip()
    if not by:
        raise FactoryError("Elige quién eres (arriba a la derecha)")
    act = a.get("action")
    res = None
    if act == "new_book":
        langs = [l for l in (a.get("target_languages") or []) if l]
        b = books.create(a["topic"], a.get("language", "en-US"), agent=by, priority=a.get("priority", "NORMAL"),
                         niche=a.get("niche", ""), target_audience=a.get("audience", ""), target_languages=langs,
                         word_count_target=int(a.get("words") or 6000), notes=a.get("notes", ""))
        res = {"id": b["id"]}
    elif act == "approve":
        price = float(a["price"]) if str(a.get("price") or "").strip() else None
        res = publishing.approve(a["id"], by, a.get("notes", ""), (a.get("author") or "").strip() or None, price)
    elif act == "request_changes":
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
                write_json(tasks.task_path(t["status"], t["task_id"]), {k: v for k, v in t.items()})
        log_event("BOOK_UPDATED", book_id=a["id"], by=by, fields=[f"priority={a['priority']}"])
        res = a["priority"]
    elif act == "translate":
        b = books.load(a["id"]); lang = books.norm_lang(a["to"])
        if lang not in b["target_languages"]:
            b["target_languages"].append(lang); books.save(b)
        log_event("TRANSLATION_REQUESTED", book_id=a["id"], language=lang, by=by)
        res = orchestrator.spawn_translations(books.load(a["id"]), by) if states.STATES.index(b["status"]) >= states.STATES.index("FACT_CHECKED") \
            and b["status"] not in ("REJECTED", "BLOCKED") else f"Se creará cuando {a['id']} pase el fact-check"
    elif act == "unblock":
        res = tasks.unblock(a["task"], by, a.get("note", ""))["task_id"]
    elif act == "decide":
        res = decisions.answer(a["id"], by, a["answer"])["id"]
    elif act == "order_new":
        res = orders.create(a["text"], by, a.get("kind", "GENERAL"), a.get("target") or None, a.get("book") or None,
                            a.get("priority", "NORMAL"))["id"]
    elif act == "order_cancel":
        res = orders.update(a["id"], "CANCELLED", by, a.get("note", ""))["id"]
    elif act == "mark_published":
        res = publishing.mark_published(a["id"], by, a["platform"], a.get("url", ""))["status"]
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
    elif act == "sync":
        return {"ok": True, "result": _sync(by, "panel sync")}
    else:
        raise FactoryError(f"Acción desconocida: {act}")
    sync = _sync(by, f"panel: {act} {a.get('id') or a.get('task') or ''}".strip())
    return {"ok": True, "result": res, "sync": sync}


# ------------------------------------------------------------------ http
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False, default=str) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                html = (Path(__file__).parent / "panel.html").read_text(encoding="utf-8").replace("__PANEL_TOKEN__", TOKEN)
                return self._send(200, html, "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._send(200, state())
            if u.path.startswith("/api/book/"):
                return self._send(200, book_detail(unquote(u.path.split("/")[-1])))
            if u.path.startswith("/files/"):
                rel = unquote(u.path[len("/files/"):])
                p = (path() / rel)
                p_abs = Path(str(p)).absolute()
                if ".." in Path(rel).parts or not rel.split("/")[0] in SERVE_ROOTS or not p_abs.is_file():
                    return self._send(404, {"error": "no encontrado"})
                ctype = mimetypes.guess_type(p_abs.name)[0] or "application/octet-stream"
                if p_abs.suffix in (".md", ".json", ".txt", ".jsonl"):
                    ctype = "text/plain; charset=utf-8"
                return self._send(200, p_abs.read_bytes(), ctype)
            return self._send(404, {"error": "no encontrado"})
        except FactoryError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/action":
            return self._send(404, {"error": "no encontrado"})
        if self.headers.get("X-Panel-Token") != TOKEN:
            return self._send(403, {"error": "token inválido (recarga el panel)"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            with ACTION_LOCK:
                return self._send(200, do_action(payload))
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


def serve(port=8765, open_browser=True, sync_every=120):
    SYNC["enabled"] = gitsync.enabled()
    if SYNC["enabled"]:
        _sync("PANEL", "panel start")
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=_background_sync, args=(sync_every,), daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"Panel en {url}  (Ctrl+C para cerrar). Sincroniza con GitHub cada {sync_every}s.")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

"""Command line interface: `python factory.py <command> ...`. Run with -h for help."""
import argparse
import json
import shutil
import subprocess
import sys

from . import agents, books, build, chat, decisions, directives, gitsync, orchestrator, orders, pg_sync, publishing, qc, reports, states, tasks
from .core import FactoryError, all_events, load_config, log_event, now_iso, path, read_json, utcnow, write_json, write_text

DIRS = ["AGENTS", "BOOKS", "COLLECTIONS", "CONFIG", "DECISIONS", "LOCKS", "LOGS/events", "METRICS", "PROMPTS",
        "REPORTS/daily", "REPORTS/weekly", "RESEARCH/opportunities", "SYSTEM", "TEMPLATES/covers", "TEMPLATES/text"] + \
       [f"TASKS/{s}" for s in tasks.TASK_STATUSES]

# What each step reads and must write (paths relative to BOOKS/<id>/). Mirrors validators.py.
STEP_IO = {
    "RESEARCH": (["book.json"], ["research/research.md", "research/sources.json"]),
    "BRIEF": (["book.json", "research/research.md", "research/sources.json"], ["brief.md"]),
    "WRITE": (["book.json", "brief.md", "research/research.md"], ["manuscript/draft.md"]),
    "TRANSLATE": (["book.json", "../<translated_from>/manuscript/final.md", "../<translated_from>/brief.md"],
                  ["manuscript/draft.md", "reports/translation_notes.md"]),
    "EDIT": (["book.json", "brief.md", "manuscript/draft.md"], ["manuscript/edited.md", "reports/editing_report.md"]),
    "FACT_CHECK": (["manuscript/edited.md", "research/sources.json"], ["manuscript/final.md", "reports/factcheck_report.md", "research/sources.json"]),
    "METADATA": (["book.json", "brief.md", "research/research.md", "manuscript/final.md"], ["metadata/metadata.json"]),
    "DESIGN": (["metadata/metadata.json", "TEMPLATES/covers/*.html"], ["design/design.json", "design/cover.png (python factory.py cover <ID>)"]),
    "FORMAT": (["manuscript/final.md", "metadata/metadata.json", "design/cover.png"], ["build/*.epub", "build/*.pdf"]),
    "QC": (["todo el libro", "reports/qc_auto.json (python factory.py qc <ID>)"], ["reports/qc_report.md"]),
    "FIX": (["reports/qc_report.md", "reports/qc_auto.json"], ["reports/fix_report.md", "+ archivos corregidos"]),
}


def out(obj):
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))


def _after(agent, msg):
    if gitsync.enabled():
        r = gitsync.sync(agent, msg)
        if r.get("sync") != "OK":
            out(r)
    if pg_sync.enabled():
        _pg_drain(agent)


def _pg_drain(agent):
    """Apply actions queued from the remote (Vercel) panel, then push fresh state to it."""
    from . import panel  # lazy: panel imports cli lazily too, avoids a circular import at module load
    try:
        for row in pg_sync.pull_pending_actions():
            try:
                result = panel.do_action(row["payload"], row["partner"])
                pg_sync.mark_action_done(row["id"], result)
            except FactoryError as e:
                pg_sync.mark_action_error(row["id"], str(e))
            except Exception as e:  # noqa: BLE001
                pg_sync.mark_action_error(row["id"], f"{type(e).__name__}: {e}")
        pg_sync.push_users()
        pg_sync.push_state(panel.state(agent))
        for b in books.all_books():
            pg_sync.push_book_details(b["id"], panel.book_detail(b["id"]))
    except Exception as e:  # noqa: BLE001 - the remote bridge must never break a local CLI command
        print(f"[pg_sync] fallo: {e}")


# ------------------------------------------------------------------ commands
def cmd_init(a):
    for d in DIRS:
        path(d).mkdir(parents=True, exist_ok=True)
    cfgp = path("CONFIG", "factory.json")
    if not cfgp.exists():
        from .core import DEFAULT_CONFIG
        write_json(cfgp, DEFAULT_CONFIG)
    out("Estructura inicializada.")


def cmd_doctor(a):
    def ver(cmd):
        exe = shutil.which(cmd[0])
        if not exe:
            return None
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
        except Exception:  # noqa: BLE001
            return "presente"
    res = {
        "python": sys.version.split()[0],
        "git": ver(["git", "--version"]),
        "chrome_or_edge (PDF/portada)": build.find_chrome(),
        "pandoc (opcional)": ver(["pandoc", "--version"]),
        "epubcheck (opcional, requiere Java)": ver(["epubcheck", "--version"]),
        "java (opcional)": ver(["java", "-version"]),
        "calibre ebook-convert (opcional, MOBI/AZW3)": ver(["ebook-convert", "--version"]),
        "git_sync_enabled": gitsync.enabled(),
        "integrity_problems": orchestrator.check_integrity(),
    }
    write_json(path("CONFIG", "environment.json"), {**res, "checked_at": now_iso()})
    out(res)


def cmd_agent(a):
    if a.action == "register":
        out(agents.register(a.id, a.owner, a.provider, a.model, a.capabilities.split(",") if a.capabilities else None, a.notes or ""))
    elif a.action == "list":
        out([{k: x.get(k) for k in ("agent_id", "owner", "status", "current_task", "last_seen", "capabilities")} for x in agents.all_agents()])
    elif a.action == "heartbeat":
        out(tasks.heartbeat(a.id))


def cmd_book(a):
    a.id = a.id or a.id_opt
    if a.action == "new":
        b = books.create(a.topic, a.language, a.market, book_id=a.id, agent=a.by, priority=a.priority, niche=a.niche or "",
                         target_audience=a.audience or "", target_languages=a.target_languages.split(",") if a.target_languages else None,
                         collection=a.collection, word_count_target=a.words, notes=a.notes or "")
        if a.collection:
            _collection_add(a.collection, b["id"])
        out({"id": b["id"], "status": b["status"], "risk_level": b["risk_level"]})
        _after(a.by, f"book new {b['id']}")
    elif a.action == "show":
        b = books.load(a.id)
        b["_history"] = books.history(a.id)[-15:]
        b["_open_tasks"] = [{k: t[k] for k in ("task_id", "type", "status", "assigned_agent", "retry_count")} for t in tasks.open_tasks_for_book(a.id)]
        out(b)
    elif a.action == "list":
        for b in books.all_books():
            print(f"{b['id']:<14} {b['status']:<22} {b['language']:<6} {b['priority']:<8} {b['title'][:60]}")
    elif a.action == "set":
        b = books.load(a.id)
        allowed = {"priority", "niche", "target_audience", "word_count_target", "owner_partner", "series", "target_languages", "genre"}
        for kv in a.fields:
            k, _, v = kv.partition("=")
            if k not in allowed:
                raise FactoryError(f"Campo no editable por CLI: {k}. Editables: {sorted(allowed)}")
            if k == "word_count_target":
                v = int(v)
            elif k == "target_languages":
                v = [books.norm_lang(x) for x in v.split(",") if x]
            elif k == "priority" and v not in states.PRIORITIES:
                raise FactoryError("prioridad inválida")
            b[k] = v
        books.save(b)
        log_event("BOOK_UPDATED", book_id=a.id, by=a.by, fields=a.fields)
        out({k: b[k] for k in ("id", "priority", "target_languages", "word_count_target")})
        _after(a.by, f"book set {a.id}")


def cmd_tick(a):
    """One maintenance cycle: recover -> orchestrate -> run automatic tasks -> orchestrate -> reports."""
    if gitsync.enabled():
        gitsync.sync(a.agent, "tick-start")
    r = {"recover": orchestrator.recover(a.agent)}
    r["orchestrate"] = orchestrator.orchestrate(a.agent)
    r["auto"] = _run_auto(a.agent)
    r["orchestrate2"] = orchestrator.orchestrate(a.agent)
    r["reports"] = reports.all_reports()["groups"]
    r["ready_tasks"] = [f"{t['task_id']} {t['type']} {t['book_id']} {t['priority']}" for t in tasks.all_tasks(["READY"])]
    out(r)
    _after(a.agent, "tick")


def _run_auto(agent):
    try:
        agents.get(agent)
    except FactoryError:
        agents.ensure_system(agent)  # e.g. ORCHESTRATOR running `tick` before any registration
    done, tried = [], set()
    while True:
        # each task at most once per run: retries are spread across ticks, not burned in a loop
        t = tasks.claim_next(agent, types=["FORMAT"], include_auto=True, exclude=tried)
        if not t:
            return done
        tried.add(t["task_id"])
        try:
            info = build.build_all(t["book_id"])
            res = tasks.complete(t["task_id"], agent, note=f"{info['pages']} págs, {info['chapters']} caps, {info['words']} palabras")
        except Exception as e:  # noqa: BLE001 - any build error is a task failure, never a crash
            res = tasks.fail(t["task_id"], agent, f"{type(e).__name__}: {e}")
        done.append({"task": t["task_id"], "book": t["book_id"], **res})


def cmd_auto(a):
    out(_run_auto(a.agent))
    _after(a.agent, "auto")


def cmd_next(a):
    if gitsync.enabled():
        gitsync.sync(a.agent, "pre-claim")
    for _ in range(5):
        t = tasks.claim_next(a.agent, types=a.types.split(",") if a.types else None, book_id=a.book)
        if not t:
            out({"task": None, "message": "No hay tareas disponibles para este agente. Ejecuta 'tick' o termina la sesión."})
            return
        if gitsync.publish_claim(a.agent, t["task_id"]):
            break
        out({"warning": f"{t['task_id']} reclamada por otra máquina antes; probando otra"})
    else:
        out({"task": None, "message": "Demasiadas colisiones; reintenta más tarde"})
        return
    b = books.load(t["book_id"])
    ins, outs = STEP_IO[t["type"]]
    out({
        "task": t["task_id"], "type": t["type"], "role": t["role"], "book_id": t["book_id"],
        "book_dir": f"BOOKS/{t['book_id']}", "title": b["title"], "language": b["language"], "market": b["market"],
        "risk_level": b["risk_level"], "translated_from": b.get("translated_from"),
        "instructions": t["prompt"], "rules": ["CLAUDE.md", "SYSTEM/writing_rules.md", "SYSTEM/quality_rules.md"],
        "inputs": ins, "required_outputs": outs, "notes": t.get("notes"),
        "previous_errors": [e["error"] for e in t.get("errors", [])][-3:],
        "change_requests": [c for c in b.get("change_requests", []) if not c.get("resolved")],
        "lock_ttl_minutes": load_config()["lock_ttl_minutes"],
        "when_done": f"python factory.py complete {t['task_id']} --agent {a.agent}",
        "if_failed": f"python factory.py fail {t['task_id']} --agent {a.agent} --error \"...\"",
        "if_limit_reached": f"python factory.py release {t['task_id']} --agent {a.agent} --reason usage_limit",
    })


def cmd_complete(a):
    usage = {"tokens": a.tokens} if a.tokens else None
    r = tasks.complete(a.task, a.agent, a.note or "", usage)
    r["next"] = orchestrator.orchestrate(a.agent)
    out(r)
    _after(a.agent, f"complete {a.task}")


def cmd_fail(a):
    out(tasks.fail(a.task, a.agent, a.error, a.permanent))
    _after(a.agent, f"fail {a.task}")


def cmd_release(a):
    out(tasks.release(a.task, a.agent, a.reason))
    _after(a.agent, f"release {a.task}")


def cmd_unblock(a):
    out(tasks.unblock(a.task, a.by, a.note or ""))
    _after(a.by, f"unblock {a.task}")


def cmd_recover(a):
    out(orchestrator.recover(a.agent))
    _after(a.agent, "recover")


def cmd_orchestrate(a):
    out(orchestrator.orchestrate(a.agent))
    _after(a.agent, "orchestrate")


def cmd_cover(a):
    out(build.render_cover(a.id))


def cmd_build(a):
    out(build.build_all(a.id))


def cmd_qc(a):
    r = qc.run_auto_qc(a.id, require_build=not a.no_build)
    write_text(books.book_dir(a.id) / "reports" / "qc_auto.md", qc.qc_markdown(r))
    out({"overall": r["overall"], "counts": r["counts"],
         "problems": [c for c in r["checks"] if c["result"] != "PASS"], "report": f"BOOKS/{a.id}/reports/qc_auto.md"})


def cmd_approve(a):
    out(publishing.approve(a.id, a.by, a.notes or "", a.author, a.price))
    _after(a.by, f"approve {a.id}")


def cmd_approve_brief(a):
    publishing.approve_brief(a.id, a.by)
    out(orchestrator.orchestrate(a.by))
    _after(a.by, f"approve-brief {a.id}")


def cmd_request_changes(a):
    b = publishing.request_changes(a.id, a.by, a.notes, a.restart_at)
    out({"id": b["id"], "status": b["status"], "next": orchestrator.orchestrate(a.by)})
    _after(a.by, f"request-changes {a.id}")


def cmd_reject(a):
    out({"id": publishing.reject(a.id, a.by, a.notes or "")["id"], "status": "REJECTED"})
    _after(a.by, f"reject {a.id}")


def cmd_mark_published(a):
    out({"id": publishing.mark_published(a.id, a.by, a.platform, a.url or "")["id"], "status": "PUBLISHED"})
    _after(a.by, f"published {a.id}")


def cmd_translate(a):
    b = books.load(a.id)
    lang = books.norm_lang(a.to)
    if lang not in b["target_languages"]:
        b["target_languages"].append(lang)
        books.save(b)
    log_event("TRANSLATION_REQUESTED", book_id=a.id, language=lang, by=a.by)
    if states.STATES.index(b["status"]) >= states.STATES.index("FACT_CHECKED") and b["status"] not in ("REJECTED", "BLOCKED"):
        out(orchestrator.spawn_translations(books.load(a.id), a.by) + orchestrator.orchestrate(a.by))
    else:
        out(f"Registrado: la edición {lang} se creará cuando {a.id} pase el fact-check.")
    _after(a.by, f"translate {a.id} {lang}")


def _collection_add(cid, book_id):
    p = path("COLLECTIONS", f"{cid}.json")
    c = read_json(p, default={"id": cid, "name": cid, "type": "collection", "description": "", "books": [], "created_at": now_iso()})
    if book_id not in c["books"]:
        c["books"].append(book_id)
    write_json(p, c)
    b = books.load(book_id)
    if cid not in b["collections"]:
        b["collections"].append(cid)
        books.save(b)
    return c


def cmd_collection(a):
    if a.action == "create":
        p = path("COLLECTIONS", f"{a.id}.json")
        if p.exists():
            raise FactoryError(f"Ya existe {a.id}")
        write_json(p, {"id": a.id, "name": a.name or a.id, "type": a.type, "description": a.description or "",
                       "season": a.season, "design": {"template": None, "palette": None}, "books": [], "created_at": now_iso()})
        out(read_json(p))
    elif a.action == "add":
        out(_collection_add(a.id, a.book))
    elif a.action == "list":
        out([read_json(p) for p in sorted(path("COLLECTIONS").glob("*.json"))])
    _after(a.by, f"collection {a.action}")


def cmd_ask(a):
    out(decisions.ask(a.question, a.by, a.book, a.options.split("|") if a.options else None))
    _after(a.by, "ask")


def cmd_decide(a):
    out(decisions.answer(a.id, a.by, a.answer))
    _after(a.by, f"decide {a.id}")


def cmd_orders(a):
    if gitsync.enabled():
        gitsync.sync(a.agent or "HUMAN", "pull orders")
    lst = orders.for_agent(a.agent) if a.agent else orders.all_orders(["OPEN", "IN_PROGRESS"])
    out([{k: o[k] for k in ("id", "kind", "status", "priority", "by", "target_agent", "book_id", "text", "taken_by")} for o in lst]
        or "No hay órdenes abiertas.")


def cmd_order(a):
    if a.action == "new":
        out(orders.create(a.text, a.by, a.kind, a.target, a.book, a.priority))
    else:
        status = {"take": "IN_PROGRESS", "done": "DONE", "reject": "REJECTED", "cancel": "CANCELLED"}[a.action]
        out(orders.update(a.id, status, a.by, a.note or ""))
    _after(a.by, f"order {a.action} {a.id or ''}".strip())


def cmd_team(a):
    if a.action == "setup":
        out(agents.setup_team(a.owner, a.prefix, a.model))
        _after(a.owner, f"team setup {a.prefix}")
    else:
        out([{"agent": x["agent_id"], "rol": x.get("label") or "-", "estado": x["status"], "tarea": x.get("current_task")}
             for x in agents.all_agents() if x.get("owner") != "SYSTEM"])


def cmd_recommend(a):
    """Chief: recommend a topic to the partners (chat question with Adelante / Descartar buttons)."""
    cfg = load_config()
    auto = cfg["auto_approve_recommendations"]
    b = books.create(a.topic, a.language, agent=a.agent, priority=a.priority, niche=a.niche or "",
                     target_audience=a.audience or "", recommended=not auto, rationale=a.why, word_count_target=a.words)
    if auto:
        chat.post(a.agent, "agent", f"He añadido a producción «{a.topic}» ({a.language}). {a.why}", book_id=b["id"])
    else:
        decisions.ask(f"Te recomiendo «{a.topic}» ({a.language}). {a.why}", a.agent, b["id"], ["Adelante", "Descartar"],
                      action={"type": "approve_idea", "book_id": b["id"], "yes": "Adelante", "no": "Descartar"})
    out({"id": b["id"], "needs_approval": not auto})
    _after(a.agent, f"recommend {b['id']}")


def cmd_directives(a):
    if a.action == "add":
        out(directives.add(a.text, a.by))
    elif a.action == "remove":
        out(directives.remove(a.id, a.by))
    else:
        if gitsync.enabled():
            gitsync.sync(a.by or "HUMAN", "pull directives")
        lst = directives.active()
        out([f"[{d['id']}] {d['text']} (de {d['by']})" for d in lst] or "No hay directrices vigentes.")
        return
    _after(a.by, f"directive {a.action}")


def cmd_say(a):
    """Agent progress note shown live in the partners' chat/panel."""
    agents.get(a.agent)
    out(chat.post(a.agent, "agent", a.text, kind="progress", book_id=a.book)["id"])
    _after(a.agent, "say")


def cmd_chat(a):
    if gitsync.enabled():
        gitsync.sync(a.agent or "HUMAN", "pull chat")
    for m in chat.all_messages()[-a.last:]:
        print(f"[{m['ts'][:16].replace('T', ' ')}] {m['from']} ({m['role']}/{m['kind']}): {m['text']}")


def cmd_panel(a):
    from . import panel
    panel.serve(a.port, open_browser=not a.no_browser)


def cmd_report(a):
    out(reports.all_reports())
    out("Generados: REPORTS/DASHBOARD.md, REPORTS/dashboard.html, REPORTS/DAILY_REPORT.md, REPORTS/WEEKLY_REPORT.md, REPORTS/MEETING_PACK.md, METRICS/metrics.json")


def capacity():
    """How many new topics the chief should recommend now to keep the daily target."""
    cfg = load_config()
    all_b = books.all_books()
    today = utcnow().strftime("%Y-%m-%d")
    done_today = sum(1 for e in all_events() if e["type"] == "STATE_CHANGE" and e.get("to") == "HUMAN_REVIEW" and e["ts"].startswith(today))
    approved_ideas = sum(1 for b in all_b if b["status"] == "IDEA" and b.get("idea_approved", True))
    early = sum(1 for b in all_b if b["status"] in ("RESEARCH_PENDING", "RESEARCHING", "RESEARCH_COMPLETE", "BRIEFING",
                                                     "BRIEF_READY", "WRITING_PENDING"))
    pending = sum(1 for b in all_b if b["status"] == "IDEA" and not b.get("idea_approved", True))
    want = max(0, cfg["daily_target"] - approved_ideas - early - pending)
    return {"objetivo_diario": cfg["daily_target"], "terminados_hoy": done_today, "ideas_aprobadas_en_reserva": approved_ideas,
            "libros_empezando": early, "recomendaciones_sin_responder": pending, "recomendar_ahora": min(5, want)}


def cmd_status(a):
    g = reports._group_counts(books.all_books())
    out({"pipeline": {k: v for k, v in g.items() if v},
         "running": [f"{t['task_id']} {t['type']} {t['book_id']} by {t['assigned_agent']}" for t in tasks.all_tasks(["RUNNING"])],
         "ready": [f"{t['task_id']} {t['type']} {t['book_id']} {t['priority']}" for t in tasks.all_tasks(["READY"])],
         "blocked": [f"{t['task_id']} {t['type']} {t['book_id']}: {str(t.get('error'))[:100]}" for t in tasks.all_tasks(["BLOCKED"])],
         "human_review": [b["id"] for b in books.all_books() if b["status"] == "HUMAN_REVIEW"],
         "open_decisions": [d["id"] for d in decisions.all_decisions("OPEN")],
         "capacidad": capacity(), "directrices": [d["text"] for d in directives.active()]})


def cmd_sync(a):
    out(gitsync.sync(a.agent, a.message or "sync"))


def cmd_pg_setup(a):
    """One-time: create the remote-panel tables and push the current state, so the
    Vercel panel has data immediately instead of waiting for the next tick."""
    if not pg_sync.enabled():
        raise FactoryError("Falta DATABASE_URL (ponlo en .env o como variable de entorno)")
    import os
    import psycopg
    schema = path("web", "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()
    _pg_drain(a.agent)
    out({"ok": True, "result": "esquema creado y primer envío hecho"})


def cmd_pg_status(a):
    out({"enabled": pg_sync.enabled(),
         "pending": len(pg_sync.pull_pending_actions()) if pg_sync.enabled() else None})


# ------------------------------------------------------------------ parser
def parser():
    p = argparse.ArgumentParser(prog="factory.py", description="E-Book Factory CLI")
    sp = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        s = sp.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        return s

    add("init", cmd_init, "crear estructura y config")
    add("doctor", cmd_doctor, "comprobar herramientas e integridad")
    s = add("agent", cmd_agent, "registro de agentes")
    s.add_argument("action", choices=["register", "list", "heartbeat"])
    s.add_argument("--id"); s.add_argument("--owner", default=""); s.add_argument("--provider", default="anthropic")
    s.add_argument("--model", default=""); s.add_argument("--capabilities", help="coma: RESEARCH_AGENT,WRITER_AGENT o *"); s.add_argument("--notes")
    s = add("book", cmd_book, "crear/ver/listar/editar libros")
    s.add_argument("action", choices=["new", "show", "list", "set"])
    s.add_argument("id", nargs="?"); s.add_argument("fields", nargs="*", help="para set: campo=valor")
    s.add_argument("--topic"); s.add_argument("--language", default="en-US"); s.add_argument("--market")
    s.add_argument("--priority", default="NORMAL"); s.add_argument("--niche"); s.add_argument("--audience")
    s.add_argument("--target-languages"); s.add_argument("--collection"); s.add_argument("--words", type=int, default=6000)
    s.add_argument("--notes"); s.add_argument("--by", default="HUMAN")
    s.add_argument("--id", dest="id_opt", help="ID explícito (p.ej. EB-TEST-001); por defecto se asigna EB-NNNNNN")
    for name, fn, h in [("tick", cmd_tick, "recover+orchestrate+auto+reports"), ("auto", cmd_auto, "ejecutar tareas automáticas (FORMAT)"),
                        ("recover", cmd_recover, "RECOVER tras un cierre"), ("orchestrate", cmd_orchestrate, "crear siguientes tareas")]:
        s = add(name, fn, h); s.add_argument("--agent", default="ORCHESTRATOR")
    s = add("next", cmd_next, "reclamar la siguiente tarea"); s.add_argument("--agent", required=True)
    s.add_argument("--types", help="filtrar: WRITE,EDIT"); s.add_argument("--book")
    s = add("complete", cmd_complete, "completar tarea (valida salidas)"); s.add_argument("task"); s.add_argument("--agent", required=True)
    s.add_argument("--note"); s.add_argument("--tokens", type=int)
    s = add("fail", cmd_fail, "registrar fallo"); s.add_argument("task"); s.add_argument("--agent", required=True)
    s.add_argument("--error", required=True); s.add_argument("--permanent", action="store_true")
    s = add("release", cmd_release, "devolver tarea sin contar reintento"); s.add_argument("task"); s.add_argument("--agent", required=True)
    s.add_argument("--reason", default="released")
    s = add("unblock", cmd_unblock, "desbloquear tarea (humano)"); s.add_argument("task"); s.add_argument("--by", required=True); s.add_argument("--note")
    s = add("cover", cmd_cover, "renderizar portada"); s.add_argument("id")
    s = add("build", cmd_build, "generar EPUB+PDF"); s.add_argument("id")
    s = add("qc", cmd_qc, "QC automático independiente"); s.add_argument("id"); s.add_argument("--no-build", action="store_true")
    s = add("approve", cmd_approve, "aprobar (socio)"); s.add_argument("id"); s.add_argument("--by", required=True)
    s.add_argument("--notes"); s.add_argument("--author"); s.add_argument("--price", type=float)
    s = add("approve-brief", cmd_approve_brief, "aprobar brief de riesgo"); s.add_argument("id"); s.add_argument("--by", required=True)
    s = add("request-changes", cmd_request_changes, "pedir cambios (socio)"); s.add_argument("id"); s.add_argument("--by", required=True)
    s.add_argument("--notes", required=True); s.add_argument("--restart-at", default="EDIT", choices=list(states.STEPS))
    s = add("reject", cmd_reject, "rechazar (socio)"); s.add_argument("id"); s.add_argument("--by", required=True); s.add_argument("--notes")
    s = add("mark-published", cmd_mark_published, "registrar publicación manual"); s.add_argument("id"); s.add_argument("--by", required=True)
    s.add_argument("--platform", required=True); s.add_argument("--url")
    s = add("translate", cmd_translate, "pedir edición en otro idioma"); s.add_argument("id"); s.add_argument("--to", required=True)
    s.add_argument("--by", default="HUMAN")
    s = add("collection", cmd_collection, "colecciones/series/bundles"); s.add_argument("action", choices=["create", "add", "list"])
    s.add_argument("id", nargs="?"); s.add_argument("book", nargs="?"); s.add_argument("--name"); s.add_argument("--description")
    s.add_argument("--type", default="collection", choices=["collection", "series", "bundle"]); s.add_argument("--season"); s.add_argument("--by", default="HUMAN")
    s = add("ask", cmd_ask, "escalar una pregunta a los socios"); s.add_argument("question"); s.add_argument("--by", required=True)
    s.add_argument("--book"); s.add_argument("--options", help="opciones separadas por |")
    s = add("decide", cmd_decide, "responder decisión (socio)"); s.add_argument("id"); s.add_argument("--by", required=True); s.add_argument("--answer", required=True)
    s = add("orders", cmd_orders, "órdenes abiertas de los socios (con --agent: las que te tocan)"); s.add_argument("--agent")
    s = add("order", cmd_order, "crear/gestionar una orden"); s.add_argument("action", choices=["new", "take", "done", "reject", "cancel"])
    s.add_argument("id", nargs="?"); s.add_argument("--text"); s.add_argument("--by", required=True)
    s.add_argument("--kind", default="GENERAL", choices=orders.KINDS); s.add_argument("--target"); s.add_argument("--book")
    s.add_argument("--priority", default="NORMAL"); s.add_argument("--note")
    s = add("team", cmd_team, "equipo de agentes especialistas"); s.add_argument("action", choices=["setup", "list"])
    s.add_argument("--owner", default="SOCIO-1"); s.add_argument("--prefix", default="S1"); s.add_argument("--model", default="claude")
    s = add("recommend", cmd_recommend, "jefe: recomendar un tema a los socios"); s.add_argument("--topic", required=True)
    s.add_argument("--why", required=True, help="por qué, con evidencia (FACT/ESTIMATE/HYPOTHESIS)"); s.add_argument("--agent", required=True)
    s.add_argument("--language", default="en-US"); s.add_argument("--niche"); s.add_argument("--audience"); s.add_argument("--priority", default="NORMAL")
    s.add_argument("--words", type=int, default=6000)
    s = add("directives", cmd_directives, "directrices de los socios"); s.add_argument("action", nargs="?", default="list", choices=["list", "add", "remove"])
    s.add_argument("id", nargs="?"); s.add_argument("--text"); s.add_argument("--by", default="HUMAN")
    s = add("say", cmd_say, "agente: publicar un mensaje de progreso en el chat de los socios"); s.add_argument("text")
    s.add_argument("--agent", required=True); s.add_argument("--book")
    s = add("chat", cmd_chat, "leer los últimos mensajes del chat"); s.add_argument("--last", type=int, default=30); s.add_argument("--agent")
    s = add("panel", cmd_panel, "abrir el panel de control web (solo en este ordenador)"); s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    add("report", cmd_report, "dashboard + informes + meeting pack + métricas")
    add("status", cmd_status, "resumen rápido")
    s = add("sync", cmd_sync, "git pull --rebase + push"); s.add_argument("--agent", default="HUMAN"); s.add_argument("--message")
    s = add("pg-setup", cmd_pg_setup, "crear tablas del panel remoto (Postgres) y enviar el estado actual"); s.add_argument("--agent", default="HUMAN")
    add("pg-status", cmd_pg_status, "ver si el puente con el panel remoto está activo")
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    a = parser().parse_args(argv)
    try:
        a.fn(a)
        return 0
    except FactoryError as e:
        out({"error": str(e)})
        return 2

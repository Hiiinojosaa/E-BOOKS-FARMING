"""Command line interface: `python factory.py <command> ...`. Run with -h for help."""
import argparse
import json
import shutil
import subprocess
import sys

from . import agents, books, build, decisions, gitsync, orchestrator, publishing, qc, reports, states, tasks
from .core import FactoryError, load_config, log_event, now_iso, path, read_json, write_json, write_text

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
    done = []
    while True:
        t = tasks.claim_next(agent, types=["FORMAT"], include_auto=True)
        if not t:
            return done
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


def cmd_report(a):
    out(reports.all_reports())
    out("Generados: REPORTS/DASHBOARD.md, REPORTS/dashboard.html, REPORTS/DAILY_REPORT.md, REPORTS/WEEKLY_REPORT.md, REPORTS/MEETING_PACK.md, METRICS/metrics.json")


def cmd_status(a):
    g = reports._group_counts(books.all_books())
    out({"pipeline": {k: v for k, v in g.items() if v},
         "running": [f"{t['task_id']} {t['type']} {t['book_id']} by {t['assigned_agent']}" for t in tasks.all_tasks(["RUNNING"])],
         "ready": [f"{t['task_id']} {t['type']} {t['book_id']} {t['priority']}" for t in tasks.all_tasks(["READY"])],
         "blocked": [f"{t['task_id']} {t['type']} {t['book_id']}: {str(t.get('error'))[:100]}" for t in tasks.all_tasks(["BLOCKED"])],
         "human_review": [b["id"] for b in books.all_books() if b["status"] == "HUMAN_REVIEW"],
         "open_decisions": [d["id"] for d in decisions.all_decisions("OPEN")]})


def cmd_sync(a):
    out(gitsync.sync(a.agent, a.message or "sync"))


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
    add("report", cmd_report, "dashboard + informes + meeting pack + métricas")
    add("status", cmd_status, "resumen rápido")
    s = add("sync", cmd_sync, "git pull --rebase + push"); s.add_argument("--agent", default="HUMAN"); s.add_argument("--message")
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

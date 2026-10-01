"""ORCHESTRATOR: keeps the pipeline full and consistent. Idempotent: safe to run any time, by any agent.

It never writes book content. It only: promotes ideas (WIP limit), applies gates,
creates the next task for each book, spawns translations, and recovers crashes.
"""
from pathlib import Path

from . import agents, books, locks, publishing, states, tasks
from .core import load_config, log_event, path

ORCH = "ORCHESTRATOR"


def _active(book):
    return book["status"] not in ("IDEA", "REJECTED", "PUBLISHED", "READY_FOR_PUBLISHING", "BLOCKED", "HUMAN_REVIEW")


def orchestrate(agent=ORCH):
    cfg = load_config()
    actions = []
    if not locks.acquire("orchestrator", agent, ttl_minutes=10):
        return ["otro orquestador está activo; nada que hacer"]
    try:
        tasks.promote_inbox()
        all_b = books.all_books()
        active = sum(1 for b in all_b if _active(b))
        ideas = sorted((b for b in all_b if b["status"] == "IDEA"),
                       key=lambda b: (states.PRIORITIES[b["priority"]], b["created_at"]))
        for b in ideas:
            if cfg["auto_promote_ideas"] and active < cfg["max_active_books"]:
                books.transition(b["id"], "RESEARCH_PENDING", agent, "PROMOTE_IDEA", note=f"WIP {active + 1}/{cfg['max_active_books']}")
                active += 1
                actions.append(f"{b['id']}: IDEA -> RESEARCH_PENDING")

        for b in books.all_books():
            bid, st = b["id"], b["status"]
            if st == "BRIEF_READY":
                needs_human = cfg["brief_approval"] == "human" or b["risk_level"] == "HIGH"
                if b["brief_approved"] or not needs_human:
                    if not b["brief_approved"]:
                        b["brief_approved"], b["brief_approved_by"] = True, f"{agent} (auto: riesgo {b['risk_level']})"
                        books.save(b)
                    b = books.transition(bid, "WRITING_PENDING", agent, "BRIEF_GATE", "APPROVED", note=b["brief_approved_by"])
                    st = b["status"]
                    actions.append(f"{bid}: brief aprobado -> WRITING_PENDING")
                else:
                    continue  # waits for `approve-brief` (listed in MEETING_PACK)
            if st == "QC_PASSED":
                for c in b.get("change_requests", []):
                    c["resolved"] = True  # the requested changes went through the full pipeline again
                books.save(b)
                publishing.review_pack(bid)
                books.transition(bid, "HUMAN_REVIEW", agent, "REVIEW_PACK", "OK")
                actions.append(f"{bid}: QC_PASSED -> HUMAN_REVIEW (review/HUMAN_REVIEW.md)")
                continue
            if st == "QC_FAILED" and b.get("qc_fail_count", 0) > cfg["max_qc_failures"]:
                books.transition(bid, "BLOCKED", agent, "QC_LIMIT", "BLOCKED",
                                 note=f"QC falló {b['qc_fail_count']} veces: requiere humano")
                actions.append(f"{bid}: demasiados fallos de QC -> BLOCKED")
                continue
            if st == "APPROVED" and len(b["human_approval"]["by"]) >= cfg["approvals_required"]:
                publishing.release(bid, agent)
                actions.append(f"{bid}: paquete de publicación creado")
                continue
            if b["target_languages"] and states.STATES.index(st) >= states.STATES.index("FACT_CHECKED") \
                    and st not in ("REJECTED", "BLOCKED"):
                actions += spawn_translations(b, agent)
            step = states.step_for_state(st)
            if step and not tasks.open_tasks_for_book(bid):
                notes = ""
                pending = [c for c in b.get("change_requests", []) if not c.get("resolved")]
                if pending:
                    notes = "CAMBIOS PEDIDOS POR LOS SOCIOS: " + " | ".join(f"[{c['by']}] {c['notes']}" for c in pending)
                t = tasks.create(bid, step, priority=b["priority"], notes=notes, agent=agent)
                actions.append(f"{bid}: tarea {t['task_id']} {step}")
    finally:
        locks.release("orchestrator", agent, force=True)
    if actions:
        log_event("ORCHESTRATE", agent=agent, actions=len(actions))
    return actions


def spawn_translations(book, agent):
    """Each language edition is its own traceable book (parent_book / translated_from)."""
    out = []
    existing = {b["language"] for b in books.all_books() if b.get("translated_from") == book["id"]}
    for lang in book["target_languages"]:
        if lang == book["language"] or lang in existing:
            continue
        child = books.create(book["topic"], lang, agent=agent, priority=book["priority"], niche=book["niche"],
                             genre=book["genre"], target_audience=book["target_audience"],
                             parent_book=book.get("parent_book") or book["id"], translated_from=book["id"],
                             state="TRANSLATION_PENDING", word_count_target=book["word_count_target"])
        child["brief_chapters"] = book.get("brief_chapters")
        child["brief_approved"] = True
        child["brief_approved_by"] = f"heredado de {book['id']}"
        child["collections"] = list(book.get("collections", []))
        child["risk_level"], child["risk_reasons"] = book["risk_level"], list(book["risk_reasons"])
        child["related_books"] = [book["id"]]
        books.save(child)
        parent = books.load(book["id"])
        parent["related_books"].append(child["id"])
        books.save(parent)
        out.append(f"{book['id']}: edición {lang} creada como {child['id']}")
    return out


def recover(agent=ORCH):
    """RECOVER: run after any crash/restart. Rebuilds a consistent state from files."""
    report = {"stale_running": [], "locks_broken": [], "books_reverted": [], "tmp_removed": [], "agents_offline": []}
    # 1) RUNNING tasks whose lock expired or vanished -> retry (counts as an attempt; avoids infinite loops)
    for t in tasks.all_tasks(["RUNNING"]):
        lk = locks.read_lock(locks.book_resource(t["book_id"]))
        if lk and lk.get("agent") == t.get("assigned_agent") and not locks.is_expired(lk):
            continue
        owner = t.get("assigned_agent") or agent
        if not lk or locks.is_expired(lk):
            # give the dead owner's lock back to it momentarily so the standard fail path can run
            locks.release(locks.book_resource(t["book_id"]), owner, force=True)
            locks.acquire(locks.book_resource(t["book_id"]), owner, t["task_id"])
        try:
            res = tasks.fail(t["task_id"], owner, "interrumpida: lock expirado o agente caído (recover)")
        except Exception as e:  # noqa: BLE001 - recovery must continue
            res = {"error": str(e)}
        report["stale_running"].append({"task": t["task_id"], **res})
    # 2) expired locks
    report["locks_broken"] = locks.recover_expired()
    # 3) books stuck in a working state with no running task
    working = states.working_states()
    running_books = {t["book_id"] for t in tasks.all_tasks(["RUNNING"])}
    for b in books.all_books():
        if b["status"] in working and b["id"] not in running_books:
            step = states.STEPS[working[b["status"]]]
            last = [h for h in books.history(b["id"]) if h.get("to") == b["status"]]
            back = last[-1]["from"] if last and last[-1].get("from") in step["from"] else step["from"][0]
            books.transition(b["id"], back, agent, "RECOVER", "REVERTED", note=f"{b['status']} sin tarea activa")
            report["books_reverted"].append(b["id"])
    # 4) temp files from interrupted atomic writes
    for p in Path(path()).rglob("*.tmp"):
        if ".git" in p.parts:
            continue
        try:
            p.unlink()
            report["tmp_removed"].append(str(p.relative_to(path())))
        except OSError:
            pass
    # 5) agents not seen for a long time
    report["agents_offline"] = agents.mark_offline_stale()
    # 6) agents pointing to tasks that are no longer running
    for a in agents.all_agents():
        if a.get("current_task"):
            try:
                st, _ = tasks.find(a["current_task"])
            except Exception:  # noqa: BLE001
                st = None
            if st != "RUNNING":
                agents.update(a["agent_id"], current_task=None, status="IDLE" if a.get("status") != "OFFLINE" else "OFFLINE")
    log_event("RECOVER", agent=agent, **{k: len(v) for k, v in report.items()})
    return report


def check_integrity():
    """Consistency audit (used by tests and `doctor`). Returns list of problems."""
    problems = []
    seen = {}
    for t in tasks.all_tasks():
        if t["task_id"] in seen:
            problems.append(f"{t['task_id']} duplicada en {seen[t['task_id']]} y {t['status']}")
        seen[t["task_id"]] = t["status"]
    for b in books.all_books():
        if b["status"] not in states.STATES:
            problems.append(f"{b['id']}: estado desconocido {b['status']}")
        running = [t for t in tasks.all_tasks(["RUNNING"]) if t["book_id"] == b["id"]]
        if len(running) > 1:
            problems.append(f"{b['id']}: {len(running)} tareas RUNNING a la vez")
        if b["status"] in states.working_states() and not running:
            problems.append(f"{b['id']}: en {b['status']} sin tarea RUNNING")
        for t in running:
            lk = locks.read_lock(locks.book_resource(b["id"]))
            if not lk or lk.get("agent") != t.get("assigned_agent"):
                problems.append(f"{t['task_id']}: RUNNING sin lock del agente asignado")
    return problems

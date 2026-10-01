"""REPORTING_AGENT (scripted): metrics, dashboard (md + html), daily/weekly reports, MEETING_PACK."""
import datetime
import html
from collections import Counter, defaultdict

from . import agents, books, decisions, states, tasks
from .core import all_events, load_config, now_iso, parse_iso, path, utcnow, write_json, write_text


def _hours(a, b):
    return round((parse_iso(b) - parse_iso(a)).total_seconds() / 3600, 2)


def metrics():
    all_b = books.all_books()
    all_t = tasks.all_tasks()
    ev = all_events()
    hist = {b["id"]: books.history(b["id"]) for b in all_b}
    started, completed, per_book, review_times = 0, 0, {}, []
    for b in all_b:
        h = hist[b["id"]]
        start = next((x["ts"] for x in h if x.get("to") in ("RESEARCH_PENDING", "TRANSLATION_PENDING")), None)
        done = next((x["ts"] for x in h if x.get("to") == "READY_FOR_PUBLISHING"), None)
        if start:
            started += 1
        if done:
            completed += 1
            if start:
                per_book[b["id"]] = _hours(start, done)
        rv = None
        for x in h:
            if x.get("to") == "HUMAN_REVIEW":
                rv = x["ts"]
            elif rv and x.get("from") == "HUMAN_REVIEW":
                review_times.append(_hours(rv, x["ts"]))
                rv = None
    util = defaultdict(lambda: {"tasks_done": 0, "tasks_failed": 0, "busy_hours": 0.0})
    tokens = 0
    for t in all_t:
        for a in t.get("attempts", []):
            u = util[a["agent"]]
            if a.get("ended_at"):
                u["busy_hours"] = round(u["busy_hours"] + _hours(a["started_at"], a["ended_at"]), 3)
            if a.get("result") == "DONE":
                u["tasks_done"] += 1
            elif a.get("result") == "FAILED":
                u["tasks_failed"] += 1
            usage = a.get("usage")
            if isinstance(usage, dict):
                tokens += int(usage.get("tokens", 0) or 0)
    qc_fail = sum(1 for e in ev if e["type"] == "STATE_CHANGE" and e.get("to") == "QC_FAILED")
    val_fail = sum(1 for e in ev if e["type"] in ("TASK_FAILED", "TASK_BLOCKED") and "Validación" in str(e.get("error", "")))
    m = {
        "generated_at": now_iso(),
        "books_total": len(all_b),
        "books_started": started,
        "books_completed": completed,
        "books_failed": sum(1 for b in all_b if b["status"] in ("REJECTED", "BLOCKED")),
        "average_completion_time_hours": round(sum(per_book.values()) / len(per_book), 2) if per_book else None,
        "time_per_book_hours": per_book,
        "tasks_total": len(all_t),
        "tasks_completed": sum(1 for t in all_t if t["status"] == "DONE"),
        "tasks_failed": sum(1 for e in ev if e["type"] in ("TASK_FAILED", "TASK_BLOCKED")),
        "tasks_blocked": sum(1 for t in all_t if t["status"] == "BLOCKED"),
        "retries": sum(t.get("retry_count", 0) for t in all_t),
        "agent_utilization": dict(util),
        "human_review_time_hours_avg": round(sum(review_times) / len(review_times), 2) if review_times else None,
        "quality_failures": {"qc_failed": qc_fail, "validation_failed": val_fail},
        "cost_estimate": {"reported_tokens": tokens,
                          "note": "Suscripciones de tarifa plana: el coste marginal es 0; los tokens solo se cuentan si el agente los reporta con --tokens."},
    }
    write_json(path("METRICS", "metrics.json"), m)
    return m


def _group_counts(all_b):
    c = Counter(b["status"] for b in all_b)
    out = {"TOTAL BOOKS": len(all_b)}
    for g, sts in states.DASHBOARD_GROUPS.items():
        out[g] = sum(c[s] for s in sts)
    return out


def _week_stats(all_b, days=7):
    since = utcnow() - datetime.timedelta(days=days)
    ev = [e for e in all_events() if parse_iso(e["ts"]) >= since]
    return {
        "books_created": sum(1 for e in ev if e["type"] == "BOOK_CREATED"),
        "books_completed": sum(1 for e in ev if e["type"] == "STATE_CHANGE" and e.get("to") == "READY_FOR_PUBLISHING"),
        "books_awaiting_approval": sum(1 for b in all_b if b["status"] == "HUMAN_REVIEW"),
        "tasks_completed": sum(1 for e in ev if e["type"] == "TASK_DONE"),
        "tasks_failed": sum(1 for e in ev if e["type"] in ("TASK_FAILED", "TASK_BLOCKED")),
        "agent_activity": dict(Counter(e.get("agent") for e in ev if e["type"] == "TASK_DONE")),
    }


def dashboard():
    all_b = books.all_books()
    groups = _group_counts(all_b)
    week = _week_stats(all_b)
    ags = agents.all_agents()
    md = [f"# DASHBOARD — {load_config()['project_name']}", "", f"_Generado {now_iso()}_", "",
          "| " + " | ".join(groups) + " |", "|" + "---|" * len(groups), "| " + " | ".join(str(v) for v in groups.values()) + " |", "",
          "## Últimos 7 días", ""]
    md += [f"- {k.replace('_', ' ')}: **{v}**" for k, v in week.items()]
    md += ["", "## Libros", "", "| ID | Título | Idioma | Estado | Prioridad | Agente | Actualizado |", "|---|---|---|---|---|---|---|"]
    for b in all_b:
        md.append(f"| {b['id']} | {b['title']} | {b['language']} | {b['status']} | {b['priority']} | {b.get('assigned_agent') or '-'} | {b['updated_at']} |")
    md += ["", "## Agentes", "", "| Agente | Dueño | Estado | Tarea | Visto |", "|---|---|---|---|---|"]
    md += [f"| {a['agent_id']} | {a['owner']} | {a['status']} | {a.get('current_task') or '-'} | {a['last_seen']} |" for a in ags]
    write_text(path("REPORTS", "DASHBOARD.md"), "\n".join(md) + "\n")
    write_text(path("REPORTS", "dashboard.html"), _dashboard_html(all_b, groups, week, ags))
    return groups


def _dashboard_html(all_b, groups, week, ags):
    e = html.escape
    tiles = "".join(f'<div class="tile{" hot" if k in ("HUMAN REVIEW", "BLOCKED", "FAILED") and v else ""}"><div class="n">{v}</div><div class="l">{e(k)}</div></div>'
                    for k, v in groups.items())
    rows = "".join(f"<tr><td class=mono>{e(b['id'])}</td><td>{e(b['title'])}</td><td>{e(b['language'])}</td>"
                   f"<td><span class='st st-{e(b['status'])}'>{e(b['status'])}</span></td><td>{e(b['priority'])}</td>"
                   f"<td>{e(b.get('assigned_agent') or '–')}</td><td class=mono>{e(b['updated_at'][:16].replace('T', ' '))}</td></tr>" for b in all_b)
    arows = "".join(f"<tr><td class=mono>{e(a['agent_id'])}</td><td>{e(a['owner'])}</td><td>{e(a['status'])}</td>"
                    f"<td class=mono>{e(a.get('current_task') or '–')}</td><td class=mono>{e(a['last_seen'][:16].replace('T', ' '))}</td></tr>" for a in ags)
    wk = "".join(f"<li><b>{e(str(v))}</b> {e(k.replace('_', ' '))}</li>" for k, v in week.items())
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>E-Book Factory</title><style>
:root{{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--mut:#6b6b66;--line:#e4e4df;--acc:#2f5d50;--hot:#b4472f}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#151614;--card:#1e1f1c;--fg:#ecece7;--mut:#9a9a93;--line:#30312d;--acc:#7fb8a4;--hot:#e58a72}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 10px}}
.mut{{color:var(--mut);font-size:13px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}} .tile .n{{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}}
.tile .l{{font-size:11px;letter-spacing:.04em;color:var(--mut)}} .tile.hot .n{{color:var(--hot)}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{color:var(--mut);font-weight:500}} .mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px}}
.st{{font-size:11px;padding:2px 6px;border-radius:4px;border:1px solid var(--line)}} .st-READY_FOR_PUBLISHING,.st-PUBLISHED{{color:var(--acc);border-color:var(--acc)}}
.st-BLOCKED,.st-QC_FAILED,.st-HUMAN_REVIEW{{color:var(--hot);border-color:var(--hot)}} ul{{padding-left:18px;margin:0}}
</style></head><body><main><h1>E-Book Factory</h1><div class=mut>Generado {e(now_iso())} · regenerar con <code>python factory.py report</code></div>
<h2>Pipeline</h2><div class=grid>{tiles}</div><h2>Últimos 7 días</h2><ul>{wk}</ul>
<h2>Libros</h2><div class=wrap><table><tr><th>ID</th><th>Título</th><th>Idioma</th><th>Estado</th><th>Prioridad</th><th>Agente</th><th>Actualizado (UTC)</th></tr>{rows}</table></div>
<h2>Agentes</h2><div class=wrap><table><tr><th>Agente</th><th>Dueño</th><th>Estado</th><th>Tarea</th><th>Visto (UTC)</th></tr>{arows}</table></div>
</main></body></html>"""


def _period_report(days, title):
    since = utcnow() - datetime.timedelta(days=days)
    ev = [e for e in all_events() if parse_iso(e["ts"]) >= since]
    all_b = books.all_books()
    done = [e for e in ev if e["type"] == "TASK_DONE"]
    fails = [e for e in ev if e["type"] in ("TASK_FAILED", "TASK_BLOCKED")]
    advanced = sorted({e["book_id"] for e in ev if e["type"] == "STATE_CHANGE"})
    finished = [e["book_id"] for e in ev if e["type"] == "STATE_CHANGE" and e.get("to") == "READY_FOR_PUBLISHING"]
    blocked = [b for b in all_b if b["status"] == "BLOCKED"]
    nxt = sorted(tasks.all_tasks(["READY", "INBOX"]), key=lambda t: (states.PRIORITIES.get(t["priority"], 9), t["created_at"]))[:10]
    md = [f"# {title}", "", f"_Periodo: últimos {days} día(s) hasta {now_iso()}_", "",
          "## Trabajo realizado", ""]
    md += [f"- {e['ts'][:16]} {e.get('agent')} completó **{e.get('step')}** de {e.get('book_id')} ({e.get('task_id')})" for e in done] or ["- Nada"]
    md += ["", "## Libros avanzados", ""] + ([f"- {b}: ahora en **{books.load(b)['status']}**" for b in advanced] or ["- Ninguno"])
    md += ["", "## Libros terminados (listos para publicar)", ""] + ([f"- {b}" for b in finished] or ["- Ninguno"])
    md += ["", "## Errores", ""] + ([f"- {e['ts'][:16]} {e.get('task_id')} {e.get('book_id')}: {str(e.get('error'))[:200]}" for e in fails] or ["- Ninguno"])
    md += ["", "## Bloqueos", ""] + ([f"- {b['id']} (desde {b.get('blocked_from')})" for b in blocked] or ["- Ninguno"])
    md += ["", "## Decisiones necesarias", ""]
    md += [f"- {b['id']} {b['title']}: HUMAN_REVIEW" for b in all_b if b["status"] == "HUMAN_REVIEW"]
    md += [f"- {d['id']}: {d['question']}" for d in decisions.all_decisions("OPEN")] or []
    md += ["", "## Próximas tareas", ""] + ([f"- {t['task_id']} {t['type']} {t['book_id']} ({t['priority']})" for t in nxt] or ["- Cola vacía"])
    return "\n".join(md) + "\n"


def daily():
    day = utcnow().strftime("%Y-%m-%d")
    txt = _period_report(1, f"DAILY REPORT {day}")
    write_text(path("REPORTS", "daily", f"DAILY_REPORT_{day}.md"), txt)
    write_text(path("REPORTS", "DAILY_REPORT.md"), txt)
    return txt


def weekly():
    wk = utcnow().strftime("%G-W%V")
    txt = _period_report(7, f"WEEKLY REPORT {wk}")
    write_text(path("REPORTS", "weekly", f"WEEKLY_REPORT_{wk}.md"), txt)
    write_text(path("REPORTS", "WEEKLY_REPORT.md"), txt)
    return txt


def meeting_pack():
    """Only what the partners must decide. Goal: a short meeting, then the factory runs again."""
    cfg = load_config()
    all_b = books.all_books()
    md = [f"# MEETING PACK — {now_iso()[:10]}", "", "> Solo lo que requiere decisión de los socios.", ""]
    rev = [b for b in all_b if b["status"] == "HUMAN_REVIEW"]
    md += ["## APROBAR (listos, QC superado)", ""]
    for b in rev:
        warn = [f for f in b.get("flags", [])]
        md.append(f"- **{b['id']}** — {b['title']} ({b['language']}) · QC {b.get('qc_status')} · {b.get('page_count')} págs · "
                  f"precio sugerido {(b.get('price_suggested') or {}).get('amount')} → `BOOKS/{b['id']}/review/HUMAN_REVIEW.md`"
                  + (f" · ⚠ {len(warn)} flags" if warn else ""))
    if not rev:
        md.append("- Nada")
    md += ["", "## REVISAR (bloqueados o esperando a un humano)", ""]
    rv = [b for b in all_b if b["status"] == "BLOCKED"] + \
         [b for b in all_b if b["status"] == "BRIEF_READY" and not b["brief_approved"]]
    for b in rv:
        why = "brief de riesgo ALTO pendiente de aprobar (`approve-brief`)" if b["status"] == "BRIEF_READY" else f"BLOCKED desde {b.get('blocked_from')}"
        md.append(f"- **{b['id']}** — {b['title']}: {why}")
    for t in tasks.all_tasks(["BLOCKED"]):
        md.append(f"  - {t['task_id']} {t['type']} {t['book_id']}: {str(t.get('error'))[:160]} → `python factory.py unblock {t['task_id']} --by <SOCIO>`")
    if not rv:
        md.append("- Nada")
    md += ["", "## DESCARTAR (candidatos)", ""]
    disc = [b for b in all_b if b["status"] == "BLOCKED" and b.get("qc_fail_count", 0) > cfg["max_qc_failures"]]
    md += [f"- {b['id']} — {b['title']}: QC falló {b['qc_fail_count']} veces" for b in disc] or ["- Nada"]
    md += ["", "## DECISIONES", ""]
    dec = []
    if any(b.get("author") == cfg["default_author"] for b in all_b if b["status"] in ("HUMAN_REVIEW", "READY_FOR_PUBLISHING")):
        dec.append("¿Nombre de autor / pen name? (ahora es provisional: `" + cfg["default_author"] + "`)")
    for b in all_b:
        if b["status"] in ("HUMAN_REVIEW", "READY_FOR_PUBLISHING") and not b.get("translated_from"):
            have = {x["language"] for x in all_b if x.get("translated_from") == b["id"]} | {b["language"]}
            missing = [l for l in ("es-ES", "en-US", "en-GB") if l not in have and l not in b["target_languages"]]
            if missing:
                dec.append(f"{b['id']}: ¿crear versiones {', '.join(missing)}? (`python factory.py translate {b['id']} --to <lang>`)")
    dec += [f"{d['id']}: {d['question']} " + (f"Opciones: {', '.join(d['options'])}" if d["options"] else "") +
            f" (`python factory.py decide {d['id']} --by <SOCIO> --answer \"...\"`)" for d in decisions.all_decisions("OPEN")]
    md += [f"- {d}" for d in dec] or ["- Nada"]
    groups = _group_counts(all_b)
    md += ["", "## Estado de la fábrica", "", " · ".join(f"{k}: {v}" for k, v in groups.items() if v), ""]
    write_text(path("REPORTS", "MEETING_PACK.md"), "\n".join(md) + "\n")
    return "\n".join(md)


def all_reports():
    m = metrics()
    g = dashboard()
    daily()
    weekly()
    meeting_pack()
    return {"groups": g, "metrics": {k: m[k] for k in ("books_total", "books_completed", "tasks_completed", "tasks_failed", "retries")}}

"""Multi-agent simulation (tests 43 + 44 of the bootstrap prompt).

Runs N agent processes concurrently against a SANDBOX copy of the factory (never the real BOOKS/).
Each agent loops: tick-lite -> next -> write synthetic step output -> complete, with random delays.
Content is synthetic test text, not real books.

    python SCRIPTS/simulate_agents.py            # 2 agents, EB-TEST-002 + EB-TEST-003
    python SCRIPTS/simulate_agents.py --agents 4 --books 6
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def worker(agent, seed):
    from factory import build, core, orchestrator, tasks
    from tests import fixtures
    random.seed(seed)
    log, idle = [], 0
    while idle < 6:
        orchestrator.orchestrate(agent)
        t = tasks.claim_next(agent, include_auto=True)
        if not t:
            idle += 1
            time.sleep(0.3)
            continue
        idle = 0
        time.sleep(random.uniform(0.05, 0.4))  # "thinking"
        try:
            if t["type"] == "FORMAT":
                build.build_all(t["book_id"])
            else:
                fixtures.write_step(core.root(), t["book_id"], t["type"])
                if t["type"] == "DESIGN":
                    build.render_cover(t["book_id"])
            r = tasks.complete(t["task_id"], agent)
        except Exception as e:  # noqa: BLE001
            r = tasks.fail(t["task_id"], agent, f"{type(e).__name__}: {e}")
        log.append({"task": t["task_id"], "book": t["book_id"], "step": t["type"], "result": r["result"], "error": r.get("error"), "pid": os.getpid()})
    print(json.dumps(log))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=2)
    ap.add_argument("--books", type=int, default=2)
    ap.add_argument("--worker")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--report")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.worker:
        return worker(a.worker, a.seed)

    from factory import agents, books, core, orchestrator, tasks
    from tests import fixtures
    root = fixtures.sandbox()
    core.set_root(root)
    ids = [f"AGENT-{chr(65 + i)}" for i in range(a.agents)]
    for i, ag in enumerate(ids):
        agents.register(ag, "SOCIO-1" if i % 2 == 0 else "DANI")
    book_ids = [f"EB-TEST-{n:03d}" for n in range(2, 2 + a.books)]
    for n, bid in enumerate(book_ids):
        books.create(f"Simulation book {n}", "en-US" if n % 2 == 0 else "en-GB", book_id=bid)
    t0 = time.time()
    env = {**os.environ, "EBF_ROOT": str(root), "PYTHONIOENCODING": "utf-8"}
    procs = {ag: subprocess.Popen([sys.executable, __file__, "--worker", ag, "--seed", str(i)], env=env, cwd=REPO,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
             for i, ag in enumerate(ids)}
    logs = {}
    for ag, p in procs.items():
        out, err = p.communicate(timeout=900)
        try:
            logs[ag] = json.loads(out.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            logs[ag] = []
            print(f"{ag} stderr:\n{err[-2000:]}")
    elapsed = round(time.time() - t0, 1)

    per_book_agents = defaultdict(Counter)
    for ag, lg in logs.items():
        for e in lg:
            per_book_agents[e["book"]][ag] += 1
    done_tasks = [t for t in tasks.all_tasks(["DONE"])]
    dup = [k for k, v in Counter(t["task_id"] for t in done_tasks).items() if v > 1]
    final = {b: books.load(b)["status"] for b in book_ids}
    mixing = []
    for b in book_ids:
        txt = (root / "BOOKS" / b / "manuscript" / "final.md").read_text(encoding="utf-8")
        for other in book_ids:
            if other != b and fixtures.marker(other) in txt:
                mixing.append(f"{b} contiene texto de {other}")
    integrity = orchestrator.check_integrity()
    ok = all(s == "HUMAN_REVIEW" for s in final.values()) and not dup and not mixing and not integrity
    lines = [f"# Simulación multi-agente — {core.now_iso()}", "",
             f"- Agentes (procesos del SO independientes): {', '.join(ids)}",
             f"- Libros: {', '.join(book_ids)}", f"- Duración: {elapsed} s", f"- Sandbox: carpeta temporal (no toca BOOKS/ reales)", "",
             "## Estado final", ""] + [f"- {b}: **{s}**" for b, s in final.items()] + [
             "", "## Pasos por libro y agente", ""] + [f"- {b}: {dict(c)}" for b, c in sorted(per_book_agents.items())] + [
             "", "## Comprobaciones", "",
             f"- Tareas completadas: {len(done_tasks)} · duplicadas: {dup or 'ninguna'}",
             f"- Mezcla de contenido entre libros: {mixing or 'ninguna'}",
             f"- Integridad (1 RUNNING máx. por libro, locks coherentes, sin estados huérfanos): {integrity or 'OK'}",
             f"- Resultado: **{'PASS' if ok else 'FAIL'}**", "", "## Log de cada agente", ""]
    for ag, lg in logs.items():
        lines.append(f"### {ag}")
        lines += [f"- {e['task']} {e['step']:<10} {e['book']} → {e['result']}" + (f" ({e['error'][:160]})" if e.get("error") else "") for e in lg]
        lines.append("")
    report = "\n".join(lines)
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(report, encoding="utf-8")
    print(report)
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

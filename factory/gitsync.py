"""Multi-machine mode: the Git remote is the shared source of truth.

Rule: one clone per agent. Every mutating command is followed by `sync`.
Claims are published immediately; if two machines claim the same task, git
reports an add/add conflict on TASKS/RUNNING/<task>.json and the slower agent
backs off (its claim commit is discarded, the other agent's claim wins).
"""
import subprocess

from .core import load_config, log_event, root


def git(*args):
    return subprocess.run(["git", *args], cwd=root(), capture_output=True, text=True, encoding="utf-8")


def enabled():
    cfg = load_config()["git"]
    if not cfg.get("sync_enabled"):
        return False
    return git("remote", "get-url", cfg["remote"]).returncode == 0


def _commit(message, author=None):
    git("add", "-A")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return False
    args = ["commit", "-q", "-m", message]
    if author:
        args = ["-c", f"user.name={author}", "-c", "user.email=agents@ebook-factory.local"] + args
    r = git(*args)
    return r.returncode == 0


def pull():
    cfg = load_config()["git"]
    r = git("pull", "--rebase", "-q", cfg["remote"], cfg["branch"])
    if r.returncode != 0:
        git("rebase", "--abort")
        return False, r.stderr.strip()
    return True, ""


def push():
    cfg = load_config()["git"]
    r = git("push", "-q", cfg["remote"], f"HEAD:{cfg['branch']}")
    return r.returncode == 0, r.stderr.strip()


def sync(agent, message="sync"):
    """commit local changes -> pull --rebase -> push. Never destroys work: on conflict it stops and reports."""
    if not enabled():
        return {"sync": "disabled"}
    _commit(f"{message} [{agent}]", agent)
    ok, err = pull()
    if not ok:
        log_event("SYNC_CONFLICT", agent=agent, error=err[:300])
        return {"sync": "CONFLICT", "error": err, "hint": "Resolver a mano o pedir ayuda humana; no se ha perdido nada (commit local intacto)."}
    ok, err = push()
    return {"sync": "OK" if ok else "PUSH_FAILED", "error": err or None}


def publish_claim(agent, task_id):
    """Push the claim commit. Returns True if our claim is the one on the remote."""
    if not enabled():
        return True
    _commit(f"claim {task_id} [{agent}]", agent)
    for _ in range(3):
        ok, _ = push()
        if ok:
            return True
        ok, _ = pull()
        if not ok:
            # Somebody else claimed the same task first: drop our claim commit.
            cfg = load_config()["git"]
            git("reset", "-q", "--hard", f"{cfg['remote']}/{cfg['branch']}")
            log_event("CLAIM_LOST", agent=agent, task_id=task_id)
            return False
    return False

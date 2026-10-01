"""Bridge to the Vercel-hosted panel's Postgres database.

The factory engine (this Python codebase) stays the single source of truth for the
pipeline: state machine, locks, QC, validators. Postgres is only a MIRROR of the
current state (so the remote panel can show it) and an OUTBOX of actions the remote
panel queued (so this engine can apply them with the exact same `do_action` logic
used by the local panel).

Optional feature: everything no-ops quietly if DATABASE_URL isn't configured, so the
factory keeps working stdlib-only for anyone who hasn't set up the remote panel.
Needs `pip install "psycopg[binary]"` to actually sync.
"""
import json
import mimetypes
import os

from .core import path, read_json

_ENV_LOADED = False


def _load_dotenv():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    p = path(".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def enabled():
    _load_dotenv()
    return bool(os.environ.get("DATABASE_URL"))


def _connect():
    import psycopg  # optional dependency; only imported if actually used
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=5)


def push_state(state_dict):
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into kv_state (id, data, updated_at) values ('singleton', %s, now()) "
            "on conflict (id) do update set data = excluded.data, updated_at = now()",
            [json.dumps(state_dict, ensure_ascii=False, default=str)],
        )


def push_book_details(book_id, detail_dict):
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into book_details (book_id, data, updated_at) values (%s, %s, now()) "
            "on conflict (book_id) do update set data = excluded.data, updated_at = now()",
            [book_id, json.dumps(detail_dict, ensure_ascii=False, default=str)],
        )


def push_book_file(book_id, kind, file_path):
    """Mirror a cover/PDF/EPUB into Postgres so the Vercel panel (no access to the local disk)
    can serve it. Skips the upload if this exact file (by mtime) is already stored."""
    if not enabled():
        return
    file_path = path(file_path)
    if not file_path.exists():
        return
    mtime = file_path.stat().st_mtime
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select mtime from book_files where book_id = %s and kind = %s", [book_id, kind])
        row = cur.fetchone()
        if row and row[0] == mtime:
            return
        ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        cur.execute(
            "insert into book_files (book_id, kind, filename, content_type, mtime, data, updated_at) "
            "values (%s, %s, %s, %s, %s, %s, now()) "
            "on conflict (book_id, kind) do update set filename = excluded.filename, "
            "content_type = excluded.content_type, mtime = excluded.mtime, data = excluded.data, updated_at = now()",
            [book_id, kind, file_path.name, ctype, mtime, file_path.read_bytes()],
        )


def push_book_files(book):
    """Push whichever of cover/pdf/epub currently exist for this book. Cheap no-op when unchanged."""
    if not enabled():
        return
    bdir = path("BOOKS", book["id"])
    cover = bdir / "design" / "cover.png"
    if cover.exists():
        push_book_file(book["id"], "cover", cover)
    for kind in ("pdf", "epub"):
        rel = (book.get("files") or {}).get(kind)
        if rel:
            push_book_file(book["id"], kind, bdir / rel)


def push_users():
    if not enabled():
        return
    users = read_json(path("CONFIG", "local_users.json"), default={}) or {}
    if not users:
        return
    with _connect() as conn, conn.cursor() as cur:
        for partner, u in users.items():
            cur.execute(
                "insert into users (partner, salt, pin_hash, created_at) values (%s, %s, %s, now()) "
                "on conflict (partner) do update set salt = excluded.salt, pin_hash = excluded.pin_hash",
                [partner, u["salt"], u["pin"]],
            )


def pull_pending_actions():
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select id, partner, payload from pending_actions where status = 'pending' order by created_at")
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def mark_action_done(action_id, result):
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "update pending_actions set status = 'done', result = %s, processed_at = now() where id = %s",
            [json.dumps(result, ensure_ascii=False, default=str), action_id],
        )


def mark_action_error(action_id, error):
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "update pending_actions set status = 'error', error = %s, processed_at = now() where id = %s",
            [str(error)[:2000], action_id],
        )

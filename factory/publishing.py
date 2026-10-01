"""Human review pack, partner decisions and the immutable PUBLISHING_PACKAGE."""
import json
import shutil

from . import books, states
from .core import FactoryError, load_config, log_event, now_iso, read_json, write_json, write_text


def _meta(book):
    return read_json(books.book_dir(book["id"]) / "metadata" / "metadata.json", default={}) or {}


def review_pack(book_id):
    """review/HUMAN_REVIEW.md: everything a partner needs to decide in 2 minutes."""
    book = books.load(book_id)
    bdir = books.book_dir(book_id)
    meta = _meta(book)
    qc = read_json(bdir / "reports" / "qc_auto.json", default={}) or {}
    warn = [c for c in qc.get("checks", []) if c["result"] in ("WARN", "HUMAN_REVIEW", "FAIL")]
    price = meta.get("price") or {}
    lines = [
        f"# Revisión humana — {book_id}", "",
        f"![cover](../design/cover.png)", "",
        "| Campo | Valor |", "|---|---|",
        f"| Título | {meta.get('title', book['title'])} |",
        f"| Subtítulo | {meta.get('subtitle', '')} |",
        f"| Autor | {meta.get('author', book['author'])} |",
        f"| Idioma / Mercado | {book['language']} / {book['market']} |",
        f"| Versión | {book['version']} |",
        f"| Páginas (PDF 6x9) | {book.get('page_count')} |",
        f"| Formatos | {', '.join(book.get('formats', []))} |",
        f"| QC | **{book.get('qc_status')}** (auto: {qc.get('overall')}, {qc.get('counts')}) |",
        f"| Riesgo | {book.get('risk_level')} {book.get('risk_reasons') or ''} |",
        f"| Precio sugerido | {price.get('amount')} {price.get('currency', '')} ({price.get('basis', '')}) — {price.get('rationale', '')} |",
        f"| Colecciones | {', '.join(book.get('collections', [])) or '-'} |",
        "", "## Descripción", "", meta.get("description", ""), "",
        "## Keywords", "", "\n".join(f"- {k}" for k in meta.get("keywords", [])), "",
        "## Categorías", "", "\n".join(f"- {c}" for c in meta.get("categories", [])), "",
        "## Warnings / puntos a revisar", "",
    ]
    lines += [f"- **{c['result']}** {c['category']}/{c['check']}: {c['detail']}" for c in warn] or ["- Ninguno"]
    lines += [f"- **{f['level']}** ({f['source']}): {f['message']}" for f in book.get("flags", [])]
    lines += ["", "## Archivos", ""]
    lines += [f"- {k}: `{v}`" for k, v in book.get("files", {}).items()]
    lines += ["- Informe QC: `reports/qc_report.md`, `reports/qc_auto.md`",
              "- Informe edición: `reports/editing_report.md`; fact-check: `reports/factcheck_report.md`", "",
              "## Decisión", "", "```",
              f"python factory.py approve {book_id} --by <SOCIO> [--author \"Pen Name\"] [--notes \"...\"]",
              f"python factory.py request-changes {book_id} --by <SOCIO> --restart-at EDIT --notes \"qué cambiar\"",
              f"python factory.py reject {book_id} --by <SOCIO> --notes \"motivo\"", "```", ""]
    write_text(bdir / "review" / "HUMAN_REVIEW.md", "\n".join(lines))
    return bdir / "review" / "HUMAN_REVIEW.md"


def approve(book_id, by, notes="", author=None, price=None):
    cfg = load_config()
    book = books.load(book_id)
    if book["status"] not in ("HUMAN_REVIEW", "APPROVED"):
        raise FactoryError(f"{book_id} está en {book['status']}, no en HUMAN_REVIEW")
    if author:
        meta = _meta(book)
        meta["author"] = author
        write_json(books.book_dir(book_id) / "metadata" / "metadata.json", meta)
        book["author"] = author
    if price is not None:
        meta = _meta(book)
        meta["price"] = {**meta.get("price", {}), "amount": price, "basis": "FACT", "rationale": f"fijado por {by}"}
        write_json(books.book_dir(book_id) / "metadata" / "metadata.json", meta)
        book["price_suggested"] = meta["price"]
    ha = book["human_approval"]
    if by not in ha["by"]:
        ha["by"].append(by)
    ha.update(decision="APPROVE", at=now_iso(), notes=(ha.get("notes", "") + f"\n[{by}] {notes}").strip())
    books.save(book)
    books.transition(book_id, "APPROVED", by, "HUMAN_APPROVE", "OK", note=notes)
    log_event("HUMAN_DECISION", book_id=book_id, by=by, decision="APPROVE", notes=notes)
    if len(ha["by"]) >= cfg["approvals_required"]:
        if author or price is not None:
            # Metadata changed after the build: rebuild so files match what was approved.
            from .build import build_all
            build_all(book_id)
        return release(book_id, by)
    return {"book": book_id, "approvals": ha["by"], "needed": cfg["approvals_required"]}


def request_changes(book_id, by, notes, restart_at="EDIT"):
    if restart_at not in states.STEPS:
        raise FactoryError(f"restart-at debe ser un paso: {list(states.STEPS)}")
    book = books.load(book_id)
    if book["status"] not in ("HUMAN_REVIEW", "BRIEF_READY"):
        raise FactoryError(f"{book_id} está en {book['status']}")
    book["change_requests"].append({"at": now_iso(), "by": by, "notes": notes, "restart_at": restart_at, "resolved": False})
    book["human_approval"].update(decision="REQUEST_CHANGES", at=now_iso())
    book["qc_fail_count"] = 0
    if restart_at in ("RESEARCH", "BRIEF", "WRITE"):
        book["brief_approved"] = False if restart_at != "WRITE" else book["brief_approved"]
    books.save(book)
    books.transition(book_id, "CHANGES_REQUIRED", by, "HUMAN_REQUEST_CHANGES", "OK", note=notes)
    books.transition(book_id, states.STEPS[restart_at]["from"][0], by, f"RESTART_AT {restart_at}", "OK", note=notes)
    log_event("HUMAN_DECISION", book_id=book_id, by=by, decision="REQUEST_CHANGES", notes=notes, restart_at=restart_at)
    return books.load(book_id)


def reject(book_id, by, notes=""):
    book = books.load(book_id)
    book["human_approval"].update(decision="REJECT", at=now_iso(), notes=notes)
    books.save(book)
    books.transition(book_id, "REJECTED", by, "HUMAN_REJECT", "OK", note=notes)
    log_event("HUMAN_DECISION", book_id=book_id, by=by, decision="REJECT", notes=notes)
    return books.load(book_id)


def approve_brief(book_id, by):
    book = books.load(book_id)
    if book["status"] != "BRIEF_READY":
        raise FactoryError(f"{book_id} está en {book['status']}, no en BRIEF_READY")
    book["brief_approved"], book["brief_approved_by"] = True, by
    books.save(book)
    log_event("BRIEF_APPROVED", book_id=book_id, by=by)
    return book


CHECKLIST = """# Checklist de publicación manual — {id} v{version}

> La fábrica NO publica automáticamente. Un socio sube estos archivos a mano.

- [ ] Revisar `description.md`, `keywords.txt`, `categories.txt` y `metadata.json`
- [ ] Confirmar nombre de autor / pen name: **{author}**
- [ ] Confirmar precio: **{price}**
- [ ] Ebook: subir `{epub}` (el marketplace lo convertirá) y `cover.jpg`/`cover.png`
- [ ] Revisar la previsualización del marketplace (índice, portada, saltos de capítulo)
- [ ] Marcar contenido generado con IA si el marketplace lo pide (KDP lo pregunta en el formulario)
- [ ] Derechos territoriales, DRM, royalties: decisión de los socios
- [ ] Tras publicar: `python factory.py mark-published {id} --by <SOCIO> --platform KDP --url <URL>`
"""


def release(book_id, by):
    """Snapshot approved files into releases/v<version>/PUBLISHING_PACKAGE (never overwritten)."""
    book = books.load(book_id)
    bdir = books.book_dir(book_id)
    meta = _meta(book)
    rdir = bdir / "releases" / f"v{book['version']}"
    if rdir.exists():
        raise FactoryError(f"{rdir.name} ya existe: una versión final nunca se sobrescribe. Sube la versión.")
    pkg = rdir / "PUBLISHING_PACKAGE"
    pkg.mkdir(parents=True)
    copied = []
    for key in ("epub", "pdf", "cover", "cover_jpg"):
        rel = book["files"].get(key)
        if rel and (bdir / rel).exists():
            shutil.copy2(bdir / rel, pkg / (bdir / rel).name)
            copied.append((bdir / rel).name)
    write_json(pkg / "metadata.json", {**meta, "book_id": book_id, "version": book["version"], "language": book["language"],
                                       "market": book["market"], "approved_by": book["human_approval"]["by"], "released_at": now_iso()})
    (pkg / "description.md").write_text(meta.get("description", "") + "\n", encoding="utf-8")
    (pkg / "keywords.txt").write_text("\n".join(meta.get("keywords", [])) + "\n", encoding="utf-8")
    (pkg / "categories.txt").write_text("\n".join(meta.get("categories", [])) + "\n", encoding="utf-8")
    price = meta.get("price", {})
    (pkg / "price.json").write_text(json.dumps(price, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(bdir / "manuscript" / "final.md", rdir / "manuscript.md")
    write_text(pkg / "CHECKLIST.md", CHECKLIST.format(id=book_id, version=book["version"], author=meta.get("author"),
                                                     price=f"{price.get('amount')} {price.get('currency', '')}",
                                                     epub=book["files"].get("epub", "").split("/")[-1]))
    book = books.load(book_id)
    book["files"]["publishing_package"] = f"releases/v{book['version']}/PUBLISHING_PACKAGE"
    books.save(book)
    books.transition(book_id, "READY_FOR_PUBLISHING", by, "RELEASE_PACKAGE", "OK", note=", ".join(copied))
    log_event("PACKAGE_READY", book_id=book_id, version=book["version"], files=copied)
    return {"book": book_id, "package": book["files"]["publishing_package"], "files": copied}


def mark_published(book_id, by, platform, url=""):
    book = books.load(book_id)
    book["published"].append({"platform": platform, "url": url, "by": by, "at": now_iso(), "version": book["version"]})
    book["publication_status"] = "PUBLISHED"
    books.save(book)
    books.transition(book_id, "PUBLISHED", by, "MARK_PUBLISHED", "OK", note=f"{platform} {url}")
    return books.load(book_id)

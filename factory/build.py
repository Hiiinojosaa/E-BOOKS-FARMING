"""FORMAT/DESIGN tooling: markdown -> XHTML, EPUB3 writer + validator, PDF and cover via headless Chrome."""
import html
import os
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import books
from .core import FactoryError, load_config, now_iso, path, read_json, read_text, slugify, utcnow, word_count, write_text

# ------------------------------------------------------------------ markdown
_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
]


def inline(text):
    out = html.escape(text, quote=False)
    for rx, rep in _INLINE:
        out = rx.sub(rep, out)
    return out


_IMG_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")


def md_to_xhtml(md, heading_offset=0, img_resolver=None):
    """Small, strict markdown subset -> well-formed XHTML fragment.

    A line that is only `![alt](path)` becomes its own image block. `path` is resolved
    book-dir-relative; `img_resolver(path)` (if given) maps it to whatever `src` the
    output format needs (a flat EPUB-internal name, or a PDF-relative path) and may have
    side effects (e.g. registering the file to embed). Without a resolver, `path` is used as-is.
    """
    lines = md.replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(s.strip() for s in para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush(); i += 1; continue
        m = _IMG_LINE.match(s)
        if m:
            flush()
            alt, src = m.group(1), m.group(2)
            out.append(f'<div class="pgimg"><img src="{html.escape(img_resolver(src) if img_resolver else src)}" '
                       f'alt="{html.escape(alt)}"/></div>')
            i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flush()
            lvl = min(6, len(m.group(1)) + heading_offset)
            out.append(f"<h{lvl}>{inline(m.group(2).strip())}</h{lvl}>")
            i += 1; continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush(); out.append('<hr class="break"/>'); i += 1; continue
        if s.startswith(">"):
            flush(); q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip()); i += 1
            out.append("<blockquote><p>" + inline(" ".join(q)) + "</p></blockquote>")
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            flush()
            ordered = bool(re.match(r"^\d+[.)]\s+", s))
            items = []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                item = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", lines[i]).strip()
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                    item += " " + lines[i].strip(); i += 1
                cb = re.match(r"^\[( |x|X)\]\s+(.*)$", item)
                if cb:
                    item = ("☑ " if cb.group(1).lower() == "x" else "☐ ") + cb.group(2)
                items.append("<li>" + inline(item) + "</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        para.append(ln); i += 1
    flush()
    return "\n".join(out)


def split_chapters(md):
    """Return [(title, body_md)] splitting on level-1 headings. Text before the first H1 is ignored."""
    chapters, cur, body = [], None, []
    for ln in md.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^#\s+(.+)$", ln)
        if m:
            if cur is not None:
                chapters.append((cur, "\n".join(body).strip()))
            cur, body = m.group(1).strip(), []
        elif cur is not None:
            body.append(ln)
    if cur is not None:
        chapters.append((cur, "\n".join(body).strip()))
    return chapters


# ------------------------------------------------------------------ helpers
def find_chrome():
    cfg = load_config().get("chrome_path") or os.environ.get("CHROME_PATH")
    cands = [cfg] if cfg else []
    cands += [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    for c in cands:
        if c and Path(c).exists():
            return c
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        w = shutil.which(name)
        if w:
            return w
    return None


def _chrome(args, timeout=120):
    exe = find_chrome()
    if not exe:
        raise FactoryError("Chrome/Edge no encontrado: necesario para PDF y portada (configura chrome_path)")
    with tempfile.TemporaryDirectory(prefix="ebf-chrome-") as prof:
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", f"--user-data-dir={prof}"] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r


def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise FactoryError(f"No es PNG: {p}")
    return struct.unpack(">II", head[16:24])


def jpeg_size(p):
    data = Path(p).read_bytes()
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1; continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    raise FactoryError(f"JPEG sin cabecera SOF: {p}")


def pdf_page_count(p):
    data = Path(p).read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def _ctx(book):
    cfg = load_config()
    meta = read_json(books.book_dir(book["id"]) / "metadata" / "metadata.json", default={}) or {}
    return {
        "title": meta.get("title") or book["title"],
        "subtitle": meta.get("subtitle") or book.get("subtitle", ""),
        "author": meta.get("author") or book.get("author") or cfg["default_author"],
        "publisher": cfg.get("publisher") or "",
        "year": str(utcnow().year),
        "version": book["version"],
        "language": book["language"],
        "description": meta.get("description", ""),
    }


def _fill(template, ctx):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(str(ctx.get(m.group(1), ""))), template)


def manuscript_path(book):
    d = books.book_dir(book["id"]) / "manuscript"
    for name in ("final.md", "edited.md", "draft.md"):
        if (d / name).exists():
            return d / name
    raise FactoryError(f"{book['id']}: no hay manuscrito")


def _front_text(book, ctx, name):
    lang = book["language"][:2]
    p = path("TEMPLATES", "text", f"{name}.{lang}.md")
    if not p.exists():
        p = path("TEMPLATES", "text", f"{name}.en.md")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx.get(m.group(1), "")), read_text(p)) if p.exists() else ""


# ------------------------------------------------------------------ cover
def render_cover(book_id):
    """design/design.json + TEMPLATES/covers/<template>.html -> design/cover.png (+ cover.jpg if supported)."""
    book = books.load(book_id)
    bdir = books.book_dir(book_id)
    design = read_json(bdir / "design" / "design.json")
    tpl = path("TEMPLATES", "covers", f"{design.get('template', 'minimal')}.html")
    if not tpl.exists():
        raise FactoryError(f"Plantilla de portada no existe: {tpl.name}")
    cfg = load_config()
    w, h = cfg["cover_size_px"]["width"], cfg["cover_size_px"]["height"]
    ctx = _ctx(book)
    ctx.update({k: v for k, v in design.get("palette", {}).items()})
    ctx.update({k: design[k] for k in ("tagline", "title_line1", "title_line2", "badge") if k in design})
    ctx.setdefault("title_line1", ctx["title"])
    ctx.setdefault("title_line2", "")
    ctx["width"], ctx["height"] = w, h
    page = _fill(read_text(tpl), ctx)
    html_out = bdir / "design" / "cover.html"
    write_text(html_out, page)
    png = bdir / "design" / "cover.png"
    if png.exists():
        png.unlink()
    r = _chrome([f"--screenshot={os.path.abspath(png)}", f"--window-size={w},{h}", "--hide-scrollbars",
                 "--force-device-scale-factor=1", Path(os.path.abspath(html_out)).as_uri()])
    if not png.exists():
        raise FactoryError(f"Chrome no generó la portada: {r.stderr[-400:]}")
    size = png_size(png)
    jpg = bdir / "design" / "cover.jpg"
    if jpg.exists():
        jpg.unlink()
    _chrome([f"--screenshot={os.path.abspath(jpg)}", f"--window-size={w},{h}", "--hide-scrollbars",
             "--force-device-scale-factor=1", Path(os.path.abspath(html_out)).as_uri()])
    jpg_ok = False
    if jpg.exists():
        try:
            jpg_ok = Path(jpg).read_bytes()[:2] == b"\xff\xd8"
        except OSError:
            pass
        if not jpg_ok:
            jpg.unlink()
    return {"png": str(png), "size": size, "jpg": str(jpg) if jpg_ok else None}


# ------------------------------------------------------------------ epub
CSS = """
body { font-family: Georgia, "Times New Roman", serif; line-height: 1.5; margin: 0 5%; }
h1 { font-size: 1.6em; margin: 2.5em 0 1em; text-align: left; page-break-before: always; }
h2 { font-size: 1.25em; margin: 1.6em 0 .6em; }
h3 { font-size: 1.05em; margin: 1.2em 0 .4em; }
p { margin: 0 0 .8em; text-align: left; }
blockquote { margin: 1em 1.5em; font-style: italic; }
ul, ol { margin: 0 0 1em 1.2em; padding: 0; }
li { margin: .25em 0; }
hr.break { border: 0; text-align: center; margin: 1.5em 0; }
hr.break:after { content: "* * *"; }
.titlepage { text-align: center; margin-top: 25%; }
.titlepage h1 { page-break-before: avoid; text-align: center; font-size: 2em; }
.titlepage .subtitle { font-size: 1.15em; font-style: italic; margin: 1em 0 3em; }
.titlepage p { text-align: center; }
.titlepage .author { font-size: 1.1em; letter-spacing: .05em; }
.copyright { font-size: .8em; margin-top: 30%; }
.cover { margin: 0; padding: 0; text-align: center; }
.cover img { max-width: 100%; height: auto; }
.pgimg { text-align: center; margin: 1em 0; page-break-inside: avoid; }
.pgimg img { max-width: 100%; height: auto; }
nav ol { list-style: none; margin-left: 0; }
"""

XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">
<head><meta charset="UTF-8"/><title>{title}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body{cls}>
{body}
</body>
</html>
"""


def _xhtml(lang, title, body, cls=""):
    return XHTML.format(lang=lang, title=html.escape(title), body=body, cls=f' class="{cls}"' if cls else "")


_IMG_MEDIA_TYPE = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}


def build_epub(book, out_path):
    ctx = _ctx(book)
    bdir = books.book_dir(book["id"])
    lang = book["language"]
    chapters = split_chapters(read_text(manuscript_path(book)))
    if not chapters:
        raise FactoryError("El manuscrito no tiene capítulos (# Título)")
    cover = bdir / "design" / "cover.png"
    files = {}  # name -> (content, media_type, props)
    files["style.css"] = (CSS, "text/css", None)
    img_seen = {}  # book-relative src -> flat epub filename already registered

    def img_resolver(src):
        if src in img_seen:
            return img_seen[src]
        p = bdir / src
        ext = p.suffix.lower()
        if ext not in _IMG_MEDIA_TYPE or not p.exists():
            raise FactoryError(f"imagen no encontrada o tipo no soportado: {src}")
        flat = f"img-{len(img_seen) + 1:03d}{ext}"
        files[flat] = (p.read_bytes(), _IMG_MEDIA_TYPE[ext], None)
        img_seen[src] = flat
        return flat

    spine = []
    if cover.exists():
        files["cover.xhtml"] = (_xhtml(lang, "Cover", '<div class="cover"><img src="cover.png" alt="Cover"/></div>', "cover"),
                                "application/xhtml+xml", None)
        spine.append("cover.xhtml")
    tp = f'<div class="titlepage"><h1>{inline(ctx["title"])}</h1>'
    if ctx["subtitle"]:
        tp += f'<p class="subtitle">{inline(ctx["subtitle"])}</p>'
    tp += f'<p class="author">{inline(ctx["author"])}</p></div>'
    files["title.xhtml"] = (_xhtml(lang, ctx["title"], tp), "application/xhtml+xml", None)
    spine.append("title.xhtml")
    copy_md = _front_text(book, ctx, "copyright")
    if book.get("risk_level") == "HIGH":
        copy_md += "\n\n" + _front_text(book, ctx, "disclaimer")
    files["copyright.xhtml"] = (_xhtml(lang, "Copyright", f'<div class="copyright">{md_to_xhtml(copy_md, 1)}</div>'),
                                "application/xhtml+xml", None)
    spine.append("copyright.xhtml")
    toc_label = "Contenido" if lang.startswith("es") else "Contents"
    nav_items = []
    for n, (title, body) in enumerate(chapters, 1):
        name = f"chapter-{n:02d}.xhtml"
        content = f'<section epub:type="chapter" id="ch{n:02d}"><h1>{inline(title)}</h1>\n{md_to_xhtml(body, 1, img_resolver)}</section>'
        files[name] = (_xhtml(lang, title, content), "application/xhtml+xml", None)
        spine.append(name)
        nav_items.append(f'<li><a href="{name}#ch{n:02d}">{inline(title)}</a></li>')
    nav = (f'<nav epub:type="toc" id="toc"><h1>{toc_label}</h1><ol>' + "".join(nav_items) + "</ol></nav>"
           '<nav epub:type="landmarks" hidden=""><ol>'
           + (f'<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>' if cover.exists() else "")
           + f'<li><a epub:type="toc" href="nav.xhtml">{toc_label}</a></li>'
           f'<li><a epub:type="bodymatter" href="chapter-01.xhtml">Start</a></li></ol></nav>')
    files["nav.xhtml"] = (_xhtml(lang, toc_label, nav), "application/xhtml+xml", "nav")
    spine.insert(spine.index("copyright.xhtml") + 1, "nav.xhtml")
    ident = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"ebook-factory/{book['id']}/{book['version']}"))
    modified = now_iso()
    manifest, ids = [], {}
    for i, (name, (_, mt, props)) in enumerate(files.items()):
        ids[name] = f"i{i}"
        manifest.append(f'<item id="i{i}" href="{name}" media-type="{mt}"' + (f' properties="{props}"' if props else "") + "/>")
    if cover.exists():
        manifest.append('<item id="cover-img" href="cover.png" media-type="image/png" properties="cover-image"/>')
    kw = "".join(f"<dc:subject>{html.escape(k)}</dc:subject>" for k in book.get("keywords", []))
    desc = f"<dc:description>{html.escape(ctx['description'])}</dc:description>" if ctx["description"] else ""
    pub = f"<dc:publisher>{html.escape(ctx['publisher'])}</dc:publisher>" if ctx["publisher"] else ""
    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{ident}</dc:identifier>
<dc:title>{html.escape(ctx['title'])}</dc:title>
<dc:creator>{html.escape(ctx['author'])}</dc:creator>
<dc:language>{lang}</dc:language>{pub}{desc}{kw}
<meta property="dcterms:modified">{modified}</meta>
{'<meta name="cover" content="cover-img"/>' if cover.exists() else ''}
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine>
{chr(10).join(f'<itemref idref="{ids[n]}"/>' for n in spine)}
</spine>
</package>
"""
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        for name, (content, _, _) in files.items():
            z.writestr("OEBPS/" + name, content, compress_type=zipfile.ZIP_DEFLATED)
        if cover.exists():
            z.write(cover, "OEBPS/cover.png", compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, out_path)
    return {"chapters": len(chapters), "words": sum(word_count(b) for _, b in chapters)}


NS = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/",
      "c": "urn:oasis:names:tc:opendocument:xmlns:container", "x": "http://www.w3.org/1999/xhtml"}


def validate_epub(epub_path):
    """Structural EPUB3 check (epubcheck-lite). Returns (errors, warnings, info)."""
    errors, warnings, info = [], [], {}
    try:
        z = zipfile.ZipFile(epub_path)
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        return [f"EPUB ilegible: {e}"], [], {}
    with z:
        infos = z.infolist()
        names = set(z.namelist())
        if not infos or infos[0].filename != "mimetype":
            errors.append("mimetype no es la primera entrada")
        elif infos[0].compress_type != zipfile.ZIP_STORED or z.read("mimetype") != b"application/epub+zip":
            errors.append("mimetype comprimido o con contenido incorrecto")
        try:
            cont = ET.fromstring(z.read("META-INF/container.xml"))
            opf_path = cont.find(".//c:rootfile", NS).get("full-path")
            opf = ET.fromstring(z.read(opf_path))
        except Exception as e:  # noqa: BLE001 - any parse failure is a validation error
            return errors + [f"container/OPF inválido: {e}"], warnings, info
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        md = opf.find("opf:metadata", NS)
        for tag in ("identifier", "title", "language", "creator"):
            el = md.find(f"dc:{tag}", NS)
            if el is None or not (el.text or "").strip():
                (errors if tag != "creator" else warnings).append(f"metadato dc:{tag} vacío")
            else:
                info[tag] = el.text.strip()
        if md.find("opf:meta[@property='dcterms:modified']", NS) is None:
            errors.append("falta dcterms:modified")
        items = {i.get("id"): i for i in opf.find("opf:manifest", NS)}
        for it in items.values():
            if base + it.get("href") not in names:
                errors.append(f"manifest apunta a archivo inexistente: {it.get('href')}")
        if not any("nav" in (i.get("properties") or "") for i in items.values()):
            errors.append("falta documento nav")
        if not any("cover-image" in (i.get("properties") or "") for i in items.values()):
            warnings.append("sin imagen de portada")
        spine = [r.get("idref") for r in opf.find("opf:spine", NS)]
        for idref in spine:
            if idref not in items:
                errors.append(f"spine idref desconocido: {idref}")
        info["spine_items"] = len(spine)
        ids_by_file = {}
        docs = [base + i.get("href") for i in items.values() if i.get("media-type") == "application/xhtml+xml"]
        parsed = {}
        for d in docs:
            if d not in names:
                continue
            try:
                parsed[d] = ET.fromstring(z.read(d))
                ids_by_file[d] = {e.get("id") for e in parsed[d].iter() if e.get("id")}
            except ET.ParseError as e:
                errors.append(f"XHTML mal formado {d}: {e}")
        links = 0
        for d, root_el in parsed.items():
            ddir = d.rsplit("/", 1)[0] + "/"
            for el in root_el.iter():
                for attr in ("href", "src"):
                    ref = el.get(attr)
                    if not ref or re.match(r"^[a-z]+:", ref):
                        continue
                    links += 1
                    target, _, frag = ref.partition("#")
                    tpath = ddir + target if target else d
                    if tpath not in names:
                        errors.append(f"enlace roto en {d}: {ref}")
                    elif frag and tpath in ids_by_file and frag not in ids_by_file[tpath]:
                        errors.append(f"ancla rota en {d}: {ref}")
        info["internal_links"] = links
        info["documents"] = len(parsed)
    return errors, warnings, info


# ------------------------------------------------------------------ pdf
PRINT_CSS = """
@page {{ size: {w}in {h}in; margin: 0.75in 0.6in 0.8in 0.75in;
  @bottom-center {{ content: counter(page); font-family: Georgia, serif; font-size: 9pt; color: #555; }} }}
@page :first {{ @bottom-center {{ content: none; }} }}
@page front {{ @bottom-center {{ content: none; }} }}
html {{ font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.45; color: #111; }}
.front {{ page: front; }}
h1 {{ font-size: 19pt; margin: 0.9in 0 0.35in; break-before: page; line-height: 1.2; }}
h2 {{ font-size: 13pt; margin: 1.3em 0 .5em; break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 1.1em 0 .4em; break-after: avoid; }}
p {{ margin: 0 0 .65em; text-align: justify; hyphens: auto; orphans: 2; widows: 2; }}
ul, ol {{ margin: 0 0 .8em 1.2em; padding: 0; }}
blockquote {{ margin: .8em 1.2em; font-style: italic; }}
hr.break {{ border: 0; text-align: center; margin: 1.2em 0; }} hr.break:after {{ content: "* * *"; }}
.titlepage {{ text-align: center; padding-top: 2in; break-after: page; }}
.titlepage h1 {{ break-before: avoid; margin: 0; font-size: 24pt; }}
.titlepage .subtitle {{ font-style: italic; font-size: 13pt; margin: .3in 0 1.2in; }}
.titlepage p {{ text-align: center; hyphens: manual; }}
.copyright {{ font-size: 8.5pt; padding-top: 4in; break-after: page; }}
.copyright h2, .copyright h3 {{ font-size: 9pt; }}
.toc {{ break-after: page; }} .toc h1 {{ break-before: avoid; margin-top: .3in; }}
.toc ol {{ list-style: none; margin: 0; padding: 0; }} .toc li {{ margin: .35em 0; }}
.toc a {{ color: #111; text-decoration: none; }}
a {{ color: #111; }}
.pgimg {{ text-align: center; margin: .8em 0; break-inside: avoid; }}
.pgimg img {{ max-width: 100%; height: auto; }}
"""


def build_print_html(book):
    cfg = load_config()
    ctx = _ctx(book)
    chapters = split_chapters(read_text(manuscript_path(book)))
    lang = book["language"]
    css = PRINT_CSS.format(w=cfg["trim_size"]["width_in"], h=cfg["trim_size"]["height_in"])
    parts = [f'<div class="front titlepage"><h1>{inline(ctx["title"])}</h1>'
             + (f'<p class="subtitle">{inline(ctx["subtitle"])}</p>' if ctx["subtitle"] else "")
             + f'<p class="author">{inline(ctx["author"])}</p></div>']
    copy_md = _front_text(book, ctx, "copyright")
    if book.get("risk_level") == "HIGH":
        copy_md += "\n\n" + _front_text(book, ctx, "disclaimer")
    parts.append(f'<div class="front copyright">{md_to_xhtml(copy_md, 1)}</div>')
    toc_label = "Contenido" if lang.startswith("es") else "Contents"
    parts.append(f'<div class="front toc"><h1>{toc_label}</h1><ol>'
                 + "".join(f'<li><a href="#ch{n:02d}">{inline(t)}</a></li>' for n, (t, _) in enumerate(chapters, 1))
                 + "</ol></div>")
    for n, (t, body) in enumerate(chapters, 1):
        parts.append(f'<section id="ch{n:02d}"><h1>{inline(t)}</h1>{md_to_xhtml(body, 1)}</section>')
    return (f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(ctx["title"])}</title>'
            f"<style>{css}</style></head><body>" + "\n".join(parts) + "</body></html>")


def build_pdf(book, out_path):
    bdir = books.book_dir(book["id"])
    src = bdir / "build" / "interior.html"
    write_text(src, build_print_html(book))
    out_path = Path(out_path)
    if out_path.exists():
        out_path.unlink()
    r = _chrome(["--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={os.path.abspath(out_path)}",
                 Path(os.path.abspath(src)).as_uri()], timeout=180)
    if not out_path.exists():
        raise FactoryError(f"Chrome no generó el PDF: {r.stderr[-400:]}")
    return {"pages": pdf_page_count(out_path)}


# ------------------------------------------------------------------ format step
def build_all(book_id):
    """FORMAT step (automatic): EPUB + PDF into build/, validated."""
    book = books.load(book_id)
    bdir = books.book_dir(book_id)
    stem = f"{book_id}_{slugify(_ctx(book)['title'], 40)}_v{book['version']}"
    for old in (bdir / "build").glob("*"):
        if old.suffix in (".epub", ".pdf"):
            old.unlink()
    epub = bdir / "build" / f"{stem}.epub"
    pdf = bdir / "build" / f"{stem}.pdf"
    einfo = build_epub(book, epub)
    errors, warnings, vinfo = validate_epub(epub)
    if errors:
        raise FactoryError("EPUB inválido: " + "; ".join(errors[:10]))
    pinfo = build_pdf(book, pdf)
    book = books.load(book_id)
    book["formats"] = ["EPUB", "PDF"]
    book["page_count"] = pinfo["pages"]
    book["files"].update({"epub": f"build/{epub.name}", "pdf": f"build/{pdf.name}"})
    books.save(book)
    return {"epub": str(epub), "pdf": str(pdf), "pages": pinfo["pages"], "chapters": einfo["chapters"],
            "words": einfo["words"], "epub_warnings": warnings, "epub_info": vinfo}

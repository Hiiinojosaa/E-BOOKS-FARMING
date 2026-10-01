"""Regenera web/panel-src.html a partir de factory/panel.html (la fuente real del panel).

factory/panel.html es el único sitio donde se edita la interfaz. Esta copia existe solo porque
el panel de Vercel no puede mantener una conexión larga (SSE), así que aquí se cambia
EventSource por un polling simple; todo lo demás debe quedar idéntico.

Uso: python SCRIPTS/sync_web_panel.py   (ejecútalo cada vez que edites factory/panel.html)
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "factory" / "panel.html"
DST = ROOT / "web" / "panel-src.html"

html = SRC.read_text(encoding="utf-8")

html = html.replace(
    "ME=null; S=null; if(window._es) window._es.close(); showLogin();",
    "ME=null; S=null; if(window._poll) clearInterval(window._poll); showLogin();",
)

pattern = re.compile(
    r'function connectLive\(\)\{\s*'
    r'if\(window\._es\) window\._es\.close\(\);\s*'
    r'const es=new EventSource\("/api/stream"\); window\._es=es;\s*'
    r'es\.onopen=.*?;\s*'
    r'es\.onmessage=.*?;\s*'
    r'es\.onerror=.*?;\s*'
    r'\}',
    re.DOTALL,
)
replacement = (
    "function connectLive(){\n"
    "  if(window._poll) clearInterval(window._poll);\n"
    '  $("#liveDot").classList.add("on"); $("#liveTxt").textContent="En directo";\n'
    "  window._poll=setInterval(()=>{ if(ME) load(true); }, 4000);\n"
    "}"
)
html, n = pattern.subn(replacement, html)
if n != 1:
    raise SystemExit(f"ERROR: se esperaba sustituir connectLive() una vez, se sustituyó {n}. "
                      "Revisa manualmente factory/panel.html antes de seguir.")

DST.write_text(html, encoding="utf-8")
print(f"OK: {DST} regenerado desde {SRC}")

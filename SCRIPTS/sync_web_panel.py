"""Regenera web/panel-src.html a partir de factory/panel.html (la fuente real del panel).

factory/panel.html es el único sitio donde se edita la interfaz. Esta copia existe solo porque
el panel de Vercel no puede mantener una conexión larga (SSE), así que aquí se cambia
EventSource por un polling simple; todo lo demás debe quedar idéntico.

Uso: python SCRIPTS/sync_web_panel.py   (ejecútalo cada vez que edites factory/panel.html)
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "factory" / "panel.html"
DST = ROOT / "web" / "panel-src.html"

html = SRC.read_text(encoding="utf-8")

LOGOUT_OLD = 'ME=null; S=null; if(window._es) window._es.close(); showLogin();'
LOGOUT_NEW = 'ME=null; S=null; if(window._poll) clearInterval(window._poll); showLogin();'

CONNECT_OLD = (
    "function connectLive(){\n"
    "  if(window._es) window._es.close();\n"
    '  const es=new EventSource("/api/stream"); window._es=es;\n'
    '  es.onopen=()=>{ $("#liveDot").classList.add("on"); $("#liveTxt").textContent="En directo"; };\n'
    "  es.onmessage=()=>load(true);\n"
    '  es.onerror=()=>{ $("#liveDot").classList.remove("on"); $("#liveTxt").textContent="Reconectando"; };\n'
    "}"
)
CONNECT_NEW = (
    "function connectLive(){\n"
    "  if(window._poll) clearInterval(window._poll);\n"
    '  $("#liveDot").classList.add("on"); $("#liveTxt").textContent="En directo";\n'
    "  window._poll=setInterval(()=>{ if(ME) load(true); }, 4000);\n"
    "}"
)

for old, new, label in [(LOGOUT_OLD, LOGOUT_NEW, "logout"), (CONNECT_OLD, CONNECT_NEW, "connectLive")]:
    n = html.count(old)
    if n != 1:
        raise SystemExit(f"ERROR: se esperaba encontrar el bloque '{label}' exactamente una vez en "
                          f"factory/panel.html, se encontró {n}. Revisa el archivo a mano antes de seguir "
                          f"(puede que su código haya cambiado y este script necesite actualizarse).")
    html = html.replace(old, new)

DST.write_text(html, encoding="utf-8")
print(f"OK: {DST} regenerado desde {SRC}")

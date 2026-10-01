"""Real photo/illustration generation (Gemini image-generation models), stdlib-only (urllib).

Optional feature, like pg_sync: everything raises a clear FactoryError if no API key is
configured, so the rest of the factory keeps working without it. Needs GEMINI_API_KEY in
.env or the environment (never commit it — see CLAUDE.md regla 9).

Used by the WRITE step of any book that needs real photos/illustrations embedded (recipe
step photos, fitness pose illustrations, etc.) — generate the file, then reference it from
the manuscript with the same `![alt](design/photos/xxx.png)` markdown convention puzzle
books use (see build.md_to_xhtml's img_resolver, which embeds it into EPUB/PDF either way).

Image generation lives on Gemini's unified `generateContent` endpoint (not a separate Imagen
:predict endpoint): the model returns an inline base64 image part alongside any text part.
"""
import base64
import json
import os
import urllib.error
import urllib.request

from .core import FactoryError, path

DEFAULT_MODEL = "gemini-3-pro-image"  # highest quality; set GEMINI_IMAGE_MODEL to override (e.g. a faster/cheaper -flash variant)
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
    return bool(os.environ.get("GEMINI_API_KEY"))


def generate_image(prompt, out_path, aspect_ratio="1:1"):
    """One real, original image from a text prompt. Never for photorealistic depictions of a
    real, identifiable person; keep prompts to original scenes/subjects described in the brief."""
    if not enabled():
        raise FactoryError("Falta GEMINI_API_KEY (ponlo en .env) para generar imágenes")
    model = os.environ.get("GEMINI_IMAGE_MODEL", DEFAULT_MODEL)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect_ratio}},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.environ['GEMINI_API_KEY']}",
        data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        if e.code == 429:
            raise FactoryError(f"Gemini sin cuota para '{model}' (probablemente falta facturación activada "
                               f"en el proyecto de Google AI Studio de esta clave): {detail}")
        raise FactoryError(f"Gemini error {e.code} (modelo '{model}'): {detail}")
    except urllib.error.URLError as e:
        raise FactoryError(f"no se pudo contactar con Gemini: {e}")
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise FactoryError(f"respuesta inesperada de Gemini: {str(data)[:400]}")
    img = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not img:
        raise FactoryError(f"Gemini no devolvió una imagen (puede haber bloqueado el prompt): {str(data)[:400]}")
    out_path = path(out_path)  # joinpath with an absolute path is a no-op, so this handles both
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(img["data"]))
    return str(out_path)

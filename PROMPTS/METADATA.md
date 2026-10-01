# METADATA — MARKET_AGENT (+ METADATA_AGENT)

**Objetivo:** posicionar el libro para que lo encuentre y lo compre la audiencia correcta, sin prometer lo que no contiene.

**Entradas:** `book.json`, `brief.md`, `research/research.md`, `manuscript/final.md`.
**Salida:** `metadata/metadata.json`:

```json
{
  "title": "…",                      // corto, claro, beneficio; sin marcas registradas ajenas
  "subtitle": "…",                   // concreta la promesa y la audiencia
  "description": "…",                // 300–4000 caracteres; párrafo gancho, qué aprenderás (lista), para quién es; texto plano
  "keywords": ["…"],                 // 1–7 frases de búsqueda (≤50 caracteres), sin repetir palabras del título si es posible
  "categories": ["…"],               // 1–3 rutas de categoría plausibles del marketplace (los socios las confirman)
  "price": {"amount": 2.99, "currency": "USD", "basis": "ESTIMATE", "rationale": "…"},
  "target_audience": "…",
  "positioning": "…",                // 1–2 frases: por qué este libro y no otro
  "claims": [{"text": "…", "type": "FACT|ESTIMATE|HYPOTHESIS", "source": "S1"}]   // afirmaciones de mercado usadas
}
```

Reglas: diferenciar FACT / ESTIMATE / HYPOTHESIS en cualquier afirmación de demanda o precio. No inventar rankings ni
volúmenes de búsqueda. La descripción no puede contener afirmaciones que el libro no cumpla ni reseñas o testimonios falsos.
El sistema copia título, subtítulo, keywords, categorías y descripción a `book.json` al completar.

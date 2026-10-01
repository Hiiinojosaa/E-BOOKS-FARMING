# OPPORTUNITIES — MARKET_AGENT (detectar ideas)

Uso: cuando la cola está vacía y los socios lo han pedido (no generar ideas sin límite).

1. Investiga nichos con evidencia (búsqueda web): demanda visible, competencia mejorable, temas perennes o estacionales (colecciones).
2. Escribe `RESEARCH/opportunities/<YYYY-MM-DD>_<slug>.md` con: nicho, audiencia, evidencia (FACT/ESTIMATE/HYPOTHESIS + fuentes), ángulo, riesgo, idiomas sugeridos.
3. Registra como máximo **3 ideas por sesión**:
   `python factory.py book new --topic "…" --language en-US --niche "…" --audience "…" --priority LOW --by <TU-ID> --notes "RESEARCH/opportunities/…"`
4. Las ideas quedan en IDEA. El orquestador las promueve respetando `max_active_books`. Los socios pueden cambiar prioridad o rechazarlas.

No registrar temas de alto riesgo (salud, finanzas, legal) sin `ask` previo a los socios.

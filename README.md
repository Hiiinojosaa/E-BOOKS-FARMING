# E-Book Factory

Fábrica de e-books de **SOCIO-1** y **DANI**, operada por agentes Claude. Produce libros hasta un paquete listo para
publicar; **la publicación la hacéis vosotros a mano**.

- Manual de los agentes: [`CLAUDE.md`](CLAUDE.md) · Arquitectura: [`SYSTEM/architecture.md`](SYSTEM/architecture.md)
- Estado de la fábrica: [`REPORTS/DASHBOARD.md`](REPORTS/DASHBOARD.md) y `REPORTS/dashboard.html`
- Lo que tenéis que decidir: [`REPORTS/MEETING_PACK.md`](REPORTS/MEETING_PACK.md)
- Informe de arranque: [`FACTORY_BOOTSTRAP_REPORT.md`](FACTORY_BOOTSTRAP_REPORT.md)

## Requisitos
Python 3.10+ (sin paquetes extra), Git, Google Chrome o Microsoft Edge (para PDF y portadas). Nada más.

## Panel de control (lo más fácil)

Doble clic en **`ABRIR_PANEL.bat`** (o `python factory.py panel`). Se abre en el navegador, solo en tu ordenador
(http://127.0.0.1:8765), y se sincroniza con GitHub cada 2 minutos, así que ves lo mismo que Dani.

- **Inicio:** qué hay en la cadena y qué necesita vuestra atención.
- **Libros:** portadas, estado, ficha de cada libro; aprobar, pedir cambios, rechazar, prioridad, otras ediciones; nueva idea.
- **Órdenes a los agentes:** escribís lo que queréis en lenguaje normal; el siguiente agente que arranque lo lee, lo hace y responde ahí.
- **Decisiones:** preguntas que os hacen los agentes.
- **Agentes:** quién está trabajando, en qué, y cómo arrancar uno (a mano o con horario).
- **Actividad:** todo lo que ha pasado.

El panel no lanza agentes: les deja órdenes. Un agente es una sesión de Claude abierta en la carpeta del proyecto
(a mano o programada con horario).

## Uso diario por terminal (socios)

```bash
python factory.py status                 # resumen rápido
python factory.py report                 # regenera dashboard, informes y MEETING_PACK
python factory.py book new --topic "Tema" --language en-US --niche "…" --audience "…" --priority HIGH --by SOCIO-1
python factory.py approve EB-000003 --by SOCIO-1 --author "Pen Name" --price 3.99
python factory.py request-changes EB-000003 --by DANI --restart-at EDIT --notes "Capítulo 2 demasiado largo"
python factory.py reject EB-000004 --by SOCIO-1 --notes "nicho saturado"
python factory.py approve-brief EB-000005 --by DANI      # briefs de riesgo ALTO
python factory.py decide DEC-00001 --by SOCIO-1 --answer "Sí, crear colección"
python factory.py unblock TASK-000042 --by DANI --note "arreglado"
python factory.py translate EB-000003 --to es            # edición en otro idioma (libro propio)
python factory.py collection create CHRISTMAS-2026 --type collection --season 2026-12
python factory.py mark-published EB-000003 --by SOCIO-1 --platform KDP --url https://…
```

Reunión cada 2–3 días: `python factory.py report`, abrir `REPORTS/MEETING_PACK.md`, decidir, y la fábrica sigue.

## Poner a trabajar a un agente

En Claude Code, dentro de esta carpeta: *"Trabaja como agente S1-CLAUDE-001 siguiendo PROMPTS/WORKER.md"*.
Sin supervisión: `powershell -File SCRIPTS\run_worker.ps1 -AgentId S1-CLAUDE-001` (programable).

## Tests
```bash
python -m unittest discover -s tests -t .
python SCRIPTS/simulate_agents.py --agents 4 --books 6
```

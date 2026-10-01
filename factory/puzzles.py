"""Puzzle-book generation: Sudoku and Word Search, independently re-verifiable.

Used for book["kind"] in ("PUZZLE_SUDOKU", "PUZZLE_WORDSEARCH"). The WRITE step for a
puzzle-kind book calls `generate_book()` instead of an agent writing prose: it produces

  manuscript/draft.md      -- real intro + how-to-solve text, flows through EDIT/FACT_CHECK/QC
  manuscript/puzzles.json  -- raw grid/solution/placement data, re-verified (never just trusted)
  design/puzzles/*.png     -- one rendered page per puzzle and per solution

Rendering reuses the same headless-Chrome screenshot mechanism as covers (see build.render_cover),
so no extra dependency is needed beyond what FORMAT already requires.
"""
import html
import random

from . import books, build
from .core import FactoryError, now_iso, read_json, word_count, write_json, write_text

KINDS = ("PUZZLE_SUDOKU", "PUZZLE_WORDSEARCH")

# ---------------------------------------------------------------------- sudoku: solve/generate
def _empty():
    return [[0] * 9 for _ in range(9)]


def _candidates(grid, r, c):
    used = set(grid[r]) | {grid[i][c] for i in range(9)}
    br, bc = 3 * (r // 3), 3 * (c // 3)
    used |= {grid[br + i][bc + j] for i in range(3) for j in range(3)}
    return [v for v in range(1, 10) if v not in used]


def _find_empty(grid):
    best, best_n = None, 10
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                n = len(_candidates(grid, r, c))
                if n == 0:
                    return (r, c), 0  # dead end: report immediately
                if n < best_n:
                    best, best_n = (r, c), n
                    if n == 1:
                        return best, best_n
    return best, best_n


def count_solutions(grid, limit=2):
    """Backtracking counter, stops as soon as `limit` solutions are found (fast uniqueness check)."""
    grid = [row[:] for row in grid]

    def rec():
        pos, n = _find_empty(grid)
        if pos is None:
            return 1
        if n == 0:
            return 0
        r, c = pos
        found = 0
        for v in _candidates(grid, r, c):
            grid[r][c] = v
            found += rec()
            grid[r][c] = 0
            if found >= limit:
                return found
        return found

    return rec()


def generate_solution(rng):
    """A complete, randomly-shuffled valid 9x9 Sudoku solution via backtracking."""
    grid = _empty()

    def rec():
        pos, n = _find_empty(grid)
        if pos is None:
            return True
        if n == 0:
            return False
        r, c = pos
        cands = _candidates(grid, r, c)
        rng.shuffle(cands)
        for v in cands:
            grid[r][c] = v
            if rec():
                return True
            grid[r][c] = 0
        return False

    if not rec():
        raise FactoryError("no se pudo generar una solución de sudoku (no debería pasar)")
    return grid


DIFFICULTY_CLUES = {"EASY": (42, 46), "MEDIUM": (32, 36), "HARD": (24, 28)}


def dig_holes(solution, rng, difficulty):
    lo, hi = DIFFICULTY_CLUES[difficulty]
    target = rng.randint(lo, hi)
    grid = [row[:] for row in solution]
    cells = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(cells)
    clues = 81
    for r, c in cells:
        if clues <= target:
            break
        saved = grid[r][c]
        grid[r][c] = 0
        if count_solutions(grid, limit=2) == 1:
            clues -= 1
        else:
            grid[r][c] = saved
    return grid, clues


def make_sudoku(difficulty, rng):
    solution = generate_solution(rng)
    puzzle, clues = dig_holes(solution, rng, difficulty)
    return {"type": "SUDOKU", "difficulty": difficulty, "puzzle": puzzle, "solution": solution, "clues": clues}


def verify_sudoku(entry):
    """Independent re-check: never trust stored puzzle data (CLAUDE.md regla 3)."""
    puzzle, solution = entry["puzzle"], entry["solution"]
    for r in range(9):
        for c in range(9):
            if puzzle[r][c] and puzzle[r][c] != solution[r][c]:
                return False, "una pista no coincide con la solución"
    if count_solutions([row[:] for row in solution]) != 1:
        return False, "la solución guardada no es válida"
    if count_solutions([row[:] for row in puzzle], limit=2) != 1:
        return False, "el puzzle no tiene solución única"
    return True, ""


# ---------------------------------------------------------------------- word search: generate
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1), (-1, 1)]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_wordsearch(words, rng, size=15, allow_backwards=True):
    words = [w.upper().replace(" ", "") for w in words if w.strip()]
    words.sort(key=len, reverse=True)  # longest first: fits more reliably
    grid = [["" for _ in range(size)] for _ in range(size)]
    placements = []
    dirs = DIRECTIONS if allow_backwards else [d for d in DIRECTIONS if d[0] >= 0 and (d[0], d[1]) != (0, -1)]
    for w in words:
        placed = False
        attempts = list(range(size * size * len(dirs)))
        rng.shuffle(attempts)
        for a in attempts:
            d = dirs[a % len(dirs)]
            r0 = rng.randint(0, size - 1)
            c0 = rng.randint(0, size - 1)
            r1 = r0 + d[0] * (len(w) - 1)
            c1 = c0 + d[1] * (len(w) - 1)
            if not (0 <= r1 < size and 0 <= c1 < size):
                continue
            cells = [(r0 + d[0] * i, c0 + d[1] * i) for i in range(len(w))]
            if all(grid[r][c] in ("", w[i]) for i, (r, c) in enumerate(cells)):
                for i, (r, c) in enumerate(cells):
                    grid[r][c] = w[i]
                placements.append({"word": w, "row": r0, "col": c0, "dr": d[0], "dc": d[1]})
                placed = True
                break
        if not placed:
            continue  # word didn't fit after many tries: book still works with the rest
    for r in range(size):
        for c in range(size):
            if grid[r][c] == "":
                grid[r][c] = rng.choice(LETTERS)
    return {"type": "WORDSEARCH", "size": size, "grid": grid, "placements": placements,
            "words": [p["word"] for p in placements]}


def verify_wordsearch(entry):
    grid, size = entry["grid"], entry["size"]
    for p in entry["placements"]:
        w, r, c, dr, dc = p["word"], p["row"], p["col"], p["dr"], p["dc"]
        got = "".join(grid[r + dr * i][c + dc * i] for i in range(len(w)))
        if got != w:
            return False, f"'{w}' no está realmente en la rejilla donde dice la clave de soluciones"
    return True, ""


# ---------------------------------------------------------------------- rendering (headless Chrome, like covers)
def _render_png(svg, out_path, width, height):
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f"html,body{{margin:0;padding:0;background:#fff}}</style></head>"
            f"<body>{svg}</body></html>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_html = out_path.with_suffix(".tmp.html")
    write_text(tmp_html, page)
    if out_path.exists():
        out_path.unlink()
    r = build._chrome([f"--screenshot={out_path.resolve()}", f"--window-size={width},{height}",
                        "--hide-scrollbars", "--force-device-scale-factor=1", tmp_html.resolve().as_uri()])
    tmp_html.unlink(missing_ok=True)
    if not out_path.exists():
        raise FactoryError(f"Chrome no generó la imagen del puzzle: {r.stderr[-400:]}")


def img_height(size, title):
    return size + (60 if title else 0)


def sudoku_svg(grid, size=900, given_mask=None, title=""):
    cell = size / 9
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size + (60 if title else 0)}" '
             f'width="{size}" height="{size + (60 if title else 0)}">']
    off = 60 if title else 0
    if title:
        parts.append(f'<text x="{size/2}" y="38" font-family="Georgia,serif" font-size="28" '
                      f'text-anchor="middle" fill="#111">{html.escape(title)}</text>')
    parts.append(f'<rect x="0" y="{off}" width="{size}" height="{size}" fill="#fff" stroke="#111" stroke-width="3"/>')
    for i in range(1, 9):
        w = 3 if i % 3 == 0 else 1
        x = i * cell
        parts.append(f'<line x1="{x}" y1="{off}" x2="{x}" y2="{off+size}" stroke="#111" stroke-width="{w}"/>')
        y = off + i * cell
        parts.append(f'<line x1="0" y1="{y}" x2="{size}" y2="{y}" stroke="#111" stroke-width="{w}"/>')
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if not v:
                continue
            given = given_mask[r][c] if given_mask else True
            weight = "700" if given else "400"
            color = "#111" if given else "#39507a"
            x, y = c * cell + cell / 2, off + r * cell + cell / 2 + cell * 0.12
            parts.append(f'<text x="{x}" y="{y}" font-family="Georgia,serif" font-size="{cell*0.6}" '
                         f'font-weight="{weight}" fill="{color}" text-anchor="middle">{v}</text>')
    parts.append("</svg>")
    return "".join(parts)


def wordsearch_svg(entry, size=900, title="", show_solution=False):
    grid, n = entry["grid"], entry["size"]
    cell = size / n
    off = 60 if title else 0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size + off}" '
             f'width="{size}" height="{size + off}">']
    if title:
        parts.append(f'<text x="{size/2}" y="38" font-family="Georgia,serif" font-size="24" '
                     f'text-anchor="middle" fill="#111">{html.escape(title)}</text>')
    parts.append(f'<rect x="0" y="{off}" width="{size}" height="{size}" fill="#fff" stroke="#111" stroke-width="2"/>')
    if show_solution:
        for p in entry["placements"]:
            x1 = p["col"] * cell + cell / 2
            y1 = off + p["row"] * cell + cell / 2
            x2 = (p["col"] + p["dc"] * (len(p["word"]) - 1)) * cell + cell / 2
            y2 = off + (p["row"] + p["dr"] * (len(p["word"]) - 1)) * cell + cell / 2
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#e0a030" '
                         f'stroke-width="{cell*0.5}" stroke-linecap="round" opacity="0.55"/>')
    for r in range(n):
        for c in range(n):
            x, y = c * cell + cell / 2, off + r * cell + cell / 2 + cell * 0.14
            parts.append(f'<text x="{x}" y="{y}" font-family="Courier New,monospace" font-size="{cell*0.55}" '
                         f'fill="#111" text-anchor="middle">{grid[r][c]}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------- book assembly
SUDOKU_INTRO = """# Introduction

{count} sudoku puzzles, sorted from easy to hard, each with exactly one solution and verified
before going to print. No guessing required: every puzzle in this book can be solved through
logic alone.

Puzzles are grouped by difficulty so you can warm up on the easy grids before moving on to the
medium and hard ones. Every solution is in the back of the book, in the same order as the
puzzles, so you can check your work or get unstuck without spoiling the next page.

# How to Solve

Each grid is nine rows and nine columns, divided into nine 3x3 boxes. Fill every empty cell with
a digit from 1 to 9 so that each row, each column, and each 3x3 box contains every digit exactly
once. A finished puzzle never repeats a digit in the same row, column, or box.

Start with the rows, columns, or boxes that already have the most numbers filled in: they leave
the fewest open cells, so the correct digit is often forced. For any empty cell, look at its row,
its column, and its box together; if only one digit from 1 to 9 is missing from all three, that
digit belongs there.

When no cell is immediately forced, pick a digit and scan the whole grid for the one box, row, or
column where it can only go in a single remaining cell, even if that cell isn't obvious at first
glance. Working digit by digit like this, rather than cell by cell, often breaks a puzzle open
faster than staring at one stubborn square.

If you get stuck, it's rarely because a puzzle has no logical path forward: it usually means a
digit was placed too early based on a guess. Double-check your filled-in numbers against their
row, column, and box before assuming the puzzle is unsolvable, and the stuck point almost always
resolves itself.
"""

WORDSEARCH_INTRO = """# Introduction

{count} word search puzzles with a clear theme in every grid, a word list to match, and a full
solution key in the back. Words can run in any of eight directions: forward or backward,
horizontally, vertically, or diagonally, so the hunt stays genuinely challenging even on the
easier puzzles.

# How to Solve

Read the word list before you start scanning: knowing what you're looking for, and how long each
word is, narrows the search far more than scanning letter by letter. Start with the longest words
on the list first; they're easier to spot and rule out the most ground on the grid at once.

Scan systematically rather than randomly: run your eyes along each row, then each column, then
each diagonal, rather than jumping around the grid. Most solvers miss words that run backward or
diagonally simply because they only scanned left-to-right and top-to-bottom; once you've checked
the obvious directions, go back over the grid specifically looking for the less common angles.

When a word seems to be hiding, look for its first letter anywhere it appears in the grid, then
check in every direction from that letter for the second letter of the word. A letter that starts
several different words on your list is worth checking carefully, since the grid often places
tricky overlaps exactly there.
"""

DIFFICULTY_LABEL = {"EASY": "Easy", "MEDIUM": "Medium", "HARD": "Hard"}


def generate_book(book_id, agent, seed=None):
    """WRITE step for a puzzle-kind book: generates puzzles, renders pages, writes the manuscript."""
    b = books.load(book_id)
    kind = b.get("kind")
    if kind not in KINDS:
        raise FactoryError(f"{book_id}: kind '{kind}' no es un libro de puzzles")
    rng = random.Random(seed if seed is not None else f"{book_id}-{b.get('version',1)}")
    bdir = books.book_dir(book_id)
    pdir = bdir / "design" / "puzzles"
    count = int(b.get("puzzle_count") or 100)
    tiers = ["EASY"] * (count // 3) + ["MEDIUM"] * (count // 3)
    tiers += ["HARD"] * (count - len(tiers))

    entries = []
    if kind == "PUZZLE_SUDOKU":
        for difficulty in tiers:
            entries.append(make_sudoku(difficulty, rng))
    else:
        words = b.get("word_list") or []
        if len(words) < 15:
            raise FactoryError(f"{book_id}: word_list tiene {len(words)} palabras, hacen falta al menos 15")
        for _ in range(count):
            entries.append(make_wordsearch(rng.sample(words, k=min(15, len(words))), rng))

    full = SUDOKU_INTRO.format(count=count) if kind == "PUZZLE_SUDOKU" else WORDSEARCH_INTRO.format(count=count)
    by_tier = {}
    for i, entry in enumerate(entries, 1):
        tier = entry.get("difficulty", "ALL")
        by_tier.setdefault(tier, []).append((i, entry))

    for tier, items in by_tier.items():
        label = DIFFICULTY_LABEL.get(tier, "Puzzles")
        lines = []
        for i, entry in items:
            if kind == "PUZZLE_SUDOKU":
                svg = sudoku_svg(entry["puzzle"], given_mask=[[bool(v) for v in row] for row in entry["puzzle"]],
                                  title=f"Puzzle {i} · {label}")
            else:
                svg = wordsearch_svg(entry, title=f"Puzzle {i} · Find: " + ", ".join(entry["words"][:3]) + "…")
            png = pdir / f"puzzle-{i:03d}.png"
            _render_png(svg, png, 900, img_height(900, True))
            lines.append(f"![Puzzle {i}](design/puzzles/puzzle-{i:03d}.png)")
            if kind == "PUZZLE_WORDSEARCH":
                lines.append(f"\nWords: " + ", ".join(entry["words"]) + "\n")
        full += f"\n\n# {label} Puzzles\n\n" + "\n\n".join(lines)

    sol_lines = []
    for i, entry in enumerate(entries, 1):
        if kind == "PUZZLE_SUDOKU":
            svg = sudoku_svg(entry["solution"], title=f"Solution {i}")
        else:
            svg = wordsearch_svg(entry, title=f"Solution {i}", show_solution=True)
        png = pdir / f"solution-{i:03d}.png"
        _render_png(svg, png, 900, img_height(900, True))
        sol_lines.append(f"![Solution {i}](design/puzzles/solution-{i:03d}.png)")
    full += "\n\n# Solutions\n\n" + "\n\n".join(sol_lines)

    manuscript_dir = bdir / "manuscript"
    write_text(manuscript_dir / "draft.md", full)
    write_json(manuscript_dir / "puzzles.json", {"kind": kind, "count": count, "generated_at": now_iso(),
                                                  "seed": str(seed), "entries": entries})
    # word_count_target / brief_chapters come from the brief, same contract as any other book: the
    # brief for a puzzle book should state ~N words (intro + how-to-solve only) and 6 chapters
    # (Introduction, How to Solve, Easy/Medium/Hard Puzzles, Solutions) — see SYSTEM/puzzle_books.md.
    return {"puzzles": count, "images": count * 2, "word_count": word_count(full)}


def verify_book_puzzles(book_id):
    """Independent re-check used by validators.py: never trust the stored puzzles.json blindly."""
    b = books.load(book_id)
    data = read_json(books.book_dir(book_id) / "manuscript" / "puzzles.json", default=None)
    if not data:
        return ["falta manuscript/puzzles.json"]
    errors = []
    verify = verify_sudoku if data["kind"] == "PUZZLE_SUDOKU" else verify_wordsearch
    for i, entry in enumerate(data["entries"], 1):
        ok, why = verify(entry)
        if not ok:
            errors.append(f"puzzle #{i}: {why}")
    if len(data["entries"]) != b.get("puzzle_count"):
        errors.append(f"{len(data['entries'])} puzzles generados, se esperaban {b.get('puzzle_count')}")
    return errors

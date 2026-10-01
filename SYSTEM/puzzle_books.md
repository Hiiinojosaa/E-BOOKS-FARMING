# Libros de puzzles (Sudoku / Sopa de letras)

Mismo pipeline que cualquier libro (RESEARCH → BRIEF → WRITE → EDIT → FACT_CHECK → METADATA →
DESIGN → FORMAT → QC → HUMAN_REVIEW → …). Lo único que cambia es el paso WRITE: en vez de un
agente escribiendo prosa, se ejecuta el generador (`factory/puzzles.py`), que crea los puzzles,
los verifica de forma independiente (nunca se confía en los datos guardados) y los renderiza a
PNG vía Chrome headless (el mismo mecanismo que `build.render_cover`).

## Crear uno

```
python factory.py book new --topic "..." --kind PUZZLE_SUDOKU --puzzle-count 100 --words 600 --niche "..." --audience "..."
python factory.py book new --topic "..." --kind PUZZLE_WORDSEARCH --puzzle-count 100 --word-list "cat,dog,sun,..." --words 600
```

`kind` es `TEXT` (por defecto), `PUZZLE_SUDOKU` o `PUZZLE_WORDSEARCH`. Para sopa de letras,
`word_list` necesita como mínimo 15 palabras del mismo tema (cada puzzle usa una muestra de 15).

## RESEARCH y BRIEF

Iguales que cualquier libro: investigación real del nicho/audiencia + brief con outline. La
**única regla especial**: el outline del brief tiene que tener **exactamente estos 6 capítulos**
(es lo que genera `puzzles.generate_book`, y `brief_chapters` se usa luego para validar el
manuscrito final):

1. Introduction
2. How to Solve
3. Easy Puzzles
4. Medium Puzzles
5. Hard Puzzles
6. Solutions

Y en "Length": pon un número realista. La intro + instrucciones son un texto corto (típicamente
~500-700 palabras), no un capítulo de 6000 — el valor del libro son los puzzles verificados, no
la prosa. Pedir un `word_count_target` inflado solo invita a meter relleno, que va contra la
regla 5 de `CLAUDE.md`.

## WRITE (generar)

```
python factory.py next --agent <TU-ID>          # reclama la tarea WRITE
python factory.py puzzles <BOOK_ID> --agent <TU-ID>   # genera + renderiza + escribe el manuscrito
python factory.py complete <TASK> --agent <TU-ID> --note "..."
```

`puzzles.generate_book` escribe `manuscript/draft.md` (prosa + referencias de imagen
`![Puzzle N](design/puzzles/puzzle-NNN.png)`), `manuscript/puzzles.json` (datos crudos: grid,
solución, dificultad — para QC) y las imágenes en `design/puzzles/`.

## EDIT / FACT_CHECK

Igual que siempre, pero el trabajo real es sobre la prosa (Introduction/How to Solve); las líneas
`![...]()` se copian tal cual de un paso al siguiente. `validators.py` vuelve a verificar
`puzzles.json` de forma independiente en WRITE, EDIT y FACT_CHECK (nunca confía en que sigue
siendo válido solo porque lo fue una vez).

## FORMAT

Sin cambios de proceso: `python factory.py build <ID>` genera EPUB y PDF normalmente. Las
imágenes de los puzzles se empaquetan dentro del EPUB y se referencian en el PDF igual que
cualquier imagen de un libro de texto (ver `build.md_to_xhtml`'s `img_resolver` — esta
infraestructura de imágenes es genérica, también sirve para fotos de pasos de receta, etc. en
libros de texto normales).

## Dificultad y unicidad (Sudoku)

Clues por dificultad: EASY 42-46, MEDIUM 32-36, HARD 24-28. Cada puzzle se genera quitando
celdas de una solución completa y comprobando después de cada quitada, con un contador de
soluciones por backtracking, que sigue teniendo **exactamente una** solución. Esa misma
comprobación se repite de forma independiente en cada paso de validación — un `puzzles.json`
corrupto o editado a mano se detecta, no se publica.

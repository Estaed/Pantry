# Task-01: Import the MyNetDiary history
> **Execution:** agent `ultracode`
> *Why:* v1 starts with Tarık's 464 real days and 115 foods, so his frequent lists and past days are full on day one.

**Lane**
- OWNS: `tools/import_mynetdiary.py`, `tests/test_import.py`, `tests/fixtures/mynetdiary-slice.json`
- MUST NOT TOUCH: `index.html`, `app/`, `tests/acceptance.py` (Task-00), `references/`
- GATE: `python tests/test_import.py` (from repo root)
- DEPENDS ON: none

## Goal
Tarık runs one command on his PC and gets the Pantry data document built from his whole
MyNetDiary history: every food he ever logged becomes a Pantry food with per 100 g values, and
every entry keeps its date, meal, amount as typed, grams and nutrient totals exactly as
MyNetDiary had them. The tool prints a short summary he can trust at a glance (days, entries,
foods, entries without grams, first and last date) and refuses to write a document whose totals
do not match the source.

Source: `references/mynetdiary-history-2026-10-20.json` (gitignored; 464 days, 2,722 entries,
115 distinct foods; per entry: meal, foodId, food, cleanName, vendor, amount, weightTitle,
weightAmount, grams, kcal, nutrients, servings). How it was pulled and what it covers:
`notes.md` → *MyNetDiary history*. Nutrient keys there are MyNetDiary's (`totalFat`, `satFat`,
`totalCarbs`, `sodium` in mg, ...); map them to the Pantry names, salt = sodium × 2.5 / 1000 g.

## Why
Without it the app opens empty and the day strip shows nothing; with it every acceptance check
of v1 (frequent foods, past days, overage) runs on real data.

## Acceptance
- [ ] `python tools/import_mynetdiary.py references/mynetdiary-history-2026-10-20.json -o .tmp/pantry-data.json` writes the document and prints the summary; on this source: 464 days, 2,722 entries, 115 foods.
- [ ] For every day, the sum of entry kcal in the output equals the source day's sum within 1 kcal; the tool exits non-zero and writes nothing if any day fails.
- [ ] Foods are one per MyNetDiary `foodId`; a food's per 100 g values come from an entry with grams (kcal ÷ grams × 100); a food that never has grams (drinks in ml, restaurant servings) keeps its servings and no per 100 g, and its entries keep their totals.
- [ ] Meals map Breakfast, Lunch, Dinner, Snacks to `breakfast`, `lunch`, `dinner`, `snacks`; entries keep `amount` as typed ("4 eggs", "2 scoops").
- [ ] The output follows the document shape fixed in `tasks/Task-00.md` and holds settings with the targets read from MyNetDiary (2,200 kcal; protein 20 %, carbs 45 %, fat 35 %; salt 5.8 g).
- [ ] `python tests/test_import.py` runs the tool on `tests/fixtures/mynetdiary-slice.json` and checks the cases above; when the full source file exists it also checks the full counts, and when it does not, it says it skipped them.
- [ ] The tool never writes inside `references/` and never into a tracked path; `.tmp/` is the default output folder.

## Out of scope
- Uploading to the data repo (the sync task does that).
- Barcodes: MyNetDiary entries carry none; the catalogue task adds them.
- Any change to the app.

Fixed:
- The fixture holds only days `design/screens.html` already shows (2026-08-08, 2026-10-19, 2026-10-20), cut from the source file.
- Output shape: `tasks/Task-00.md` → Fixed.

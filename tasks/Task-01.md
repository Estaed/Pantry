# Task-01: Import the MyNetDiary history
> **Execution:** agent `ultracode`
> *Why:* v1 starts with Tarık's 464 real days and 115 foods, so his frequent lists and past days are full on day one.

**Lane**
- OWNS: `tools/import_mynetdiary.py`, `tests/test_import.py`
- MUST NOT TOUCH: `index.html`, `app/`, `tests/acceptance.py`, `tests/fixtures/app/`, `.gitignore` (Task-00), `references/`, `tests/fixtures/mynetdiary-slice.json` (main loop)
- GATE: `python tests/test_import.py` (from repo root)
- DEPENDS ON: none

## Goal
Tarık runs one command on his PC and gets the Pantry data document built from his whole MyNetDiary
history: every food he ever logged becomes a Pantry food he can log again (by grams or by its
servings), and every entry keeps its date, meal, amount as typed, grams and nutrient totals
exactly as MyNetDiary had them. The tool prints a summary he can trust at a glance (days,
entries, foods, foods without grams, entries with no nutrients, first and last date, days whose
MyNetDiary "eaten" figure differs from its entries) and refuses to write a document that does not
match the source.

Source: `references/mynetdiary-history-2026-10-20.json` (gitignored, so absent in a worktree: read it at `D:/Projects/Pantry/references/mynetdiary-history-2026-10-20.json`). Top keys `exported, source,
days, errors`; each day `{date, eaten (a string like "2,254"), entries}`; each entry `{meal,
entryNo, foodId, food, cleanName, vendor?, amount, weightTitle, weightAmount, grams|null, kcal,
nutrients, servings: [{amount, title, gm?, kcal}]}`. Measured: 464 days, 2,722 entries, 115
foodIds; 137 entries without grams; 16 foods never have grams (servings, tablets, ml); 55
entries have empty nutrients; one day (2026-04-06) has `eaten` 2,318 against 2,141 from its
entries. How it was pulled: `notes.md` → *MyNetDiary history*.

## Why
Without it the app opens empty and the day strip shows nothing; with it every v1 acceptance check
(frequent foods, past days, overage) runs on real data.

## Acceptance
- [ ] `python tools/import_mynetdiary.py references/mynetdiary-history-2026-10-20.json -o .tmp/pantry-data.json` writes the document and prints the summary; on this source: 464 days, 2,722 entries, 115 foods, 16 foods without grams.
- [ ] Per day, the output's kcal, protein, carbs, fat and salt sums equal the source entries' sums (within 1 kcal and 0.1 g); any mismatch makes the tool exit non-zero and write nothing. Days whose `eaten` differs from their entries are listed in the summary, not fatal (on this source: 2026-04-06).
- [ ] Ids are stable across re-imports: food id = MyNetDiary `foodId`, entry id = `<date>-<entryNo>`.
- [ ] A food's `per100.kcal` = its `gram` serving's kcal × 100 (present on every food with grams; butter comes out at 616.6, not 600 or 620 from a small entry); its other per 100 g values come from its entry with the most grams.
- [ ] A food that never has grams has no `per100`; its servings keep label and `kcal` with `grams: null`, so it can be logged again by serving.
- [ ] Nutrient mapping: carbs = `totalCarbs`, fat = `totalFat`, satFat = `satFat`, fibre = `fiber`, salt = `sodium` (mg) × 2.5 / 1000 g with `sodium` kept as is; the other MyNetDiary nutrients keep their names; `netCarbs` and `diabetesCarbCount` are dropped. A nutrient missing in the source stays absent, never 0; on the full source, entries with empty nutrients carry totals with `kcal` only.
- [ ] name = `cleanName`, brand = `vendor` (absent when MyNetDiary has none); meals map Breakfast, Lunch, Dinner, Snacks to `breakfast`, `lunch`, `dinner`, `snacks`; `amount` stays as typed ("4 eggs", "2 scoops").
- [ ] The output follows the document shape fixed in `tasks/Task-00.md`; settings hold the targets from `notes.md` (2,200 kcal; protein 20 %, carbs 45 %, fat 35 %; salt 5.8 g), written in the tool since the source has none.
- [ ] The tool refuses an output path that `git check-ignore` does not report as ignored, and never writes inside `references/`.
- [ ] `python tests/test_import.py` runs the tool on `tests/fixtures/mynetdiary-slice.json` and checks the cases above; it corrupts one fixture entry's kcal and asserts the tool exits non-zero and writes no file; when the full source exists it also checks the full counts, the 2026-04-06 listing, butter's 616.6 and the empty-nutrients case, and says so when it skips them.

## Out of scope
- Uploading to the data repo (the sync task does that).
- Barcodes: MyNetDiary entries carry none; the catalogue task adds them.
- Any change to the app.

Fixed:
- The fixture `tests/fixtures/mynetdiary-slice.json` is committed by the main loop: the days `design/screens.html` already shows (2026-08-08, 2026-10-19, 2026-10-20), cut from the source unchanged; the hard cases (empty nutrients, ml drinks, the mismatch day, butter rounding) are tested only on the full source.
- Output shape: `tasks/Task-00.md` → Fixed.
- `.tmp/` is ignored by Task-00's `.gitignore`; until that lands the test may run with an ignored temp folder of its own outside the repo.

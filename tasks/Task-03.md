# Task-03: Meal list and gram sheet — frequent foods, usual grams, one-tap add
**Status: DONE** — verified 2026-10-21, eye check pending: 1 (list and gram sheet on Tarık's phone)
> **Execution:** agent `ultracode`
> *Why:* logging a frequent food in three taps or fewer is v1's acceptance, and this is where it happens.

**Lane**
- OWNS: `app/log.js`, `app/drawings.js`, `tests/test_log.py`
- MUST NOT TOUCH: `app/core.js`, `app/registry.js`, `app/base.css`, `tests/acceptance.py`, `index.html`, `sw.js`, and every other `app/*.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_log.py`)
- DEPENDS ON: none

## Goal
From Today, Tarık taps Dinner (or "Add to dinner") and sees `design/screens.html` → *2. Tap Dinner or
Add*: the meal and date, a search field for food or brand with the scan button, tabs Frequent,
Recent and My foods, and rows with the food's drawing, its short name, brand and the amount he
usually logs at that meal ("350 g") with its kcal, and a + that logs exactly that amount at once
(a toast "350 g added to dinner" with Undo). Tapping a row opens the gram sheet (*3. Tap a food*):
the drawing, the name, kcal per 100 g, the grams in big type with his most used amounts for that food
as chips (with how often), the kcal for the portion, the portion's protein / carbs / fat as the
strip, "All nutrients" folding open the rest (salt, sugars, fibre, saturated fat, and any other the
food has), and "Add to <meal>", which logs it and returns to Today. A food that has only servings
(a tablet, "1 serving", ml drinks) offers its servings instead of grams.

Frequent = the foods he logged at that meal in the last 90 days, most often first; usual amount =
`Pantry.usualAmounts(foodId, meal)[0]` (the one rule, in core; chips are its list); Recent = the last distinct foods logged;
My foods = every food, A to Z. Search matches name and brand anywhere in the word list, ignoring case.
With the imported history this list is his MyNetDiary list; with only the starter foods it still works
(no entries yet: Frequent shows the starter foods in their order with "Brand, N g").

Decided (2026-10-20, planner): the row's + stays on the list and shows `Pantry.toast` with Undo, so he
can add several foods in a row; Undo deletes like any delete (the entry goes, a `removed` line is
added). "Add to <meal>" on the gram sheet returns with `Pantry.go('today', date)`. A food with only
servings logs n servings with totals = n × (its last entry's totals ÷ that entry's servings), so his
macros stay; with no entry yet, kcal from the serving only. The gram sheet is drawn over the list
inside this screen (design *3*). Use `Pantry.mealNow()` for a missing meal; log.js's own copy goes.

This task also widens `app/drawings.js` so his common foods get their own drawing: the measured
gaps on his real history are salad (iceberg), banana, pasta (penne), milk, protein powder and
supplements, cereal, cheese, steak, wraps; style C, the same 48 × 48 geometry style.

## Why
It replaces MyNetDiary's search screen, the step he uses most; the + makes a frequent food two taps.

## Acceptance
- [x] With synthetic entries built in the test (one food logged at dinner 5 times as 350 g and once as 375 g most recently, another 3 times, a third once), the Dinner list ranks them 5, 3, 1 and the first row says 350 g; when the full history exists at `D:/Projects/Pantry/references/mynetdiary-history-2026-10-20.json`, the same ranking is checked against counts computed in the test (skip says so when absent).
- [x] The row's + logs one entry with that amount, its totals fixed at log time, the entry's date and meal from the route, and the list stays; Undo in the toast removes it and adds its `removed` line; after the toast, the entry stays.
- [x] The gram sheet: typing 375 shows `Pantry.totals(food, 375).kcal` rounded; a chip sets the grams; "Add to <meal>" logs and returns to Today; an empty, zero or non-number amount says so in words and logs nothing.
- [x] A food with no `per100` offers its servings; logging 2 servings of the Roy Rogers sandwich (fixture, 2026-08-08: 350 kcal, protein 39) stores grams null and totals = 2 × that entry's totals (700 kcal, protein 78); a serving food with no entry gets kcal only.
- [x] On the starter document, search "tza" finds Classic Tzatziki Dip and "coles" lists the two Coles foods; no match says so and offers Scan.
- [x] Routes `add meal [date]` and `food id meal [date]` work as Blueprint → *Screens and seams* says; a bad food id shows a plain message and a way back.
- [x] `PantryDrawing` gives its own drawing (not the generic pack) for at least 90 % of entries of the full history when it exists (the test prints every food name with its drawing key into the report for review; no new key covers unrelated foods, and no catch-all pattern), and for every food of the fixture.
- [x] At 360 × 780 with text at 150 % and at 240 px: no horizontal scroll, long names end with an ellipsis on one line, no console errors, dark and light both render.
- [x] The tests fail when the usual amount is taken from the latest entry instead of the most typed one (shown once, restored).
- [ ] (eye) On Tarık's phone at his text size (1.0; changed from the largest font, Tarık 2026-10-21): the list and the gram sheet (closed and with all nutrients) match `design/screens.html` → *2*, *3*, *3b*; the new drawings sit with the existing ones (same weight and colour logic).

## Out of scope
- Scan and new products (Task-04); editing past entries (Task-05).
- Edits to `tests/acceptance.py`: list any hook change in the report. Hooks it reads: food rows whose accessible name starts with the food name, the five starters in order with "Brand, N g" on the empty document, the "Grams" field, meal radios named Breakfast to Snacks with breakfast checked at 07:00, and the "Add to <meal>" button.

Fixed:
- Routes, drawings, test layout: Blueprint → *Screens and seams*.
- Entry shape: `tasks/Task-00.md` → Fixed; totals at log time.

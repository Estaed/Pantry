# Task-05: Edit, move and delete an entry
> **Execution:** agent `ultracode`
> *Why:* a wrong gram or a meal logged under the wrong meal must be fixed in two taps, on any day.

**Lane**
- OWNS: `app/entry.js`, `tests/test_entry.py`
- MUST NOT TOUCH: `app/core.js`, `app/registry.js`, `app/base.css`, `tests/acceptance.py`, `index.html`, `sw.js`, and every other `app/*.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_entry.py`)
- DEPENDS ON: none

## Goal
Tarık taps an eaten row on Today or on a past day and gets the content of `design/screens.html` → *8. Edit an entry*
as its own screen (a deliberate break, `design/deviations.md`):
the food's drawing and name, the meal and date, the amount in big type (grams, or servings for a
food without grams), his usual amounts as chips, chips to move it to another meal, Delete and Save.
Save changes the amount or the meal and returns with `Pantry.go('today', entry.date)`; Delete removes
the entry, says so in `Pantry.toast` with Undo, and returns the same way. The usual-amount chips come
from `Pantry.usualAmounts(foodId, meal)`.

Changing the grams scales the entry's own totals by new ÷ old grams (an imported MyNetDiary entry
keeps MyNetDiary's values, only scaled); an entry with grams null changes by servings the same way.
Deleting appends `{ id, at }` to `doc.removed` so sync never brings it back; Undo restores the entry
and drops that line. Moving keeps the id.

## Why
Without it a mistake stays in the log, and every past day's total is wrong.

## Acceptance
- [ ] `entry <id>` for a fixture entry of 2026-08-08 shows its food, meal, date and amount; an unknown id shows a plain message and a way back.
- [ ] After the test sets the potato food's `per100.kcal` to 999, setting the 2026-08-08 entry from 1,000 g to 500 g gives kcal 295 and protein exactly half the entry's own (11.333…), not 11.35 from per100.
- [ ] Moving an entry from dinner to lunch keeps its id, date and totals; Today's corners change accordingly (tests read the document, not Today's DOM).
- [ ] Delete removes the entry and appends `{ id, at }` (ISO time) to `doc.removed`; the toast is still there on the day screen after the return; Undo puts the same entry back at the same index (deep equal) and removes that line; after the toast is gone, the deletion stands.
- [ ] An empty, zero or non-number amount is said in words and nothing is saved.
- [ ] At 360 × 780 with text at 150 % and at 240 px: no horizontal scroll, no console errors, dark and light both render.
- [ ] The tests fail when grams are edited by recomputing from per100 instead of scaling the entry (shown once, restored).
- [ ] (eye) On `terra_nt` at 360 dp: the screen carries the content and order of `design/screens.html` → *8. Edit an entry*; Delete is outlined in the danger colour, never filled.

## Out of scope
- Today and the past-day view (Task-02) beyond being opened from them; editing a food's own values.

Fixed:
- Routes, `doc.removed`, scaling rule, drawings, test layout: Blueprint → *Screens and seams*.
- `app/entry.js` is a new script: list `PANTRY_FEATURES.push('app/entry.js');` in the report for the orchestrator to append to `app/registry.js`.

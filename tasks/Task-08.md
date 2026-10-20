# Task-08: Logging the MyNetDiary way: several foods at once, yesterday's meal, instant feedback
> **Execution:** agent `ultracode`
> *Why:* a dinner of his is 3–5 foods, and today each one is a trip from Today to the list and back; logging is the act he repeats most.

**Lane**
- OWNS: `app/log.js`, `app/drawings.js`, `tests/test_log.py`
- MUST NOT TOUCH: `app/core.js`, `app/base.css`, `index.html`, `app/today.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/newfood.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_log.py`)
- DEPENDS ON: none

## Goal
Tarık opens a meal's list to log dinner. The list tells him what is already in that meal today ("In
dinner: 2 foods, 1,422 kcal", the number updating as he adds) and marks the rows already logged there. As in
MyNetDiary (looked at on his phone, 2026-10-21), each row can be ticked: he ticks chicken, rice, butter and
tzatziki and logs them all with one "Add 4 to dinner", each at its usual amount; Undo removes all four.
The + on a row still logs one food at once, and answers in the same frame: the + turns into a check and the
phone gives a short pulse (`Pantry.haptic`), then the save runs. When yesterday's same meal had entries, a
row at the top offers "Same as yesterday's dinner" with its foods and kcal; one tap logs them with their
amounts and log-time totals scaled from yesterday's entries, with one Undo.

The gram sheet: the amount is selected when it opens, so typing replaces it; Enter logs when the amount is
valid; the chips are his usual amounts and the pack size without the "59×" use counts that confused him
(MyNetDiary shows "500g 350g 1000g g serving"); macros read carbs, protein, fat (`Pantry.MACROS`). A toast
after a log carries the food's drawing (`Pantry.toast` `drawing`) and names the food when one food was logged.

Start from `reports/2026-10-21-qol-research.md` (picks 3, 4, 5, 8 and its motion spec). The prototype may be
departed from where logging gets faster (Blueprint, 2026-10-21); list each departure in the report for
`design/deviations.md`.

## Why
Most of his time in the app is here; the multi-select and yesterday's meal remove the round trips, and
instant feedback removes the moment of doubt after each tap.

## Acceptance
- [ ] With fixture entries for dinner today, the list's summary line shows their count and kcal; after a + the line and the logged row's mark update without leaving the list.
- [ ] Ticking three foods and tapping Add logs three entries, each with its usual amount and totals as a single + would have; Undo removes exactly those three; nothing is logged when none is ticked.
- [ ] "Same as yesterday's <meal>" appears only when yesterday's same meal has entries; it logs one new entry per yesterday's entry with the same amount and the same totals as yesterday's entry (log-time values, not recomputed from per100 — the test changes a food's per100 first), new ids, today's date; one Undo removes them all.
- [ ] The + calls `Pantry.haptic('tap')` and shows its check before the save starts (the test reads the order).
- [ ] The gram sheet opens with the amount selected; Enter with a valid amount logs like the Add button; with an invalid one it says why and logs nothing.
- [ ] No chip shows a use count; macros on the sheet are in the order carbs, protein, fat.
- [ ] Logged entries keep their nutrient totals from log time (Blueprint): editing a food after logging never changes them (existing check stays green).
- [ ] At 360 × 780 and text 1.0: no horizontal scroll, long names end with an ellipsis, no console errors, dark and light render.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: logging a 4-food dinner takes one visit to the list; the feedback on + feels immediate; the sheet's Add stays visible with the keyboard open.

## Out of scope
- Screen transitions and the keyboard viewport setting (Task-07), Today (Task-09), scanning and new foods, editing entries.
- Copying a meal from any day but yesterday (later list in the research report).

Fixed:
- Saving from the sheet still returns with `Pantry.go('today', date)`; multi-select and "Same as yesterday" stay in the list (the toast's Undo works there).
- Routes `add <meal> [date]` and `food <foodId> <meal> [date]`, `Pantry.usualAmounts`, entry shape: Blueprint → *Screens and seams*.
- Tests that need yesterday drive the page clock (as `tests/test_today.py` does), never real time.

# Task-08: Logging the MyNetDiary way: several foods at once, yesterday's meal, instant feedback
> **Execution:** agent `ultracode`
> *Why:* a dinner of his is 3–5 foods, and today each one is a trip from Today to the list and back; logging is the act he repeats most.

**Lane**
- OWNS: `app/log.js`, `app/drawings.js`, `app/newfood.js`, `tests/test_log.py`, `tests/test_scan.py`
- MUST NOT TOUCH: `app/core.js`, `app/base.css`, `index.html`, `app/today.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_log.py`)
- DEPENDS ON: none

## Goal
Tarık opens a meal's list to log dinner. The list tells him what is already in that meal today ("In
dinner: 2 foods, 1,422 kcal", the number updating as he adds) and marks the rows already logged there. As in
MyNetDiary (looked at on his phone, 2026-10-21), each row can be ticked: he ticks chicken, rice, butter and
tzatziki and logs them all with one "Add 4 to dinner", each at its usual amount; Undo removes all four.
After Add the ticks clear and the logged rows show their mark. A food with no usual amount cannot be
ticked (its + opens the sheet, as now). The + on a row still logs one food at once, and answers before the
save: the + turns into a check and the phone gives a short pulse (`Pantry.haptic`), the browser paints that,
then the save runs. When the day before the shown day had entries in the same meal, a
row at the top offers "Same as yesterday's dinner" with its foods and kcal; one tap logs them with their
amounts and their totals copied unchanged, with one Undo; the row then shows it was logged until Undo.

The gram sheet: the amount is selected when it opens, so typing replaces it; Enter logs when the amount is
valid; the chips are his usual amounts and the pack size without the "59×" use counts that confused him
(MyNetDiary shows "500g 350g 1000g g serving"); macros read carbs, protein, fat (`Pantry.MACROS`), here and on New food (Found and From the label). A toast
after a log carries the food's drawing (`Pantry.toast` `drawing`) and names the food when one food was logged.

Start from `reports/2026-10-21-qol-research.md` (picks 3, 4, 5, 8 and its motion spec). The prototype may be
departed from where logging gets faster (Blueprint, 2026-10-21); list each departure in the report for
`design/deviations.md`.

## Why
Most of his time in the app is here; the multi-select and yesterday's meal remove the round trips, and
instant feedback removes the moment of doubt after each tap.

## Acceptance
- [ ] With fixture entries for dinner today, the list's summary line shows their count and kcal; after a + the line and the logged row's mark update without leaving the list.
- [ ] Ticking three foods and tapping Add logs three entries, each with its usual amount and totals as a single + would have; Undo removes exactly those three; nothing is logged when none is ticked; tapping Add twice fast logs one set; the ticks are clear afterwards.
- [ ] "Same as yesterday's <meal>" appears only when the shown day − 1 has entries in that meal (a list opened for 2026-08-08 offers 2026-08-07's); tapped twice fast it logs one set; it logs one new entry per yesterday's entry with the same amount and the same totals as yesterday's entry (log-time values, not recomputed from per100 — the test changes a food's per100 first), new ids, today's date; one Undo removes them all.
- [ ] The + calls `Pantry.haptic('tap')`; when its click handler returns the check is visible and the document is still unchanged; the entry is saved on the next frame.
- [ ] The gram sheet opens with the amount selected; Enter with a valid amount logs like the Add button; with an invalid one it says why and logs nothing.
- [ ] No chip shows a use count; macros on the sheet and on New food read carbs, protein, fat.
- [ ] Logged entries keep their nutrient totals from log time (Blueprint): editing a food after logging never changes them (existing check stays green).
- [ ] At 360 × 780 and text 1.0: no horizontal scroll, long names end with an ellipsis, no console errors, dark and light render.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: logging a 4-food dinner takes one visit to the list; the feedback on + feels immediate; after integration with Task-07, the sheet's Add stays visible with the keyboard open.

## Out of scope
- Screen transitions and the keyboard viewport setting (Task-07), Today (Task-09), scanning and new foods, editing entries.
- Copying a meal from any day but yesterday (later list in the research report). The scan flow itself (barcode to food) waits for his five-pack trial.

Fixed:
- Saving from the sheet still returns with `Pantry.go('today', date)`; multi-select and "Same as yesterday" stay in the list (the toast's Undo works there).
- Routes `add <meal> [date]` and `food <foodId> <meal> [date]`, `Pantry.usualAmounts`, entry shape: Blueprint → *Screens and seams*.
- Tests that need yesterday drive the page clock (as `tests/test_today.py` does), never real time.

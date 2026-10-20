# Task-02: Today in full — day strip, meals in the corners, ring, macro strip
**Status: DONE** — verified 2026-10-21, eye check pending: 1 (Today and a past day on Tarık's phone)
> **Execution:** agent `ultracode`
> *Why:* Today is the screen Tarık opens many times a day; it has to read at a glance, as designed.

**Lane**
- OWNS: `app/today.js`, `tests/test_today.py`
- MUST NOT TOUCH: `app/core.js`, `app/registry.js`, `app/base.css`, `tests/acceptance.py`, `index.html`, `sw.js`, and every other `app/*.js` (other wave-2 tasks)
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_today.py`)
- DEPENDS ON: none

## Goal
Tarık opens Pantry and sees his day the way `design/screens.html` → *1. Today* draws it: the date and
"Today" (or "8 Aug" for a past day) with a settings button; the day strip of seven days, each a small
tank filled to that day's kcal with a slow wave on top, the dashed 2,200 line, and the difference to
budget under each day ("+92", "−51", "today"); the four meals in the corners (Breakfast top left,
Lunch top right, Dinner bottom right, Snacks bottom left) with their kcal and the drawings of what he
ate, or a dashed + when empty; the ring in the middle (G3: each meal starts in its own quarter, or
where the one before ended, and runs on, alternating dark and light grey with its initial), with kcal
left as the one orange number and eaten / budget under it; the macro strip (B1: protein, carbs, fat as
one row whose widths are each one's share of protein × 4 + carbs × 4 + fat × 9, percentages inside,
grams against target underneath); the list of what he ate that day; and at the bottom "Add to <meal>" with the scan button.

Everything is live: tapping a day opens that day (`today date`), swiping the strip shows the week
before or after, tapping a corner opens that meal's list (`add meal date`), tapping an eaten row
opens it for editing (`entry id`), the bottom button opens the list for the meal the clock suggests
(on a past day, "Add to this day"), the scan button opens `scan meal date`, the gear opens `settings`.
Those other screens are built in parallel; this task only navigates to them (Blueprint → *Screens and seams*).
Today also owns two states: the design's *Sync failed* banner when `Pantry.syncState().lastError` is a
sentence (redraw on the `'sync'` announcement; one `.banner` at a time, the unreadable-log banner wins),
and the *First launch* empty plate when the document has no entries at all.

Decided (2026-10-20, planner): on a past day the bottom button opens `add <Pantry.mealNow()> <date>`;
past 2,200 the ring is full and the centre says "N kcal over"; the strip's scale is the larger of
2,750 and 1.25 × the budget; a swipe moves the strip by a week without changing the shown day; an
argument that is not a `YYYY-MM-DD` date shows today.

## Why
It is the dashboard of v1 and the reference all eye checks start from; the day strip is how Tarık
checks past overage and jumps to a day (he used MyNetDiary's strip exactly for that).

## Acceptance
- [x] With the 8 Aug 2026 day of `tests/fixtures/mynetdiary-slice.json` loaded (converted with `tools/import_mynetdiary.py` into the document), Today for `2026-08-08` shows 224 kcal left, 1,976 / 2,200, the corners 888, 350, 590, 148, and the macro shares 50 / 36 / 15 % in that order (the design shows the same numbers).
- [x] The ring's segments, measured from the drawn arcs, start and end where the spill rule puts them: on 2026-08-08 breakfast −90° to 55°, lunch 55° to 112°, dinner 112° to 209°, snacks 209° to 233°; on 2026-10-19 (breakfast 988, no lunch, dinner 1,304) dinner starts at 90°, not at 71.7° (within 2°).
- [x] The day strip shows the seven days ending at the shown day; each day's fill height is its kcal ÷ 2,750 (capped), its label is the signed difference to the budget, a day over budget is marked; tapping a day opens it, a swipe moves a week; with no entries on a day its tank is empty and labelled "−2,200".
- [x] With reduced motion off each day's wave has a running CSS animation (`animationName` not `none`, `animationPlayState` running); with `prefers-reduced-motion: reduce` none does.
- [x] Tapping each corner, the bottom button, the scan button, an eaten row and the gear calls `Pantry.go` with the route and arguments from Blueprint → *Screens and seams* (tests spy on `location.hash`).
- [x] At 360 × 780 with text at 150 % and at 240 px: no horizontal scroll, the corner labels never overlap the ring (bounding boxes), no console errors; in dark and in light the computed canvas and ink colours differ and both are screenshotted to `.tmp/`. Every text, the ring's initials included, is sized in rem (the gate's text-growth check).
- [x] Today updates within the same frame when an entry is added or removed (subscribe), and when the day turns at midnight Darwin time.
- [x] With `lastError` set, Today shows the banner and its sentence; cleared, it goes; the first-launch state shows when entries is empty.
- [x] The tests in `tests/test_today.py` fail when the spill rule is replaced by plain consecutive segments, and when the strip uses UTC dates (shown once in the report, then restored).
- [ ] (eye) On Tarık's phone at his text size (1.0; changed from the largest font, Tarık 2026-10-21), Today for 20 Oct and for 8 Aug matches `design/screens.html` → *1. Today* and *7. A past day*; the long empty-state text does not balloon (Chrome text boosting) next to the rest.

## Out of scope
- The food list, gram sheet, scan, entry editing and settings screens (Task-03 to Task-06).
- Any edit to `tests/acceptance.py`. Hooks it reads on Today: `data-test="kcal-left"`, the eyebrow `.top .eyebrow` = "Tuesday, 20 October", eaten rows `.fr` with `.name`/`.sub` on one line with an ellipsis (one row "Breakfast, 350 g" after its log test), one `.banner` for an unreadable log, the buttons "Add food" and "Scan a barcode". The design's button says "Add to dinner": keep an accessible name the gate finds or list the hook change; the orchestrator moves it.

Fixed:
- Routes, `doc.removed`, drawings and test layout: Blueprint → *Screens and seams*.
- Drawings: `window.PantryDrawing(food, size)`; tones and sizes from `design/DESIGN.md` and `design/screens.html`.
- The wave in each day is the one deliberate looping animation (`design/deviations.md`).

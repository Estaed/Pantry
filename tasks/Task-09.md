# Task-09: Today in colour and motion: over budget at a glance, swipe between days
> **Execution:** agent `ultracode`
> *Why:* on his phone going over budget changed nothing he could notice, the strip jumps under his finger, and the screen gives no sign of what a log changed.

**Lane**
- OWNS: `app/today.js`, `tests/test_today.py`
- MUST NOT TOUCH: `app/core.js`, `app/base.css`, `index.html`, `app/log.js`, `app/drawings.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/newfood.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_today.py`)
- DEPENDS ON: none

## Goal
Tarık glances at Today and knows at once whether he is within budget: as in MyNetDiary, the status shows in
colour, green while within and red once over (`--ok`, `--over` in `app/base.css`; Blueprint and
`design/DESIGN.md`, 2026-10-21): the ring, the kcal-left number (over budget it says how much over), the
macro bars against their targets, and each day in the strip. Over budget must be unmistakable on its own.
The macros read carbs, protein, fat (`Pantry.MACROS`).

Swiping the ring (the calorie circle) left goes to the next day and right to the previous day, as in
MyNetDiary; the header date moves with it and the numbers update; there is no day after today. Tapping a
day in the strip switches to it in place: the strip does not move under his finger and the switch does not
stack history entries (back from a past day returns where he came from, not through every day tapped). A past
day shows a way back to Today. When he returns after logging, Today shows what changed: the meal's arc grows
from its old end, the bars move to their new values and the kcal-left number changes last; nothing animates
on a return that changed nothing, and numbers never count up.

Start from `reports/2026-10-21-qol-research.md` (picks 6, 7, the motion spec) and his list in
`docs/TASKS_INDEX.md` → Wave 3. The prototype may be departed from (Blueprint, 2026-10-21); list each
departure in the report for `design/deviations.md`.

## Why
Today is the screen he opens 20+ times a day; the budget state and the day are what he reads there.

## Acceptance
- [ ] Within budget the ring, kcal-left number and day cells use the status colour for within; one kcal over budget they all switch to over and the number reads how much over; each macro bar is within or over by its own target. Tests read computed colours against `--ok` / `--over`, in dark and light.
- [ ] A left swipe on the ring opens the next day, a right swipe the previous one; on today a left swipe does nothing; a vertical scroll that starts on the ring still scrolls the page.
- [ ] Tapping three days in the strip and pressing back once returns to the screen before the first tap; the strip's position does not change on a tap; a past day offers Today, which opens Today.
- [ ] After an entry is added for dinner, returning to Today animates only what changed (the dinner arc, the bars, the numbers), and the kcal-left number finishes last; with reduced motion nothing moves; a return with no change starts no animation.
- [ ] Macros read carbs, protein, fat everywhere on Today.
- [ ] The existing Today checks stay green, updated only where an assertion pinned the old order or colour (each such line listed in the report).
- [ ] At 360 × 780 and text 1.0: no horizontal scroll, no console errors, dark and light render.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: over budget is obvious at a glance; swiping the ring between days feels natural; the strip stays still under his finger.

## Out of scope
- Screen-to-screen transitions (Task-07), the list and sheet (Task-08), Settings.

Fixed:
- Route `today [date]` and `Pantry.go('today', date)`; the status colours are the `--ok` / `--over` custom properties, never new hex values.
- Tests drive the page clock for time and motion, never real waits.

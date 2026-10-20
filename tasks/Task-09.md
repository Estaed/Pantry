# Task-09: Today in colour and motion: over budget at a glance, swipe between days
> **Execution:** agent `ultracode`
> *Why:* on his phone going over budget changed nothing he could notice, the strip jumps under his finger, and the screen gives no sign of what a log changed.

**Lane**
- OWNS: `app/today.js`, `tests/test_today.py`
- MUST NOT TOUCH: `app/core.js`, `app/base.css`, `index.html`, `app/log.js`, `app/drawings.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/newfood.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_today.py`)
- DEPENDS ON: none

## Goal
Tarık glances at Today and knows at once whether he is within budget: as in MyNetDiary, the screen changes
colour when he goes over, but in Pantry's own design language, not MyNetDiary's literal green and red
(Tarık, 2026-10-21: "tasarıma uygun bir şey yapsın, direkt birebir yeşil kırmızı olmasın, o renk
değişiminden bahsettim"). Within budget reads calm; over budget is unmistakable on its own. The change shows
on the ring, the kcal-left number (over budget it says how much over), the macro bars against their
targets, and each day in the strip; a day with nothing logged stays neutral. Pick the tones from the base
palette tokens (`D:/TarikOS/.brain/skills/tasarim/references/DESIGN.md`, `tokens.css`), defined inside
`app/today.js`; say in the report which tokens and why.
The macros read carbs, protein, fat (`Pantry.MACROS`).

Swiping the ring (the calorie circle) left goes to the next day and right to the previous day, as in
MyNetDiary; the header date moves with it and the numbers update; there is no day after today. Tapping a
day in the strip switches to it in place: the strip does not move under his finger and the switch does not
stack history entries. A past day shows a way back to Today, which switches in place too. When he returns after logging, Today shows what changed: the meal's arc grows
from its old end, the bars move to their new values and the kcal-left number changes last; nothing animates
on a return that changed nothing, and numbers never count up. What changed is found by comparing the drawn
values, so a redraw for another reason (a sync announcement) never replays it; Undo plays the same change back.

Start from `reports/2026-10-21-qol-research.md` (picks 6, 7, the motion spec) and his list in
`docs/TASKS_INDEX.md` → Wave 3. The prototype may be departed from (Blueprint, 2026-10-21); list each
departure in the report for `design/deviations.md`.

## Why
Today is the screen he opens 20+ times a day; the budget state and the day are what he reads there.

## Acceptance
- [ ] Within budget the ring, kcal-left number and day cells use the within tone; once the rounded number shown passes the budget by 1 they switch to the over tone and the number reads how much over; each macro bar is within or over by its own target; a day with no entries stays neutral. Tests read computed colours, in dark and light, and the two states differ.
- [ ] A left swipe on the ring opens the next day, a right swipe the previous one; on today a left swipe does nothing; a vertical scroll that starts on the ring still scrolls the page.
- [ ] Tapping three days in the strip (or swiping the ring) and pressing back once returns to the day shown before the first switch; the strip's position does not change on a tap; a past day offers Today, which switches to today in place.
- [ ] After an entry is added for dinner, returning to Today animates only what changed (the dinner arc, the bars, the numbers), and the kcal-left number finishes last; with reduced motion nothing moves; a return with no change starts no animation, and a `Pantry.setSyncState` right after a return does not replay it.
- [ ] Macros read carbs, protein, fat everywhere on Today.
- [ ] The existing Today checks stay green, updated only where an assertion pinned the old order or colour (each such line listed in the report).
- [ ] At 360 × 780 and text 1.0: no horizontal scroll, no console errors, dark and light render.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: over budget is obvious at a glance; swiping the ring between days feels natural; the strip stays still under his finger.

## Out of scope
- Screen-to-screen transitions (Task-07), the list and sheet (Task-08), Settings.

Fixed:
- Route `today [date]` and `Pantry.go('today', date)`; status tones come from the base tokens, never new hex values.
- Day switching in place: the first switch (tap, swipe, Today action) pushes one history entry with the same hash and `state.day`, handled by `app/today.js`'s own `popstate` (the pattern `app/log.js` uses for the gram sheet); later switches replace it; `app/today.js` never changes `location.hash` itself, so core's router stays in step. A deep link `#/today/<date>` still opens that day.
- Tests drive the page clock for time and motion, never real waits.

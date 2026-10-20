# Task-07: Screens that move, a router that forgives, Settings and Edit that answer
> **Execution:** agent `ultracode`
> *Why:* every screen change is a hard cut today, a fast second tap lands on the wrong screen, and Edit saves silently; this is the "animasyon eksikliği" Tarık feels first.

**Lane**
- OWNS: `app/core.js` (routing, screens and their motion only), `app/base.css`, `index.html`, `app/entry.js`, `app/settings.js`, `tests/test_shell.py`, `tests/test_entry.py`, `tests/test_sync.py`
- MUST NOT TOUCH: `app/today.js`, `app/log.js`, `app/drawings.js`, `app/scan.js`, `app/newfood.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`, `tools/`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_shell.py`)
- DEPENDS ON: none

## Goal
Tarık logs four to eight times a day on his Galaxy S24 at text size 1.0. Moving between screens should
feel like one app, not page swaps: opening a screen (Today → list, → Edit entry, → Settings, → Scan)
slides the new one in a short way from the right while the old one fades; going back reverses it; a save
or delete that returns to Today crossfades. When Chrome already animated a back swipe, the app does not
animate it a second time. Reduced motion turns every slide into a fade. A second tap within a moment of a
navigation never opens another screen (today two quick taps on Delete land on Today's Add). Coming back to
Today puts him where he was in it, not at the top.

Edit entry answers: Save shows "Saved, 200 g" with Undo (the drawing of the food in the toast) and Undo
restores the entry exactly; macro lists read carbs, protein, fat (`Pantry.MACROS`). Settings shows the macro
split as carbs / protein / fat (stored values unchanged, only the order they are shown and typed in), and
the history row counts every logged day: the imported MyNetDiary days plus the days logged in Pantry, in
the form Tarık asked for ("464 (+10)": MyNetDiary days, then Pantry days), never "0 days" when the log has
days. The typed grams field and its button stay above the keyboard on Android (the viewport resizes with
the keyboard).

Design: `reports/2026-10-21-qol-research.md` → *Motion spec* is the starting point (durations and easings
from the base tokens); the base motion rules are in `D:/TarikOS/.brain/skills/tasarim/references/DESIGN.md`.
The prototype may be departed from where daily use gets better (Blueprint, 2026-10-21); record each
departure in the report for `design/deviations.md`.

## Why
Motion and a forgiving router are the shared layer every other wave 3 screen sits on, and the two
silent defects (double tap, silent save) were found in wave 2 and left open.

## Acceptance
- [ ] A push, a back and a return-to-Today each run their own transition; the test reads which one ran (e.g. a type or class the transition sets) and the screen that results; with reduced motion no element moves (opacity only).
- [ ] When a popstate reports that the browser already animated it, the app runs no transition of its own.
- [ ] Two navigations within 350 ms: the second does nothing (Delete tapped twice ends on Today, not on Add); a navigation 400 ms later works. Tests drive the clock, never sleep through it.
- [ ] Today's scroll position comes back after list → Today via back.
- [ ] Edit entry Save: one toast "Saved, <amount>" with Undo and the food's drawing; Undo makes the entry deep-equal to before; the toast does not survive a second screen change.
- [ ] Settings: the split editor reads and writes carbs, protein, fat in that order and saves the same `settings.targets` shape as before (a document saved by wave 2 opens unchanged); the history row shows MyNetDiary days and Pantry days ("464 (+N)" for the full history plus N Pantry days) and is right for an empty log, an import-only log and a Pantry-only log.
- [ ] `Pantry`'s public API keeps every name and signature listed in the header of `app/core.js` (a test lists them).
- [ ] At 360 × 780 and text 1.0: no horizontal scroll, no console errors, dark and light render.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: opening and leaving each screen feels smooth and quick, nothing double-animates on the back swipe, and the grams field's button stays visible with the keyboard open.

## Out of scope
- Today's own motion and layout (Task-09), the list and gram sheet (Task-08), new screens, the scan flow.
- Copying the base `tarik-motion.js` into the app: write what this task needs in its own files.

Fixed:
- The `Pantry` API names and signatures in the header of `app/core.js` (other wave 3 tasks call `toast`, `haptic`, `MACROS`, `go`, `back`, `home`).
- Saving and deleting still return with `Pantry.go('today', date)` (Blueprint → Screens and seams).
- Lesson: Chrome on Android boosts long paragraphs; `text-size-adjust: none` on `html` already stops it (`D:/TarikOS/knowledge/concepts/android-chrome-metin-buyutme-headless-gormez.md`).

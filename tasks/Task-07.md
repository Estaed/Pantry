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
navigation never acts again (today two quick taps on Delete land on Today's Add): the guard is on taps
(the tap that started a navigation and any tap within 350 ms of it, by the event's own time), never on
`popstate` or a direct `Pantry.go` call, so tests and the back gesture keep working. Going back to Today
(button or gesture) puts him where he was in it; a save or delete that returns to Today opens it at the top.

Edit entry answers: Save shows "Saved, 200 g" with Undo (the drawing of the food in the toast) and Undo
restores the entry exactly; macro lists read carbs, protein, fat (`Pantry.MACROS`). Settings shows the macro
split as carbs / protein / fat (stored values unchanged, only the order they are shown and typed in), and
the history row counts every logged day: M MyNetDiary days plus P days logged only in Pantry, shown as
"M (+P)" when P > 0 and "M" when P = 0 (Tarık: "460 (+10)"); a day with both kinds counts as MyNetDiary
(2026-10-20 is one); an empty log shows "0"; a Pantry-only log shows "0 (+P)". The typed grams field and its button stay above the keyboard on Android (the viewport resizes with
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
- [ ] Two taps within 350 ms: the second does nothing, whether it lands on a navigation (Delete tapped twice ends on Today, not on Add) or on a control that changes data (a list row's + logs nothing); a tap 400 ms later works; back-to-back `Pantry.go` calls and popstates are never dropped, so `tests/acceptance.py` and `tests/test_core.py` stay green unchanged. Tests use the event time, never sleep.
- [ ] Today's scroll position comes back after list → Today via back; a save that returns with `Pantry.go('today', date)` opens Today at the top.
- [ ] A back during a running transition ends on the right screen with no console error (a skipped transition's rejected promise is handled).
- [ ] Edit entry Save: one toast "Saved, <amount>" with Undo and the food's drawing; Undo makes the entry deep-equal to before; the toast does not survive a second screen change.
- [ ] Settings: the split editor reads and writes carbs, protein, fat in that order and saves the same `settings.targets` shape as before (a document saved by wave 2 opens unchanged); the history row reads exactly "0" (empty log), "464" (the full import), "0 (+3)" (three Pantry-only days) and "464 (+2)" (the import plus two Pantry-only days, with one more Pantry entry on 2026-10-20 that adds no day).
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
- A `popstate` that leaves the hash unchanged is not a screen change (the gram sheet in `app/log.js` and Today's day switching use one): no transition, no guard, no scroll change.
- Lesson: Chrome on Android boosts long paragraphs; `text-size-adjust: none` on `html` already stops it (`D:/TarikOS/knowledge/concepts/android-chrome-metin-buyutme-headless-gormez.md`).

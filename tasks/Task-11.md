# Task-11: A meal's list opens on that meal, and tapping a food never logs by surprise
> **Execution:** agent `ultracode`
> *Why:* after a day on the phone Tarık could not find how to take a wrongly logged food out of a meal, a tap on a food's drawing ticked it when he meant to open it, and a check mark floated over the search box.

**Lane**
- OWNS: `app/log.js`, `tests/test_log.py`
- MUST NOT TOUCH: `app/core.js`, `app/base.css`, `index.html`, `app/today.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/newfood.js`, `app/drawings.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_log.py`)
- DEPENDS ON: none

## Goal
Tarık opens a meal from Today (a corner, or the floating +) on his Galaxy S24, text size 1.0, in the installed
app (Samsung Internet). The list opens on that meal: a first tab named after it ("Lunch") lists what is already
in lunch that day, each entry with its amount and kcal; tapping one opens Edit entry, and each row also offers a
way to take it out right there (`Pantry.removeEntry`, with Undo), so he stays in Lunch to log the right food.
Frequent, Recent and My foods follow as tabs, on one line at 360 px and text 1.0. The "In lunch: N foods, kcal" line
stays under the title on every tab; "Same as yesterday's lunch" belongs to Frequent. When the meal is still empty the list opens on Frequent,
as today. Tarık, 2026-10-21: "breakfast'a tıkladım direkt tüm liste yerine oradaki liste çıksın, sağdaki liste
frequent olsun ama liste boş ise frequent çıksın".

In the food lists, the + logs the food at once (as today). Tapping anywhere else on a row, its drawing included,
opens the gram sheet; it never ticks or logs. The sheet opens without the keyboard: the amount shows, the chips
work, and the keyboard comes up only when he taps the amount (then it is selected, so typing replaces it). Several
foods at once (Task-08's ticks and "Add N to <meal>") stay possible, started in a way he will not trigger by
accident when he only wants to open a food (for example a long press on a row); the builder picks the gesture and
says why. Tarık, 2026-10-21: "direkt resime tıkladığımızda eklemek değil de artıya tıkladığımızda direkt eklesin,
üstüne tıkladığımızda menü açılsın ama direkt klavye getirme, sayının üstüne tıklarsam getir".

The grey "already in this meal" check on a food's drawing stays on its row: today it floats over the search box and
the tabs when the list scrolls (Tarık's screenshot, 2026-10-21: two checks above "Food or brand").

## Why
Logging is the app's whole job and he does it 4 to 8 times a day; a wrong tap must cost nothing and a wrong entry
must be easy to take back. Opening the keyboard with the sheet also left Samsung Internet's back key dead until he
restarted the app (Tarık, 2026-10-21: "yemeğin üstüne tıklayıp klavye açılırsa o zaman bozuluyor gibi geri tuşu").

## Acceptance
- [ ] Opening `add <meal> <date>` for a meal with entries that day shows the meal's tab first and selected, listing exactly those entries (name, amount, kcal) in log order; tapping one opens `entry <id>`. For an empty meal the list opens on Frequent and the meal's tab says it is empty.
- [ ] Taking an entry out from the meal's tab goes through `Pantry.removeEntry` (a `doc.removed` line, Undo puts it back deep-equal and drops that line), keeps him on the list, and takes at most two deliberate steps; it is never a plain tap on the row.
- [ ] The meal's tab follows the data both ways: an entry logged with + on another tab, or removed elsewhere (another tab, sync), shows or leaves without a reload.
- [ ] A tap on a row's drawing or name opens the gram sheet and changes no entry; a tap on + logs exactly one entry (a quick double tap still logs one, as Task-08 made it).
- [ ] The gram sheet opens with no focused field (no keyboard on the phone); a tap on the amount focuses and selects it; Enter and Add still log; the sheet's other controls work without the keyboard.
- [ ] Ticking several foods and "Add N to <meal>" still work through the new start gesture, and that gesture is not a plain tap; ending it opens no sheet, a finger resting during a scroll starts nothing, and the browser's text-selection menu does not appear.
- [ ] With the list scrolled so a check lies under the sticky search and tabs, the check is painted under them: `elementFromPoint` at its centre does not return the check (the bug is paint order, not position; the check may still stick out of its drawing as drawn).
- [ ] At 360 × 780, text 1.0, light and dark: no horizontal scroll, no console errors.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: opening Lunch after logging lunch shows lunch first; taking a wrong food out takes two taps and leaves him in Lunch; a tap on a food never logs it; the keyboard comes only from the amount, and typing then replaces the amount (not "3502"); with the keyboard up, Back closes the keyboard, Back closes the sheet, Back leaves the list (Samsung Internet).

Gate hooks: `tests/acceptance.py` (check_phone, after a breakfast entry exists) and `tests/test_shell.py` (lines
clicking the first `.log-open` and waiting for the first `[data-act="plus"]` on `add dinner 2026-08-08`, a day with a
dinner entry) reach the first food row on the add screen. The meal tab's rows must not be what those reach (no
`.fr`, `.log-open` or plus on them), and when the meal tab opens first those tests need Frequent selected: name the
exact change under seams_missing; the orchestrator moves those old-look steps at integration.

## Out of scope
- Today's screen (Task-12), the theme (Task-13), Edit entry's own screen.

Fixed: route `add <meal> [date]` and `entry <id>` as in Blueprint → Screens and seams.

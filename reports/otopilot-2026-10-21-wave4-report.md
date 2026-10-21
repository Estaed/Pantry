# Otopilot report: Pantry wave 4 (2026-10-21)

Plan: `reports/otopilot-2026-10-21-wave4-plan.md`. One Workflow (`wf_b6efce3a-2ae`, 20 agents, 175 min): Opus/xhigh
builders, an Opus/high review panel, a fixer loop of at most 3 rounds. Codex `sol`/high read every builder commit and
every final commit. BASE `e112c41`.

| Task | Outcome | Main | Gate on main | Panel rounds | Second family |
|---|---|---|---|---|---|
| Task-11 The meal list opens on that meal | DONE, eye check pending: 5 | 31edebb (+ hook moves in the integration commit) | ALL PASS | 3 fix rounds | Codex, both commits: no findings |
| Task-12 Today at a glance | DONE, eye check pending: 6 | 580cacb | ALL PASS | 1 fix round | Codex, builder commit: 1 real (already fixed by the panel), 1 negligible; final commit: the negligible one again |
| Task-13 Theme in Settings | DONE, eye check pending: 4 | 610c913 | ALL PASS | 1 round, nothing to fix | Codex, final commit: no findings |

## Added after the wave (orchestrator)
- **Task-12, second lap.** Tarık asked for this after the builder had started (`eb92dc8`). Past the budget the ring runs
  on from 12 o'clock as a second lap: excess ÷ budget × 360°, at most one whole lap. The first lap goes to light
  red tints. The second lap's red deepens with the excess: 75 % of `danger` just over, full red from 25 % over.
  About 60 lines in `app/today.js`, folded into Task-12's one commit (`797a1d0`).
  Its new checks:
  - 19 Oct draws a 15.1° lap.
  - Within budget there is no lap, and the gap equals what is left.
  - 10 %, 25 %, 50 % and 120 % over draw 36°, 90°, 180° and 360°.
  - The tone is lighter at 10 % over than at 50 %, and full `danger` at 25 %.

  Each check went red when its behaviour was broken (no lap / no cap / flat tone), and the file was restored
  byte for byte.
  One older status assertion changed: it had expected the first lap's arcs to be full red, and now expects light tints.
- **Gate hooks Task-11 named.** The list now opens on the meal's own tab when the meal has entries, so these old
  steps now pick the Frequent tab first:
  - `tests/acceptance.py` check_phone: the offline step and the 240 px step.
  - `tests/test_shell.py`: the copies step and the tap-guard step.
- Service worker cache bumped to `pantry-v6`. Wave 4 departures recorded in `design/deviations.md`.

## Use check
- Tarık's phone was not on the cable at integration, so the Samsung Internet check has not been done yet.
- Instead, main was served and looked at on the PC (360 × 780, text 1.0, light and dark), with no console errors:
  - Today on 19 Oct: the ring is full with a 15° deeper-red second lap, the macro marks show −9 / +4 / +5, and
    the eaten section has a tab per meal with a trash icon on each row.
  - Scrolled to the end, the last row sits clear of the + and Scan.
  - Breakfast's list opens on its own tab, each entry with a −.
  - Settings shows the Theme group second.

  Shots: `.tmp/usecheck-w4/`.

## Left open (not failures)
- Deleting the only entry of a whole log brings back the first-launch screen (Codex). This needs a log with
  exactly one entry, so it was not fixed.
- A short meal's page sits on blank space as tall as the longest meal. This was kept so a swipe never changes
  height under the thumb, and the gate's scroll check needs it; Tarık's eye decides.
- The first lap's badges are light tints with the letter in ink. The kcal number stays full `danger` for
  contrast.
- Over budget with three arcs, the last arc and the first meet at 12 o'clock in the same tone.

## Needs Tarık (on the phone)
- **Task-11:**
  - Lunch opens on its own tab.
  - Removing a food takes − then Remove.
  - A tap never logs.
  - The keyboard comes only from the amount, and typing replaces it.
  - Back works with the keyboard up.
  - A long press ticks a food.
- **Task-12:**
  - The empty track reads as "left".
  - The second lap's red at a glance.
  - The macro marks read at a glance.
  - Swiping between meals feels natural.
  - The trash is easy to find.
  - No scrollbar line at the right edge.
- **Task-13:**
  - The Theme choice is easy to find.
  - The status bar follows it.
  - Light is not darkened by Samsung's dark mode.
  - Dynamic goes dark after sunset (18:44 on 21 Oct).
- Blueprint is 142 lines against doktor's 130. A trim is proposed, not done.

Run closed: all three tasks green on main, eye checks pending (15), phone use check waiting for the cable.

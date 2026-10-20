# Otopilot report — Pantry wave 2 (2026-10-20/21)

Plan: `reports/otopilot-2026-10-20-wave2-plan.md`. One Workflow (ultracode) over Task-02..06: builder
`opus`/`xhigh` per feature, review panel `opus`/`high` (screen on all; spec and code on Task-05 and
Task-06), fixer `opus`/`xhigh`, at most 3 rounds. Then per feature: the Codex `gpt-6.1-sol`/high lens,
integration, gate on main, and the orchestrator's use check on the `terra_nt` emulator.

| Task | Outcome | Main SHA | Gate | Rounds | Notes |
|---|---|---|---|---|---|
| Task-02 Today in full | DONE, eye check pending: 1 | 5e98822, fix b5e174e | `python tests/acceptance.py` ALL PASS | 3 (cap) | Codex: Add/Scan kept the meal from render time; fixed by the orchestrator with a test that goes red without the fix. |
| Task-03 Meal list and gram sheet | DONE, eye check pending: 1 | 472d3ec, fix 8df7252 | ALL PASS | 3 (cap) | Codex: ml drinks capped at 1,000 (1.25 l bottle refused); fixed with a red-able test. |
| Task-04 Scan and new product | DONE, eye check pending: 1 | ebb59d9 | ALL PASS | 3 (cap) | Codex: no findings. Scan hook moved in `tests/acceptance.py` at integration (the valid-read flow now lives in `tests/test_scan.py`, Open Food Facts mocked there). |
| Task-05 Edit, move, delete | DONE, eye check pending: 1 | ff3311e | ALL PASS | 2, round 3 clean | Codex: no findings. |
| Task-06 Sync and settings | DONE, eye check pending: 1 | 591f571, fix 5d7d9fe | ALL PASS | 1, round 2 clean | Codex: one false alarm. The fixer turned the Synced pill green from the reference; reverted to grey (rule: grey + one orange). |

Integration commit a8e3de8: registry lines for entry, sync, settings, newfood; the scan hook move;
`.sec` scoped to `:not(.btn)` in `app/base.css` (four of five builders hit the same collision: the
section margin landed on every secondary button); service worker cache `pantry-v2`. Then 4aeb1db:
text boosting off on every screen (below). The gate on main after every pick and fix: ALL PASS, 74 checks,
the seven test files included. `tests/test_sync.py` ran three times green after its timing fix.

## Use check (orchestrator, `terra_nt`, 360 dp)

Driven through Chrome DevTools on the emulator (`adb forward tcp:9333 localabstract:chrome_devtools_remote`,
Playwright `connect_over_cdp`), starter data only: first launch, Add to breakfast → list → gram sheet →
Add, + on My foods, Today with two meals, Edit entry, Settings, a past day, Scan with a typed code.
Screens: `reports/screens/2026-10-20-wave2/`.

- **Real, missed by every lens and by Codex:** Chrome on Android boosted the Settings token label and
  help text to 24.9 and 21.3 px (rows at 14–16 px). Headless Chromium never boosts, so no gate or lens
  can see it. Second time (Task-00's empty-state paragraph). Fixed for the class: `text-size-adjust: none`
  on `html` in `app/base.css`, Today's own copy removed; after the fix 14 and 12 px.
- **Not checked here:** the largest phone font. This emulator's Chrome is 134, which ignores
  `<meta name="text-scale">`, so the phone font size never reaches the page (root stayed 16 px at
  font scale 2.0). The meta tag was behind a Chrome flag in early 2026 (matuzo.at, adrianroselli.com,
  2026-02); whether Tarık's Chrome honours it is not verified. Large text was checked only in headless
  Chromium (gate at 150 %, screen lenses at 200 %).
- Typed barcode with the keyboard open: field and Look it up stay inside the visual viewport (measured);
  the cover in the screenshot was Chrome's own camera prompt.

## Workflow measurement (Kararlar.md 2026-10-20, check 2026-10-27)

**Time and size.** Workflow 22:30 → 00:27 (117 min wall), 38 agents (5 builders, 20 lens runs, 13 fix
runs), 6.45 M sub-agent tokens, 1,928 tool calls. Codex lens 5 bees in parallel (~25 min). Integration,
fixes and use check 00:28 → 01:10. Wave 1 baseline: 2 builders, 18 and 37 min.

**Quota.** Claude weekly 26 % → 37 % (+11 for 5 features, 2.2/feature; wave 1: +2 for 2 features).
Claude 5-hour: the window reset at 22:39, so this wave's 5-hour figure is 0 → 75 % (Workflow plus this
orchestrator session; wave 1: 7 → 22). Codex 5-hour 5 → 19 %, weekly 1 → 4 %.

**Findings by who found them** (real = reproduced or plainly against the task, reference or a rule):

| Source | Findings | Real, fixed | Real, left | False alarm | Other |
|---|---:|---:|---:|---:|---:|
| Screen lens (5 features) | 28 | 24 (5 of them only at 240 px) | 1, plus part of one fixed finding | 2 | 1 integration (lane gate red until siblings merged) |
| Spec lens (Task-05, 06) | 6 | 4 | 0 | 1 | 1 duplicate of screen |
| Code lens (Task-05, 06) | 2 | 1 | 0 | 0 | 1 duplicate of spec |
| Fix rounds (fixers) | 0 new | – | – | – | 1 wrong fix applied (green pill) |
| Codex lens (5 features) | 3 | 2 | 0 | 1 | 2 "no findings" |
| Orchestrator use check | 1 | 1 | 0 | 0 | caught the wrong fix (green pill) |

Real defects the Workflow lenses found that, as far as this run can tell, Codex and the use check would
have missed:
- **Large-text layout** (4): the page scrolled 17 px sideways at 200 % (Task-02), the bottom button
  wrapped onto three lines (Task-02), the kcal-left number ran over the ring (Task-02), the usual amount
  cut to "100…" for 1000 g so + logged an amount he could not read (Task-03). Codex reads code and does
  not render; the emulator's Chrome cannot show large text (above). These meet the decision's bar on
  their own.
- **Flow and data** (6): Back after Add reopened the sheet, one tap logged twice (Task-03); Back from
  Found re-read the pack and trapped him (Task-04); saving from Found rounded values he never edited
  (Task-04); fractions like "1 1/2 cups" misread so text and totals disagreed (Task-05); a Save undid a
  newer meal change from sync (Task-05, spec and code); a two-decimal macro split saved not adding to
  100 % (Task-06). The use check did not walk these paths. Whether Codex would have found them is **not
  measured**: it reviewed the code after the fixes.

Against the bar ("at least 2 real defects Codex and the use check would miss"): **met** (4 large-text
defects are out of their reach by construction; 6 more flow and data defects are likely). Costs: 2.2
weekly points per feature against 1 in wave 1, and one wrong fix applied by a fixer from a reference
screen against a written rule.

**Missing rule (finding in four features):** the `.sec` / `.btn.sec` collision, now fixed in
`app/base.css`; proposed Blueprint → Constraints line: "a shared class name means one thing; a modifier
never reuses a layout class name". A screen lens followed the reference over the written colour rule
once; `review-calibration.md` now carries that case.

## Left for the next wave (not failures)
- Two quick taps on Delete or Save: the second lands on Today's Add (needs a guard in `app/core.js`'s router).
- The shared `.btn` puts its + alone at the left once the label wraps (`app/base.css`).
- `Pantry.toast` takes text only; design 4 shows the food's drawing in the toast (`app/core.js`).
- `Pantry.icon` has no gear, keyboard, torch or chevron; screens inline their own.
- Each wave-2 screen still carries a local `.btn.sec { margin: 0 }`, unused since the `.sec` fix.
- No shared text-field style in `app/base.css`; scan, newfood and settings each carry one.

## Needs Tarık
1. **Eye checks** (one per task) on the phone at the largest font after deploy: Today and 8 Aug
   against *1* and *7*; list and gram sheet against *2*, *3*, *3b*; Scan, Found, From the label against
   *5*, *6*, *6b* with five real packs; Edit entry against *8*; Settings against *9*, then paste the token.
2. **Large font on your Chrome:** check that the text grows with the phone's font size. If it does not,
   your Chrome ignores `text-scale` and we decide what to do.
3. **Deviations to keep or drop** (builders' proposals, not yet in `design/deviations.md`): first launch
   keeps the bottom bar (Add + Scan) and a "2,200 kcal left today" line in place of "Scan a product";
   strip labels switch to the narrow figure font when a label does not fit; a macro percentage too wide
   for its bar moves under it; strip text sits at the bottom of each tank so the dashed line never crosses it;
   the Synced pill is a grey outline with a check (red stays for Failed); the label form follows 6b's
   order with Salt.

Run closed: all five tasks green on main, eye checks pending: 5.

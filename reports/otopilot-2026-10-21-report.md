# Otopilot report — Pantry wave 3 (2026-10-21)

Plan: `reports/otopilot-2026-10-21-plan.md`. Started unattended at 03:44 by a one-shot schedule after the Claude
5-hour reset (Tarık asleep). One Workflow (`wf_6f611c8b-d3e`) over Task-07..10: builder `opus`/`xhigh` per
feature, review panel `opus`/`high` (screen on 07, 08, 09; spec and code on 07, 08, 10), fixer `opus`/`xhigh`,
at most 3 rounds. Then per feature: worktree gate, the Codex `gpt-6.1-sol`/high lens on the builder's own commit
and on the final one, cherry-pick, gate on main, and the orchestrator's use check (headless Chromium, 360 × 780,
touch, text 1.0, a copy of his history; the phone was not on the cable).

| Task | Outcome | Main SHA | Gate | Rounds | Notes |
|---|---|---|---|---|---|
| Task-07 Screens that move, forgiving router | DONE, eye check pending: 1 | 80d74af, fix 1453533 | ALL PASS | 1, round 2 clean | Codex (final): the gram sheet's copy replayed its rise on the way back to Today; fixed with a test red without it. |
| Task-08 Logging the MyNetDiary way | DONE, eye check pending: 1 | e56758d, fix ae55d40 | ALL PASS | 3 (cap) | Codex (both commits): yesterday's row kept a stale kcal after a synced edit; fixed with a red-able test. |
| Task-09 Today in colour and motion | DONE, eye check pending: 1 | 206f9a4, fix b881683 | ALL PASS | 3 (cap) | Codex (both commits): a day tapped during the change motion kept the previous day's chart; fixed with a red-able test. |
| Task-10 Barcode catalogue | DONE (Tarık judges the matches) | dcfc898, fix 5d70815 | ALL PASS | 2, round 3 clean | Codex (builder commit only): "2X125g" matched "250g x 2 pack", "A2 ... Milk" matched another brand; both still in the final code, fixed with red-able tests. |

Gates: each worktree ALL PASS (152–162 s); on main after each pick ALL PASS (148–185 s); after the four fixes
ALL PASS (187 s). Each fix's test was run against the code before the fix and went red (output kept in the
session scratchpad), then green. Integration commit: service worker cache `pantry-v3`, task status lines and
index ticks, the builders' prototype departures in `design/deviations.md`, Blueprint's catalogue line.

## Use check (orchestrator)
Integrated main served locally, his history loaded: Today, 19 Oct over budget (violet ring, swatches, number,
tanks), 8 Aug, Settings, the meal list, "Same as yesterday's <meal>" on 19 and 20 Oct (1,304 kcal pizza for 20 Oct
dinner), tick three foods by their drawings → "Add 3 to breakfast" → 3 entries and "3 foods added to breakfast"
with Undo, back to Today (963 left), open an entry, Delete then a second finger tap 200 ms later → ends on Today,
one entry deleted. No horizontal scroll, no console or page error. Only long food names end in an ellipsis.
Task-10 run once on the real purchases: 110 Coles and 39 Woolworths receipts, 950 lines, 189 products,
56 catalogue items; 44 % of distinct Woolworths lines matched on their own (38/86), 48 wait for his answer;
the 20 sampled pairs all look right to me. After the fix the real-data catalogue is byte-identical.
Screens of his real log are not committed (personal data); the lenses' screenshots and probes are in the
gitignored `.tmp/wave3-screens/lenses/`, mine in `.tmp/usecheck-w3/shots/`.

## Workflow measurement (Kararlar.md 2026-10-20, check 2026-10-27)
**Time and size.** Workflow 03:51 → 06:40 (169 min), 34 agents (4 builders, 21 lens runs, 9 fix runs),
6.54 M sub-agent tokens, 1,900 tool calls. Codex 8 bees in parallel 06:42 → 06:47. Integration, four fixes and
the use check 06:47 → 07:10. Wave 2: 117 min, 38 agents.
**Quota.** Claude weekly 39 → 50 % (+11 for 4 features, 2.8 per feature; wave 2 2.2). Claude 5-hour 0 → 79 %
(reset 03:39). Codex 5-hour 19 → 32 %, weekly 4 % unchanged.

| Source | Findings | Real, fixed | Real, left | False alarm / rejected |
|---|---:|---:|---:|---:|
| Screen lens (07, 08, 09) | 14 | 13 | 0 | 1 rejected (toast over the list's last row: `app/base.css`, outside the lane) |
| Spec lens (07, 08, 10) | 8 | 7 | 0 | 1 rejected (name the ticked foods in the sheet: a wish) |
| Code lens (07, 08, 10) | 9 | 9 | 0 | 0 |
| Codex on the builder commits | 7 | 4 by me (T09 day switch, T10 ×2, T08 stale kcal) | 1 (T07 scroll after Forward) | 0; 2 already fixed by the panel (T08 "Added" from the meal's contents, T09 early Undo not re-checked) |
| Codex on the final commits | 3 | 1 new by me (T07 sheet replay); 2 were the builder-commit ones | 0 | 0; T10 "no findings" |
| Orchestrator use check | 0 | – | – | 1 of my own (a probe without reload) |

Lens counts include duplicates the fixers merged (07: screen and spec saw the same font jump; 08 and 10: spec
and code twice). "Real" for lens findings is the fixer's word: each fixer reproduced the finding first.
- **What only the Workflow found** (neither Codex on the builder commit nor the use check): the motion copies'
  wrong title font and jump (07); the tick column cutting his food names, a double tap logging twice, ticked
  foods dropped or logged twice, yesterday's meal offered again after a restart, the sheet moving ticked foods
  to another meal at the wrong amounts (08); macro numbers jumping on frame 0, the first tap after a swipe lost,
  a 3 px overflow while dragging, a scroll regression from a fix (09); **identifiers from his real receipts
  copied into the test code** (transaction ids, POS numbers, times, a BIG W line), the pack-size rule untested,
  non-Flybuys savings labelled Flybuys (10). The bar ("at least 2 real defects Codex and the use check would
  miss") is met again.
- **What only Codex found**, that the panel and its fixes left in: 5 real (T09 day switch, T10 two matching
  rules, T07 sheet replay, T08 stale kcal), four of them on the builder commit. Codex on the final commit alone
  would have missed the two T10 rules.
- The round cap closed 08 and 09 with their last fix unreviewed by the panel; Codex on the final commit and the
  use check were the only look at those fixes.

## Left for the next wave (not failures)
- The meal-list toast covers the last row and its + for 4 s and wraps to 3 lines at 360 px (`app/base.css`).
- Opening the gram sheet is `log.js`'s own pushState, not a screen change, so the tap guard does not hold a quick
  second tap onto the sheet's chips or Add (needs a core seam).
- The tap guard holds finger taps only (touch or pen); mouse clicks, keys, `Pantry.go` and popstate always act,
  because the gate's own Playwright clicks land 32–532 ms apart. On the phone every tap is a touch.
- Toast motion (rise 8 px and fade) is not built.
- Browser Forward then Back restores an older Today scroll (Codex, builder commit; Android has no Forward button).
- Task-10: 95 Coles product pages still to capture (bot check), 1 Woolworths search, 48 review answers.

## Needs Tarık
1. **Eye checks on the phone after deploy** (text 1.0): screen motion, back swipe, the grams field's button
   with the keyboard (07); a 4-food dinner in one visit, the + feedback and its vibration, the drawing as the
   tick (08); over budget at a glance in violet, the ring swipe, the strip under the finger, the ~800 ms return
   motion (09).
2. **The over tone**: base `chart-5` violet (warm status tokens read as the orange accent). Keep or change.
3. **Prototype departures** in `design/deviations.md` → wave 3: keep or drop each.
4. **Task-10**: judge the 20 pairs in `.tmp/catalogue-check/report.txt`, answer the 48 lines in
   `.tmp/purchases/woolworths-review.json` (a Stockcode, or "none" for e.g. the paper bag), then the main loop
   runs `--merge` into `Pantry-Data`.

Run closed: tasks consumed, all four green on main, eye checks pending: 3.

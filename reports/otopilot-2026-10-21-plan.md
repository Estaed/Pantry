# Otopilot plan — Pantry wave 3 (2026-10-21)

Written at the end of the wave 2 session for a new session that Tarık starts with `/otopilot`
(his opt-in for the Workflow). He will be away overnight and the phone will not be on the cable.

- **Direction:** orchestrator Claude (the new interactive session, `opus`), builders Claude (same pool),
  Codex `sol`/high as the second-family lens.
- **Engine:** one Workflow (ultracode) over four features: build (`opus`/`xhigh`) → review panel
  (`auditor`, `opus`/`high`) → fix loop (`opus`/`xhigh`, at most 3 rounds), each feature in its own
  detached worktree under `D:/Projects/.lanes/`. Same script shape as wave 2
  (`reports/otopilot-2026-10-20-wave2-report.md`), with the brief rules added on 2026-10-21: a written
  rule in Blueprint or `design/DESIGN.md` outranks the reference screen; the text size target is 1.0;
  the prototype may be departed from for daily comfort (Blueprint → Decisions 2026-10-21).
- **SOURCE:** tasks (Task-07..10). **UNTIL:** done.
- **BASE_SHA:** `5737ba0419f75d6ea6335f2cf421866aa7a094d8` (preflight `onkontrol.py --tasks 07,08,09,10 --features 4`
  OVERALL OK at 03:46; gate ALL PASS on main and in a worktree, 141 s).
- **Started:** 03:51, Workflow `wf_6f611c8b-d3e` (Tarık's "wave 3 basla" plus "workflowlu yapacagiz"); quota at start:
  Claude 5-hour 0 % (reset 03:39), 7-day 38-40 %; Codex 5-hour 19 %, weekly 4 %.
- **Quota when written (02:25):** Claude 5-hour 93 % (resets 03:39), 7-day 40 %; Codex 5-hour 19 %,
  weekly 4 %. Start after the 5-hour reset. Preflight's estimate: ~16 weekly points for 4 features.
- **Wake lock:** `uyanik_tut.py` (Tarık away), PID 29728. **Timebox:** 150 min per feature.
- **After v1 repeats:** none.

| Task | Agent | Model / effort | OWNS | Lenses |
|---|---|---|---|---|
| Task-07 Screens that move, forgiving router, Edit Undo, Settings count | ultracode | opus / xhigh | `app/core.js` (routing), `app/base.css`, `index.html`, `app/entry.js`, `app/settings.js`, `tests/test_shell.py`, `tests/test_entry.py`, `tests/test_sync.py` | screen, spec, code (the router touches every screen; the tap guard can swallow data taps) |
| Task-08 Logging the MyNetDiary way | ultracode | opus / xhigh | `app/log.js`, `app/drawings.js`, `app/newfood.js`, `tests/test_log.py`, `tests/test_scan.py` | screen, spec, code (multi-add and yesterday's meal write entries) |
| Task-09 Today in colour and motion | ultracode | opus / xhigh | `app/today.js`, `tests/test_today.py` | screen |
| Task-10 Barcode catalogue from his purchases | ultracode | opus / xhigh | `tools/catalogue.py`, `tests/test_catalogue.py`, `tests/fixtures/catalogue/` | spec, code (no screen; can break sync if an item is malformed) |

Gate for all: `python tests/acceptance.py` from the repo root. Integration after the Workflow, per
feature: gate in the worktree, Codex lens, cherry-pick, gate on main; then the service worker cache
bump to `pantry-v3`. No registry lines (no new scripts).

**Task-10's input is ready:** `D:/Projects/Pantry/.tmp/purchases/` (gitignored, personal data; its
`README.md` says which file is which). Builders read it from that absolute path; nothing from it enters
the repo. Captured: 42 Woolworths receipts with search and product details; 110 Coles receipts, but only 56 of
151 Coles product pages (the site's bot check stopped the rest; not bypassed). So Task-10's real run will
list the Coles product ids still to capture; that is expected, not a failure.

## Measurement (Kararlar.md 2026-10-20, second wave; decision 2026-10-27)
Wave 2's case rested partly on four large-text defects at text size 2.0, which Tarık then dropped as a
target. This wave measures again, with one change that answers "who would have caught it without the
Workflow":
- Run the Codex lens on each **builder's own commit** (`BASE_SHA..<builder sha>`, the sha is in the
  Workflow result; the object survives the fixer's amend) as well as on the final commit.
- The report lists every finding: who found it (screen, spec, code lens; fix round; Codex on the builder
  commit; Codex on the final commit; orchestrator use check), real or false alarm, and whether Codex on
  the builder commit also had it. Plus wall time, agent count, both windows' deltas
  (`onkontrol.py --record-cost`).
- Log every finding in `D:/TarikOS/.brain/skills/otopilot/references/review-calibration.md`.

## Use check without the phone
The phone use check (`bee-recipes.md` → *Phone use check*) needs the cable; tonight it is not there.
The orchestrator's use check runs in headless Chromium at 360 × 780, text 1.0, with a copy of his history
loaded into a localhost tab (`python tools/import_mynetdiary.py references/mynetdiary-history-2026-10-20.json -o .tmp/phone/doc.json`).
The phone checks (Chrome boosting, the keyboard over a button, vibration, the feel of the motion) stay
open as eye items for Tarık, listed in the report.

## Needs Tarık afterwards
Eye checks on his phone for Task-07, 08, 09; the Task-10 review list (Woolworths lines whose product
match was not clear) and the 20 sampled matches; then `--merge` into `Pantry-Data` (main loop).

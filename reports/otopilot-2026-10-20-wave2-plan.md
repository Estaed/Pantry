# Otopilot plan — Pantry wave 2 (2026-10-20)

- **Direction:** orchestrator Claude (this interactive session, `opus`), builders Claude (same pool),
  Codex `sol`/high as the Phase 3 second-family lens.
- **Seats:** plan and run in the same interactive Opus 5.5 session.
- **Engine:** one Workflow (ultracode) over five features: per feature build (`opus`/`xhigh`) →
  review panel (`auditor`, `opus`/`high`) → fix loop (`opus`/`xhigh`, ≤3 rounds). Tarık's opt-in:
  "tamam basla workflowlu yapacagiz" (2026-10-20, 22:27). Builder, lenses and fixer share the
  feature's worktree.
- **SOURCE:** tasks (Task-02..06). **UNTIL:** done.
- **BASE_SHA:** set after this plan is committed (second preflight); first preflight at a46772e, OVERALL OK.
- **Approval:** Tarık's "tamam basla" before the plan; covers it because it stays inside the written tasks.
- **Baseline gate:** `python tests/acceptance.py` at a46772e: ALL PASS, exit 0.
- **Stop markers:** none (preflight).
- **Quota at preflight (22:27):** Claude 5-hour 32 % (resets 22:39, so the wave's 5-hour delta is
  read from the fresh window), 7-day 26 %; Codex 5-hour 5 %, weekly 1 %. Estimate: preflight
  says ~22.5 weekly points at the highest per-feature cost of the last five waves (fits, 71 left).
  5-hour: five parallel xhigh builders ≈ 50–70 points plus lenses; the 97 % gate may pause agents,
  and the Workflow resumes at the reset by itself (interactive session).
- **Memory:** 16.1 GB free of 32: up to two emulators; the screen lenses use headless Chromium
  (each worktree's own port, the gate binds port 0), the orchestrator does the `terra_nt` look.
- **Wake lock:** `uyanik_tut.py`, PID 11256.
- **Timebox:** 150 min per feature (build + review + fixes).
- **After v1 repeats:** none.
- **Lenses:** screen lens on all five (every task has a screen). Spec and code lenses on Task-06
  (the task asks; sync can lose the log) and Task-05 (delete and move rewrite logged entries).
- **Measurement (Kararlar.md 2026-10-20, check 2026-10-27):** the report lists every finding with
  the lens that found it (screen, spec, code, fix round, Codex, orchestrator use check), real or
  false alarm, and who would have caught a real one without the Workflow; plus wall time, agent
  count, and both windows' deltas. Baseline: wave 1 (2 builders, 18 and 37 min, weekly 23→25,
  5-hour 7→22, 1 real finding by Codex, 0 by the orchestrator's emulator check).

| Task | Wave | Agent | Model / effort | OWNS | GATE | Lenses | Attempts |
|---|---|---|---|---|---|---|---|
| Task-02 Today in full | 2 | ultracode | opus / xhigh | `app/today.js`, `tests/test_today.py` | `python tests/acceptance.py` | screen | 1 (+1 retry) |
| Task-03 Meal list and gram sheet | 2 | ultracode | opus / xhigh | `app/log.js`, `app/drawings.js`, `tests/test_log.py` | `python tests/acceptance.py` | screen | 1 (+1 retry) |
| Task-04 Scan and new product | 2 | ultracode | opus / xhigh | `app/scan.js`, `app/newfood.js`, `tests/test_scan.py`, `tests/fixtures/scan/` | `python tests/acceptance.py` | screen | 1 (+1 retry) |
| Task-05 Edit, move, delete | 2 | ultracode | opus / xhigh | `app/entry.js`, `tests/test_entry.py` | `python tests/acceptance.py` | screen, spec, code | 1 (+1 retry) |
| Task-06 Sync and settings | 2 | ultracode | opus / xhigh | `app/sync.js`, `app/settings.js`, `tests/test_sync.py` | `python tests/acceptance.py` | screen, spec, code | 1 (+1 retry) |

Excluded: none. Integration: each green feature cherry-picked and gated on main in finishing order;
the integrator runs only if two features disagree on a shared surface (styles, navigation).

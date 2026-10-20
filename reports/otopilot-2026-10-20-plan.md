# Otopilot plan — Pantry wave 1 (2026-10-20)

- **Direction:** orchestrator Claude (this interactive session), builders Claude (same pool).
- **Engine:** two parallel single builders (Agent tool, `opus`/`xhigh`), one per task, each in its own
  detached worktree cut from BASE_SHA. Not the Workflow engine: a Workflow needs Tarık's explicit
  opt-in ("workflow"/"ultracode"), which this run does not have. Review panel replaced by the
  orchestrator's gate, diff read and use check (screen check on the app; Task-01 run on the real file).
- **SOURCE:** tasks (Task-00, Task-01). **UNTIL:** done.
- **BASE_SHA:** set after this plan is committed (second preflight); first preflight at ebf4439, OVERALL OK.
- **Approval:** Tarık's "her şey hazır ise başla madem ne gerekiyorsa yap" (2026-10-20), given before
  the plan; covers this plan because it stays inside the written tasks.
- **Baseline gate:** none at BASE_SHA (Task-00 writes `tests/acceptance.py`); Task-01's gate is its own file.
- **Stop markers:** none (preflight).
- **Quota at preflight:** Claude 5-hour 7 %, 7-day 23 %. Estimate: two Opus/xhigh builders ≈ 1–1.5 h
  each ≈ 20–30 points of the 5-hour window (≈ 10/agent-hour, `chef`), weekly a few points. Not measured for this project.
- **Memory:** 13.4 GB free of 32: one emulator at a time for the eye check, after the builders.
- **Wake lock:** not taken; Tarık is present at the PC.
- **Timebox:** 120 min per builder.
- **After v1 repeats:** none (nothing tried before).

| Task | Wave | Agent | Model / effort | OWNS | GATE | Attempts |
|---|---|---|---|---|---|---|
| Task-00 Thinnest path | 1 | ultracode → single builder | opus / xhigh | `index.html`, `app/`, `tokens.css`, `fonts/`, `sw.js`, `manifest.json`, `icons/`, `tests/acceptance.py`, `tests/fixtures/app/`, `.gitignore` | `python tests/acceptance.py` | 1 (+1 retry) |
| Task-01 Import history | 1 | ultracode → single builder | opus / xhigh | `tools/import_mynetdiary.py`, `tests/test_import.py` | `python tests/test_import.py` | 1 (+1 retry) |

Excluded: none. Integration order: Task-01 first (no shared files), then Task-00; after both, the
full gate `python tests/acceptance.py` on main must also run `tests/test_import.py`.

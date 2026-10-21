# Otopilot plan — Pantry wave 4 (2026-10-21)

From Tarık's first day on the phone with wave 3. He chose the Workflow ("Workflow dalgası", 2026-10-21) and is
present; his phone is on the cable (installed app in Samsung Internet).

- **Direction:** orchestrator Claude (this interactive session, `opus`), builders Claude, Codex `sol`/high as the
  second-family lens on each builder's commit and on the final one.
- **Engine:** one Workflow (ultracode) over three features: build (`opus`/`xhigh`) → review panel (`auditor`,
  `opus`/`high`) → fix (`opus`/`xhigh`, at most 3 rounds), each in its own detached worktree under
  `D:/Projects/.lanes/`. Same script as wave 3 (`wf_6f611c8b-d3e`).
- **SOURCE:** tasks (Task-11..13). **UNTIL:** done. **Timebox:** 150 min per feature.
- **Seam laid before the wave (main loop):** `Pantry.removeEntry(id)` in `app/core.js`, used by Edit entry and by
  Task-11 and Task-12 for taking an entry out (Blueprint → Screens and seams).
- **Acceptance attacked** by a fresh `auditor` reader before the wave; its findings were folded into the tasks
  (gate hooks named, removal through the seam, red only past target grams, theme-color media, sunset table).
- **After v1 repeats:** none.

| Task | Agent | Model / effort | OWNS | Lenses |
|---|---|---|---|---|
| Task-11 Meal list opens on that meal, tap opens, + logs | ultracode | opus / xhigh | `app/log.js`, `tests/test_log.py` | screen, spec, code (removal and multi-add write entries) |
| Task-12 Today at a glance | ultracode | opus / xhigh | `app/today.js`, `app/base.css` (page scrollbar only), `tests/test_today.py` | screen, spec, code (removal writes entries) |
| Task-13 Theme in Settings | ultracode | opus / xhigh | `app/core.js` (theme only), `app/settings.js`, `index.html`, `manifest.json` (theme colours), `tests/test_theme.py` | screen, spec |

Gate for all: `python tests/acceptance.py` from the repo root. Integration per feature: gate in the worktree, Codex
lens, cherry-pick, gate on main; gate-hook moves the builders name (acceptance.py, test_shell.py) at integration; then
the service worker cache bump to `pantry-v6`, `design/deviations.md` (over tone now `danger`).

## Use check on the phone
Integrated main served locally, opened in Samsung Internet on his phone (`adb reverse`), driven through
`localabstract:Terrace_devtools_remote` and `adb shell input`, with a copy of his history in the localhost origin
(his installed app's log is never touched). Measured: the back key with the keyboard up, the meal pages' swipe beside
the ring and strip, the removal path, the theme and status bar.

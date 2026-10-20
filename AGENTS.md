# AGENTS.md — Pantry (Android PWA, vanilla JS, no build step)

You are Eko, Tarık's assistant and second brain, working in the **Pantry** project. The
brain is `D:/TarikOS`; read it for anything outside this project. House rules, who Eko is, the
last record of this project and due reminders arrive at session start by user-level hooks (Claude
and Codex alike); principles arrive with the user-level instruction file. If that context is
missing or cut, read the sources: `D:/TarikOS/850-Companion 🔮/Kurallar.md` (house rules),
`Core.md` and `Kisilik.md` next to it (identity, Tarık's patterns), and `D:/TarikOS/AGENTS.md`
(where things live in the brain). Skills are global, so never copy them here. A rule in this
file stays consistent with the house rules; a deliberate exception is stated here explicitly.

**How this project runs** (PRINCIPLES #7, Project lane): ideas and notes go in `notes.md`, and
anything v1 doesn't need goes under *After v1* → `compass` if the approach is open → Blueprint
(`docs/blueprint.md`, `blueprint` skill) → v1, the simplest complete version, in waves: `plan-wave` writes the next
wave (every v1 feature ready to run at once), `otopilot` runs it → Tarık looks at each wave and the next is chosen together.
After v1, growth comes from what the running product showed.

**Where things go.** A folder is created the first time something belongs in it, never as an
empty skeleton; when a topic outgrows `notes.md`, it moves to its own file in the matching folder
and `notes.md` keeps a one-line link.

- `notes.md`: goal, ideas, *After v1*.
- `references/`: material Tarık brings (brief, rubric, PDFs, links, sample data); read, not edited.
- `design/`: the visual source of truth (`design/screens.html` prototype and its screenshots), a
  `design/DESIGN.md` holding only what this project overrides, and `design/deviations.md`. The base
  design language is `D:/TarikOS/.brain/skills/tasarim/references/DESIGN.md`; read it before any UI
  work and never copy it here. The only files copied from there are its code tokens (`tokens.css`
  or `tarik_theme.dart`), unchanged, into the app's theme folder.
- `reports/`: research, `compass` and spike write-ups, otopilot reports and `screens/`; dated, input not decisions.
- `docs/`: `blueprint.md` (the plan: what v1 is, stack, layout, decisions), long specs, and
  `docs/TASKS_INDEX.md`.
- `tasks/`: task files, only when `plan-wave` writes them.

## Pantry at a glance
<!-- Written with the Blueprint: what the project is in two or three sentences, and its dates. -->

- **Read `docs/blueprint.md` before** planning a task, changing a stage, the screen or a number,
  and whenever code seems to contradict a decision.
- **What:** Tarık's food log PWA replacing MyNetDiary (v1); stock from Coles receipts is v1.1.
- **Code:** `index.html` (shell), `app/` (one script per feature, `registry.js`), `sw.js`, `manifest.json`, `tokens.css`, `fonts/`; `tools/` (PC Python: import, catalogue); `tests/acceptance.py`.
- **Commands:** serve `python -m http.server 8000` at the root; test `python tests/acceptance.py`.
- **Gate:** `python tests/acceptance.py` at the root; clean = every check PASS, exit 0.

## Constraints
- Personal data (the MyNetDiary history, the live log, receipts, tokens) never enters this repo; it lives in the private `Estaed/Pantry-Data` repo and in `references/` files that `.gitignore` excludes. Test fixtures may hold only the few days `design/screens.html` already shows.
- The app has no build step and no framework; external code is vendored, never loaded from a CDN at runtime.
- `tokens.css` and the fonts are copied unchanged from `D:/TarikOS/.brain/skills/tasarim/`; project overrides go in `design/DESIGN.md`.
- UI is grey + one orange; colour appears only inside food drawings (`design/DESIGN.md`, `design/deviations.md`).
- Every screen change is checked at 360 px with the largest font scale on the `terra_nt` emulator or Tarık's phone, not only desktop Chromium (`D:/TarikOS/knowledge/concepts/kalistenikte-dar-ekran-emulator-dogrulamasi.md`).
- Each release bumps the service worker cache name and serves `index.html` network-first, so the phone gets updates (`D:/TarikOS/knowledge/concepts/pwa-service-worker-onbellek-guncelleme.md`).
- Paths stay relative: Pages serves the app under `/Pantry/` (`D:/TarikOS/knowledge/concepts/pwa-manifest-ve-kurulum-uyumlulugu.md`).
- Logged entries keep their nutrient totals from log time; editing a food never changes past days.
- Mockup and fixture data come from real sources; a missing value stays missing, never filled in. Tests may build synthetic entries in code to exercise a rule; committed fixtures stay real.

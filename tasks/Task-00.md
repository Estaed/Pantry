# Task-00: Thinnest path — install, log a food, see kcal left, scan a barcode
**Status: DONE** — verified 2026-10-20, eye check pending: 2
> **Execution:** agent `ultracode`
> *Why:* every later feature plugs into this shell, its data and its gate, and the camera scan is v1's riskiest assumption.

**Lane**
- OWNS: `index.html`, `app/`, `tokens.css`, `fonts/`, `sw.js`, `manifest.json`, `icons/`, `tests/acceptance.py`, `tests/fixtures/app/`, `.gitignore`
- MUST NOT TOUCH: `tools/`, `tests/test_import.py`, `tests/fixtures/mynetdiary-slice.json` (Task-01), `design/`, `docs/`, `references/`, `notes.md`
- GATE: `python tests/acceptance.py` (from repo root)
- DEPENDS ON: none

## Goal
Tarık opens Pantry on his Android phone (Chrome, GitHub Pages under `/Pantry/`), installs it to
the home screen, and it opens offline. Today shows today's date in Darwin and the kcal left of his
2,200 budget. He picks a food from a starter list, chooses grams, saves, and kcal left drops by
exactly that food's kcal; after a reload the entry is still there. A scan button opens the rear
camera and shows the EAN-13 it read, so he can try his real packs. Plain, but already in Tarik
Base v6: canvas, Archivo title, Manrope text, the one orange number. The full Today look (ring,
corners, strips) is a wave-2 task.

The shell is built so wave-2 features never edit each other or the shell: each feature is one
script under `app/`, registered by one appended line in `app/registry.js`; `app/core.js` alone
reads and writes storage and gives features a documented API (read the document, change it,
subscribe to changes, a dirty flag the sync feature will use). The gate serves the app under a
subpath, drives it at 360 px with large text in Darwin time, and runs every `tests/test_*.py`.

## Why
Lays the seams (registry, core API, offline caching that needs no per-feature edit, the gate) so
wave 2 runs five features at once, and puts the scanner in Tarık's hands early: if Chrome's
built-in `BarcodeDetector` fails on his phone, the fallback is chosen before the scan feature is
built.

## Acceptance
- [x] `python tests/acceptance.py` exits 0 from the repo root, printing PASS per check, and exits non-zero on any FAIL.
- [x] The gate serves the repo under `/Pantry/`, loads it at 360 × 780 with text at 150 %: no console errors, no horizontal scroll; it proves the zoom works (the title's rendered height at 150 % is at least 1.4× its height at 100 %).
- [x] The gate runs with timezone `Australia/Darwin` and the clock at 07:00 local; a food logged then is stored under that local date, not the UTC date.
- [x] Logging a starter food at 350 g lowers kcal left by that food's kcal for 350 g (to the kcal); the entry survives a reload; after the test changes that food's `per100.kcal`, kcal left does not change.
- [x] After one online load, a reload with the network blocked shows Today with the saved entry, and `document.fonts.check('16px Manrope')` and `document.fonts.check('700 40px Archivo')` are true.
- [x] A throwaway feature script listed in `app/registry.js` shows up online and offline with no edit to `index.html`, `app/core.js` or `sw.js`.
- [x] No file in `app/` other than `core.js` touches `localStorage`; `core.js` opens with a header comment documenting its API.
- [x] The manifest's `start_url`, `scope` and its 192 and 512 icons resolve with 200 under `/Pantry/`.
- [x] Every `tests/test_*.py` is run as `python <file>` from the repo root and its exit code is the verdict; a fixture test that exits 1 turns the gate red (shown once in the gate, then not left in the suite).
- [x] Scan: with `BarcodeDetector` missing, and with it present but without `ean_13` in `getSupportedFormats()`, the screen says which in plain words; leaving the scan view stops every camera track (`readyState === 'ended'`). Tests inject a fake detector and camera.
- [x] `.gitignore` ignores `.tmp/` and the personal files in `references/` (`mynetdiary-history-*.json`, `*.mp4`); `git check-ignore .tmp/x.json` exits 0.
- [ ] (eye) On the `terra_nt` emulator at 360 px and the largest font: Today, the starter list and the gram step fit without sideways scrolling and use the tokens, against `design/screens.html` (colours, type, spacing; not the full layout yet).
- [ ] (eye, after the main loop deploys to Pages) Tarık scans five real packs from his kitchen; each EAN-13 is read correctly within about two seconds. The main loop records the result in `notes.md`.

## Out of scope
- The ring, corners, macro strip, day strip and food drawings (wave 2: Today).
- Sync, import, catalogue lookup, Open Food Facts, past days, settings screen.
- Deploying: the main loop pushes and Pages serves `main`.

Fixed:
- `tokens.css` and the fonts are copied unchanged from `D:/TarikOS/.brain/skills/tasarim/references/tokens.css` and `D:/TarikOS/.brain/skills/tasarim/assets/fonts/` (Archivo with `archivo.css`, Manrope). `tokens.css` has no `@font-face`; declare Manrope as the tasarim `preview.html` does.
- localStorage key `pantry.v1` holds one JSON document `{ "version": 1, "foods": [], "entries": [], "settings": {} }`. Sync config and the token never go in it; they live under their own key `pantry.sync` (Calisthenics-App keeps them apart the same way).
- food: `{ id, name, brand?, barcode?, per100?: { kcal, protein, carbs, fat, sugars?, satFat?, salt?, fibre?, ... }, servings: [{ label, grams|null, kcal? }], source }`, source one of `mynetdiary | coles | woolworths | off | label`. `per100` is absent for foods logged only by servings (tablets, ml drinks, restaurant meals); their servings carry `kcal` and their entries carry totals.
- entry: `{ id, date: "YYYY-MM-DD" (Darwin local), meal: "breakfast|lunch|dinner|snacks", foodId, amount: "350 g", grams: number|null, totals: { kcal, protein?, carbs?, fat?, ... } }`. Totals are fixed at log time; a nutrient that is unknown is absent, never 0.
- settings: `{ targets: { kcal: 2200, proteinPct: 20, carbsPct: 45, fatPct: 35, salt: 5.8 } }`.
- Starter foods (product values as MyNetDiary has them, per 100 g; the first five of `DINNER` in `design/screens.html`), seeded only into an empty document, replaced by an import. Ids are their MyNetDiary `foodId`:
  - `v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao=` Chicken Breast Raw: kcal 108.1, protein 20.33, carbs 0, fat 3.0, sugars 0, satFat 0.54, salt 0.43, fibre 0; usual 350 g.
  - `v1.nWY1wUENSPOyu4Pt9ojJcGQKyXNwC+i8TqtlZmsYpNIdi2IepiE5wgTOo1g=` Classic Tzatziki Dip, Coles: kcal 90.0, protein 4.75, carbs 12.0, fat 3.25, sugars 7.25, satFat 2.5, salt 0.8, fibre 2.5; usual 125 g.
  - `v1.d6DR1H5K+qWQUAWwc3j8qf3M2Hc3hKdn3YcTs5+OuZghSHwXFrx2D3cMe9c=` Indian Basmati Rice, Coles: kcal 360.0, protein 8.4, carbs 80.0, fat 0.6, sugars 0, satFat 0.2, salt 0, fibre 2.0; usual 100 g.
  - `v1.aKW*42YP1j2TAk0bfGM*EM*zCxIsoQLSdlyVsH9Lzqk1scOD*H2WCHxRDw==` Original Spreadable Butter, Western Star: kcal 616.6, protein 20.0, carbs 20.0, fat 60.0, sugars 20.0, satFat 28.0, salt 1.2 (fibre unknown, absent); usual 5 g.
  - `v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg=` Washed White Potato, Woolworths: kcal 59.0, protein 2.27, carbs 14.8, fat 0.13, sugars 0.67, satFat 0.13, salt 0.01, fibre 1.87; usual 500 g.
- Display name = the short name (MyNetDiary `cleanName`), brand on the second line; long names end with an ellipsis, never wrap the row.
- Lessons: verify at 360 px with large text, desktop alone missed overflow before (`D:/TarikOS/knowledge/concepts/kalistenikte-dar-ekran-emulator-dogrulamasi.md`); bump the cache name per release and fetch `index.html` network-first (`D:/TarikOS/knowledge/concepts/pwa-service-worker-onbellek-guncelleme.md`); relative paths only, Pages serves `/Pantry/` (`D:/TarikOS/knowledge/concepts/pwa-manifest-ve-kurulum-uyumlulugu.md`); the camera needs an HTTPS origin, `file://` is refused on Android (`D:/TarikOS/knowledge/concepts/cevrimdisi-web-uygulamasinda-qr-ve-origin-siniri.md`).

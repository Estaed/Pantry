# Task-00: Thinnest path — install, log a food, see kcal left, scan a barcode
> **Execution:** agent `ultracode`
> *Why:* every later feature plugs into this shell, its data and its gate, and the camera scan is v1's riskiest assumption.

**Lane**
- OWNS: `index.html`, `app/`, `tokens.css`, `fonts/`, `sw.js`, `manifest.json`, `icons/`, `tests/acceptance.py`, `tests/fixtures/app/`, `.gitignore`
- MUST NOT TOUCH: `tools/` (Task-01), `design/`, `docs/`, `references/`, `notes.md`
- GATE: `python tests/acceptance.py` (from repo root)
- DEPENDS ON: none

## Goal
Tarık opens Pantry on his Android phone (Chrome, from GitHub Pages under `/Pantry/`), installs it to
the home screen, and it opens offline. Today shows today's date and the kcal left of his 2,200
budget. He picks a food from a starter list (the five foods `design/screens.html` shows for dinner, with
their real per 100 g values from the history), chooses
grams, saves, and kcal left drops by exactly that food's kcal; after a reload the entry is still
there. A scan button opens the rear camera and shows the EAN-13 it read, so he can try his real
packs. Plain, but already in Tarik Base v6: canvas, Archivo title, Manrope text, the one orange
number. The full Today look (ring, corners, strips) is a later task.

The shell is built so later features never edit each other: each feature is one script under
`app/` registered by one line in `app/registry.js`; `app/core.js` owns the data document and
exposes reading and writing it to the feature scripts. The gate serves the app under a subpath,
drives it at 360 px with a large font scale, and also runs every `tests/test_*.py` it finds.

## Why
Lays the seams (registry, core data API, gate) so wave 2 runs five features at once, and puts the
scanner in Tarık's hands early: if Chrome's built-in `BarcodeDetector` fails on his phone, the
fallback is chosen before the scan feature is built.

## Acceptance
- [ ] `python tests/acceptance.py` exits 0 from the repo root, printing PASS per check, and exits non-zero on any FAIL.
- [ ] The gate serves the repo under `/Pantry/` and loads it at 360 × 780 with text zoom at least 150 %: no console errors, no horizontal scroll.
- [ ] Logging a fixture food at 350 g lowers kcal left by that food's kcal for 350 g (to the kcal), and the entry survives a reload.
- [ ] After one online load, a reload with the network blocked still shows Today with the saved entry (service worker).
- [ ] The data document in localStorage has the shape fixed below; a test reads it back and checks the entry's stored nutrient totals.
- [ ] A second feature script added under `app/` and listed in `app/registry.js` shows up without any edit to `index.html` or `app/core.js` (the gate checks this with a throwaway test feature it adds at runtime or a fixture script).
- [ ] The gate runs every `tests/test_*.py` and fails when one of them fails.
- [ ] When `BarcodeDetector` is missing, the scan button says so in plain words instead of failing silently (tests inject both cases).
- [ ] (eye) On the `terra_nt` emulator or Tarık's phone at 360 px and the largest font: Today, the food list and the gram step fit without sideways scrolling and use the tokens, against `design/screens.html` (colours, type, spacing; not the full layout yet).
- [ ] (eye) Tarık scans five real packs from his kitchen; each EAN-13 is read correctly within about two seconds. Result recorded in `notes.md` by the main loop.

## Out of scope
- The ring, corners, macro strip, day strip and food drawings (wave 2: Today).
- Sync, import, catalogue lookup, Open Food Facts, past days, settings.
- Deploying: the main loop creates the repo and turns on Pages.

Fixed:
- `tokens.css` and the fonts are copied unchanged from `D:/TarikOS/.brain/skills/tasarim/references/tokens.css` and `.../assets/fonts/` (Archivo, Manrope).
- localStorage key `pantry.v1` holds one JSON document: `{ "version": 1, "foods": [...], "entries": [...], "settings": {...} }`.
- food: `{ id, name, brand?, barcode?, per100: { kcal, protein, carbs, fat, sugars?, satFat?, salt?, fibre?, ... }, servings: [{ label, grams }], source }` with source one of `mynetdiary | coles | woolworths | off | label`.
- entry: `{ id, date: "YYYY-MM-DD", meal: "breakfast|lunch|dinner|snacks", foodId, amount: "350 g", grams: number|null, totals: { kcal, protein, carbs, fat, ... } }`; totals are fixed at log time.
- settings: `{ targets: { kcal: 2200, proteinPct: 20, carbsPct: 45, fatPct: 35, salt: 5.8 } }`.
- Lessons: verify at 360 px with large text, desktop alone missed overflow before (`D:/TarikOS/knowledge/concepts/kalistenikte-dar-ekran-emulator-dogrulamasi.md`); bump the cache name per release and fetch `index.html` network-first (`D:/TarikOS/knowledge/concepts/pwa-service-worker-onbellek-guncelleme.md`); relative paths only, Pages serves `/Pantry/` (`D:/TarikOS/knowledge/concepts/pwa-manifest-ve-kurulum-uyumlulugu.md`); the camera needs an HTTPS origin, `file://` is refused on Android (`D:/TarikOS/knowledge/concepts/cevrimdisi-web-uygulamasinda-qr-ve-origin-siniri.md`).

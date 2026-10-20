# Blueprint — Pantry

The plan v1 is built from. Binding until changed on purpose (PRINCIPLES #5); the `blueprint`
skill writes and amends it. Constraints live in `AGENTS.md`, because every session must see them.

## What v1 is
Tarık's own food log on his Android phone, replacing MyNetDiary for the way he uses it: one Today
screen (day strip, kcal left, four meals in the corners, macro strip, what he ate), a meal's
frequent foods with their usual grams, a gram sheet, barcode scan for new products, past days and
editing. English UI. His 464 days of MyNetDiary history come in, so it starts full. For Tarık only.

Done when (Eko's proposal, 2026-10-20, Tarık did not object):
- a full week logged only in Pantry, MyNetDiary not opened;
- a frequent food is logged in ≤ 3 taps (Today → corner or Add → **+**);
- any past day opens from the day strip with its kcal and overage right;
- (eye) on the phone the screens match `design/screens.html`.

## Not in v1
Stock (bought − logged) and Hermes' weekly Discord list (v1.1, after the spike below); label photo
read by a model (maybe v1.3); merge with Calisthenics-App (v1.2); body weight, water, steps;
trolley or checkout; Woolworths receipts; desktop layout. Full list: `notes.md` → *After v1*.

## Riskiest assumption
- **v1:** the phone's camera reads EAN-13 through Chrome's built-in `BarcodeDetector` fast enough
  to beat typing. Untested on Tarık's phone; Task-00 ships a scan page and he tries five real
  packs. If it fails, a vendored ZXing build is the fallback (decided then, not now).
- **v1.1 (stock):** bought − logged is close enough to trust. Spike before any stock code: 2–3 real
  weeks of Coles receipts against the log, compared with what is actually in the kitchen.

## Stack
No framework and no build step, the way Calisthenics-App works, so the v1.2 merge is one style;
unlike its single file, features live in their own scripts (Layout).

| Piece | Version | Why |
|---|---|---|
| Vanilla JS, HTML, CSS | — | one `index.html` app; Tarık asked for light ("hafif") |
| `tokens.css`, Archivo, Manrope | Tarik Base v6, copied unchanged | design language; fonts local so it works offline |
| Service worker + manifest | — | installable PWA, offline; Pages serves HTTPS for the camera |
| `BarcodeDetector` (Chrome Android) | built in | EAN-13 scan, no library |
| GitHub Contents API | REST, fine-grained token | sync to a private data repo, ported from Calisthenics-App |
| Open Food Facts API | v2, CORS open | live fallback when a barcode is not in the catalogue |
| Python + Playwright | 3.13.5 / 1.62.0 (this machine) | PC tools and the acceptance test |

Rejected: native Kotlin or Flutter (an APK to build and sideload, nothing v1 needs); a framework
or bundler (a build step for one screen); IndexedDB (localStorage holds years of entries:
~2,700 entries ≈ 0.3 MB of the 5 MB).

## Data
- **foods:** id, name, brand, barcode?, per 100 g (kcal, protein, carbs, fat, sugars, sat fat,
  salt, fibre, the rest when known; absent for foods logged only by servings), servings
  (label → grams or kcal), source (`mynetdiary`, `coles`,
  `woolworths`, `off`, `label`).
- **entries:** id, date (Darwin local), meal (breakfast, lunch, dinner, snacks), foodId, amount as typed, grams,
  and the nutrient totals at log time, so editing a food never rewrites history.
- **settings:** targets (2,200 kcal; protein 20 %, carbs 45 %, fat 35 %; salt 5.8 g). The sync
  token stays on the phone under its own key, never in the synced document.
- Frequent foods per meal and their usual grams are derived from entries, not stored.
- One JSON document, `pantry-data.json`, in the private repo `Estaed/Pantry-Data`; the phone keeps
  a copy in localStorage and works offline.

## Barcode catalogue
Built on the PC, not by the phone (the stores block cross-site calls): Coles product pages carry
`gtin` and a per 100 g table in `__NEXT_DATA__`; Woolworths `apis/ui/product/detail/{stockcode}`
returns `Barcode` and per 100 g values (checked 2026-10-20). v1 builds it once from the products
in Tarık's Coles in-store receipts, from a logged-in browser session, into the data repo. Lookup
order on scan: his foods → catalogue → Open Food Facts → typed from the label once.

## Layout
- `index.html`: a thin shell; `app/core.js` (data, state, routing), one `app/<feature>.js` per
  feature (today, log, scan, history, sync, settings), listed once each in the append-only
  `app/registry.js`, so features are built in parallel without editing each other. `tokens.css`,
  `fonts/`, `sw.js`, `manifest.json`, icons at the root, served by GitHub Pages from `main`.
- `tools/`: PC-side Python: `import_mynetdiary.py` (history JSON → `pantry-data.json`),
  `catalogue.py` (store product data → catalogue). Personal data never enters this repo.
- `tests/`: `acceptance.py` (Playwright, mocked GitHub API, 360 px viewport, served under
  `/Pantry/`) also runs every `tests/test_*.py`; fixtures are a few real days already shown in
  `design/screens.html`.
- `design/`: source of truth (`screens.html`, `DESIGN.md`, `deviations.md`); `references/`: inputs.

## Screens and seams (wave 2 builds against these)
- Routes (`Pantry.go(name, ...args)`): `today [date]` Today or a past day (`app/today.js`);
  `add meal [date]` the meal's food list and `food id meal [date]` the gram sheet (`app/log.js`);
  `scan meal [date]` scan and new product (`app/scan.js`); `entry id` edit, move, delete
  (`app/entry.js`); `newfood code meal [date]` Found or From the label (`app/newfood.js`); `settings` targets,
  sync, data (`app/settings.js`, `app/sync.js`). A missing `date` is today; a missing `meal` is
  `Pantry.mealNow()`; callers pass both when they know them. Saving on a screen opened for a day
  returns with `Pantry.go('today', date)`, never `back()`.
- Shared helpers in `app/core.js` (header): `mealNow`, `usualAmounts` (the one usual-amount rule),
  `toast` (outside the screen, survives navigation), `changes`/`markClean(upTo)`, `subscribe`'s
  `prev`, `setSyncState` announcing `'sync'`. Feature classes carry the feature's prefix (`today-`,
  `log-`, `scan-`, `newfood-`, `entry-`, `settings-`); shared ones live in `app/base.css`.
- Sync pushes no sooner than 10 s after the last change, so an Undo inside a 4 s toast never meets
  a pushed tombstone; Undo removes its own `removed` line and restores the entry at the same index.
- Deleting an entry or a food removes it and appends `{ id, at }` (ISO time) to `doc.removed`
  (created when absent), so sync never brings it back. Editing an entry's grams scales its own
  totals by new ÷ old grams; it never recomputes them from the food.
- `doc.catalogue`: `[{ barcode, name, brand?, size?, store: "coles"|"woolworths", per100 }]`,
  written by the PC catalogue tool through the data repo, read by scan. Absent until wave 3.
- `window.PantryDrawing(food, size)` (`app/drawings.js`) draws a food; `PantryDrawing.named(key)`.
- A feature's tests live in its own `tests/test_<feature>.py`, reuse the helpers in
  `tests/acceptance.py` (import it, never edit it) and run in the gate. Tests reach their screen by
  route (`location.hash` or `Pantry.go`), not through another feature's DOM; only Today's tests drive
  Today. They may build synthetic entries in code to exercise a rule. Read `window.PantryDrawing` at
  render time (it loads after the features). A new script needs one
  line in `app/registry.js`, which the orchestrator appends at integration. A redrawn screen keeps
  the gate hooks listed at the top of `tests/acceptance.py`, or the task names the hook change and
  the orchestrator moves the old-look assertion at integration.
- Sync reads `pantry-data.json` above 1 MB only with the raw media type (GitHub Contents API, checked
  2026-10-20); the imported document is 1,067 KB (1,092,625 bytes) since totals are kept unrounded.
- The orchestrator appends registry lines and bumps the service worker cache name at integration.

## Verification
- Gate: `python tests/acceptance.py` from the repo root; clean = every check PASS, exit 0. Written
  and first run in Task-00.
- Eye: Tarık on his phone (or the `terra_nt` Android emulator at 360 px with the largest font
  scale), against `design/screens.html`; intended breaks go to `design/deviations.md`.

## Decisions (2026-10-20, Tarık)
- v1 is the food log; stock and Discord are v1.1. Rejected: stock in v1 (untested assumption).
- Data on the phone, synced to private `Pantry-Data`. Rejected: phone only (one lost phone loses all).
- Import all 464 MyNetDiary days. Rejected: food list only (past days would be empty).
- New product: his foods → Coles/Woolworths catalogue → Open Food Facts → label typed once.
  Rejected: label photo read by a model (an API key in a public client; maybe v1.3).
- App repo `Pantry` private with Pages, public when open-sourced; at v1.2 Calisthenics moves in.
- UI English; design as picked in `design/DESIGN.md` (corners, G3 ring, B1 strip, W3 waves, style C).

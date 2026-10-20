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
No framework and no build step, the way Calisthenics-App works, so the v1.2 merge is one style.

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
  salt, fibre, the rest when known), servings (label → grams), source (`mynetdiary`, `coles`,
  `woolworths`, `off`, `label`).
- **entries:** id, date, meal (breakfast, lunch, dinner, snacks), foodId, amount as typed, grams,
  and the nutrient totals at log time, so editing a food never rewrites history.
- **settings:** targets (2,200 kcal; protein 20 %, carbs 45 %, fat 35 %; salt 5.8 g), sync config.
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
- `index.html`: the app (screens, state, sync, scanner); `tokens.css`, `fonts/`, `sw.js`,
  `manifest.json`, icons at the root, served by GitHub Pages from `main`.
- `tools/`: PC-side Python: `import_mynetdiary.py` (history JSON → `pantry-data.json`),
  `catalogue.py` (store product data → catalogue). Personal data never enters this repo.
- `tests/`: `acceptance.py` (Playwright, mocked GitHub API, 360 px viewport), fixtures from a small
  slice of real days with names kept.
- `design/`: source of truth (`screens.html`, `DESIGN.md`, `deviations.md`); `references/`: inputs.

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

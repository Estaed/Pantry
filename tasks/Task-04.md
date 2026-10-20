# Task-04: Scan and new product — barcode to a food he can log
> **Execution:** agent `ultracode`
> *Why:* a new product must become a loggable food in under a minute, without typing a label when the data exists.

**Lane**
- OWNS: `app/scan.js`, `app/newfood.js`, `tests/test_scan.py`, `tests/fixtures/scan/`
- MUST NOT TOUCH: `app/core.js`, `app/registry.js`, `app/base.css`, `tests/acceptance.py`, `index.html`, `sw.js`, and every other `app/*.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_scan.py`)
- DEPENDS ON: none

## Goal
Tarık taps the scan button, points the camera at a pack (`design/screens.html` → *5. Scan*), and Pantry
looks the code up in order: his own foods (a food with that barcode opens its gram sheet directly),
then the store catalogue in the document (`doc.catalogue`, Coles and Woolworths products with per
100 g values), then Open Food Facts. A hit shows *6. Found* (the product's name, store tag, per 100 g
energy, protein, carbs, sugars, fat, saturated fat and pack size, editable once) and "Save and choose
grams" saves it as his food with that barcode and opens its gram sheet for the meal and day he came
from. A miss shows *6b. From the label*: name, brand, pack size, per 100 g energy (kJ or kcal, kJ
turned into kcal ÷ 4.184), protein, carbs, fat, optional sugars, salt, fibre; saving makes a `label`
food. "Type the barcode" lets him enter the digits when the camera fails.

Decided (2026-10-20, planner): none of his 115 imported foods has a barcode yet, so Found also offers
"This is my …" with his foods that match the product's name (search by words): picking one attaches
the barcode to that food instead of making a new one, so its history and usual grams stay. Found and
From the label are the route `newfood code meal [date]` in `app/newfood.js`, so the phone's back
gesture returns to Scan. The scan screen keeps a button named "Back". Offline, the lookup skips
Open Food Facts and says so.

Open Food Facts: `GET https://world.openfoodfacts.org/api/v2/product/<code>.json?fields=product_name,brands,quantity,nutriments`
answers with `Access-Control-Allow-Origin: *` (checked 2026-10-20; the Willow Farm tzatziki
9312726072232 is there). It reports many unknown micronutrients as 0, so only these are taken:
`energy-kcal_100g` (else `energy-kj_100g` ÷ 4.184), `proteins_100g`, `carbohydrates_100g`, `sugars_100g`,
`fat_100g`, `saturated-fat_100g`, `salt_100g`, `fiber_100g`; a missing one stays absent, a 0 in one of
these is kept (0 g carbs is real), every other field is ignored.

## Why
Retires the second half of v1's riskiest assumption (scan must beat typing) and replaces Task-00's
probe with the real flow.

## Acceptance
- [ ] With a fake camera and detector (as Task-00's gate injects them), reading the barcode of a food already in the document opens `food <id> <meal> <date>` with no lookup request.
- [ ] A code in `doc.catalogue` shows Found with the catalogue's values and store, with no network request; saving adds one food (source `coles` or `woolworths`, the barcode, per100) and opens its gram sheet.
- [ ] A code in neither goes to Open Food Facts (tests mock the endpoint with the real tzatziki answer saved under `tests/fixtures/scan/` with its URL and fetch date); Found shows 108 kcal per 100 g from it and none of the unlisted fields; saving gives source `off`.
- [ ] On Found, "This is my …" lists his foods matching the name ("tzatziki" finds Classic Tzatziki Dip on the starter document); picking it adds the barcode to that food, makes no new food, and opens its gram sheet.
- [ ] A code found nowhere, or Open Food Facts down or offline, shows the label form; saving with energy in kJ stores kcal = kJ ÷ 4.184; a missing name or energy is said in words and nothing is saved.
- [ ] A barcode is never stored twice: scanning a saved product again opens the same food.
- [ ] Every camera track stops when the scan screen is left by any route (Task-00's checks keep passing); an EAN-13 with a wrong check digit is ignored, not looked up.
- [ ] At 360 × 780 with text at 150 % and at 240 px: no horizontal scroll, no console errors, dark and light both render.
- [ ] The tests fail when unlisted Open Food Facts fields are copied into per100, and when a listed 0 is dropped (shown once each, restored).
- [ ] (eye) On `terra_nt` at 360 dp: Scan, Found and From the label match `design/screens.html` → *5*, *6*, *6b*. Tarık scans five real packs on his phone at https://estaed.github.io/Pantry/ after deploy (also closes Task-00's open eye check).

## Out of scope
- Building the catalogue (wave 3, from his Coles receipts); this task reads `doc.catalogue` when present and works without it.
- The gram sheet itself (Task-03): this task opens it with `Pantry.go('food', id, meal, date)`.
- Edits to `tests/acceptance.py`: its scan scenario reads 9312726072232 and expects the code, "Read in x.x s", the track still live and Back to Today; with the real flow that becomes a lookup. List the hook change; the orchestrator moves it and mocks `world.openfoodfacts.org` in the gate.

Fixed:
- Routes, `doc.catalogue` shape, drawings, test layout: Blueprint → *Screens and seams*.
- `app/newfood.js` is a new script: list `PANTRY_FEATURES.push('app/newfood.js');` in the report for the orchestrator to append to `app/registry.js`.
- Keep the gate hooks `data-test="scan-status"` and `data-test="scan-code"`.

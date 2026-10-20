# Notes

The first file of the project and the one place for ideas. Nothing here is binding; what holds
becomes Blueprint. Dump freely, then sort: v1 is the simplest complete version, and everything it
doesn't need moves to *After v1*. Eko points out when the v1 list grows past that.

Started 2026-10-20 from a TarikOS session; background and sources in
`D:/TarikOS/knowledge/concepts/hermes-ile-market-alisverisi-fizibilite.md`.

## Goal
Tarık's own food log, built from the MyNetDiary features he actually uses, that also knows what
is in his kitchen: what he bought (Coles receipts) minus what he logged eating. Once a week Hermes
posts a visual "running out this week" list to Discord. For Tarık only. Later (v1.2) it merges
with his workout app (`D:/Projects/Calisthenics-App`).

## Riskiest assumption
Bought − logged gives a stock number close enough to trust. Logging is ~80% accurate (near 100% in
training periods), meals out are not from the kitchen, and a receipt line ("Coles Tuna Chunks
185g ×4") must map to a log line ("Tuna chunks with olive oil blend, 140 g"). Cheapest test:
backfill 2–3 weeks of real Coles receipts and real log entries, compute stock, and ask Tarık what
is actually in the kitchen.

## Acceptance
- <to fill with Tarık>
- (eye) <to fill with Tarık>

## What we know (2026-10-20)
- **Coles receipts, in-store and online, item by item:** coles.com.au/account/orders → "Instore
  purchases" (Flybuys-linked), 6 pages × 20 receipts, all Coles Darwin; every receipt lists product,
  quantity and price. The page loads them as JSON from
  `GET /api/bff/orders?status=in-store&pageNumber=N&pageSize=20`; a bare `fetch` returned 401
  "missing subscription key" (the site adds a key header), so it needs a logged-in browser session.
  Online order confirmation mails in Gmail (no-reply@coles.com.au) also list every item.
  Woolworths: Tarık says past orders incl. in-store exist there too (not checked).
- **MyNetDiary today:** free version on his phone; Tarık created an account on 2026-10-20 (backup,
  web access; free yearly Excel export per MyNetDiary help, untested). No export in the app menu.
  Log entries carry brand, store and amount: "Australian mozzarella cheese shredded by Coles, 150g",
  "Washed white potato by Woolworths, 350g", "Margherita family pizza by McCain, 500g".
- **Barcode data:** Open Food Facts is free but thin for Australia (Coles eggs and tuna found,
  McCain family pizza not). Since Tarık eats the same things, a personal product list seeded from
  Coles receipts, each label read once, covers most of it.
- **No official cart or checkout API** at Coles or Woolworths; auto-checkout is out (see After v1).

## How Tarık logs today (screen recording, `references/mynetdiary-logging-2026-10-20.mp4`)
1. Dashboard: calorie budget 2,200, eaten / over, per-meal totals (Breakfast, Lunch, Dinner,
   Snacks), carbs / protein / fat bars with grams and "over/left", a 7-day bar strip.
2. Tap a meal → "Search and Log Food" (also: Copy From Yesterday's Lunch, Meal Scan, Suggest Meals).
3. The search screen opens on **"Frequent lunch foods"** (his staples, per meal) and
   **"Latest foods"**; each row shows kcal for its last amount ("590cals / 1000 g").
4. Tap a food → amount in grams with **preset chips from the pack size** (350g, 500g, 1000g, g,
   serving) and live kcal → Save. Toast "logged to Lunch on 19 Oct".
5. Barcode button exists; not used in the recording.
So the core loop is: meal → pick a frequent food → grams → save. Few taps, no typing.

Tarık's own rules (2026-10-20): a product (or a meal) is scanned by barcode **once**, then always
picked from the frequent list; a food he logged before offers its earlier grams, otherwise he types
them. He logs the **raw** weight, and the cooking oil as its own line. So foods carry raw per-100 g
values, no cooked conversion is needed, and raw grams subtract straight from pack stock.

## Ideas
- Frequent foods per meal + gram chips are the whole logging UI; search and barcode for new items.
- New product without data: photo of the nutrition panel, a model reads it once.
- Stock per product = bought (receipts) − eaten (log, converted to the pack unit).
- Weekly Discord image from Hermes: items with days left, react to correct ("ran out" / "still have").

## Decided (Tarık, 2026-10-20)
- **Stack:** single-file PWA like Calisthenics-App (index.html + sw.js, localStorage, GitHub
  sync, GitHub Pages); Android only, "hafif". Camera barcode via Chrome Android's built-in
  `BarcodeDetector` (HTTPS, `ean_13`), no library (not yet tried on his phone). Open-sourcing is
  just a public repo. Native (Kotlin/Flutter) rejected: an APK to build and sideload.
- **Calorie math:** raw weight + oil as its own line (above).
- **Eating out:** left out of v1, or logged loosely by ingredients. History shows he has logged
  restaurant meals as one item ("Whopper junior by Burger King", "2X Chicken Royale and 2X Medium
  Chips"), so such foods simply never touch kitchen stock.
- **UI language:** English (Tarık, 2026-10-20); food names are English already and the repo may go public.

## MyNetDiary history (pulled 2026-10-20)
`references/mynetdiary-history-2026-10-20.json` (gitignored, personal data): every day from
2025-07-14 to 2026-10-20, **464 days, 0 gaps, 2,722 entries, 115 distinct foods**. Each entry:
meal, food name and brand, amount as typed ("185 g", "4 eggs", "2 scoops"), grams, kcal, ~24
nutrients (protein, fat, carbs, fiber, sodium…) and the food's serving list. 137 entries have no
grams (ml drinks, restaurant "servings") but still carry kcal. Pulled from the signed-in web app's
`GET /muiGetMeals.do?date=YYYY-MM-DD` (free account, one call per day, ~2 s each, in Opera).
So v1 starts with his real food list, per-meal frequent lists and last grams; nothing to type in.
Coverage per entry: kcal, protein, carbs, fat, sugars, sat fat and sodium on ~98 %; fiber 83 %;
vitamins, minerals and cholesterol only on ~20 % (generic foods, not Coles labels). Not in it:
water (no such trackable), barcodes, body weight history (MyNetDiary shows -12 kg since 14 Jul
2025, last weigh-in 75 kg; another endpoint), steps (Samsung Health), the 100+ other nutrients
MyNetDiary lists (only what the food's label carries). Targets read: 2,200 kcal, carbs 45 %,
protein 20 %, fat 35 %, salt 5.8 g.
Top staples: butter 5 g (316×), Coles tuna 185 g (225×), chicken breast raw 350 g, Coles basmati
100 g, iceberg blend 300 g, tzatziki 125 g.

## Open questions
- Where it runs: Coles session lives in Tarık's Opera on the PC; can Hermes (Azure) fetch receipts?

## Screens
Tarık uses one screen in MyNetDiary: the calorie budget, the list of foods to add, and the amount
screen a tap opens. Prototype v2 `design/screens.html` (2026-10-20), after his notes on v1 ("biraz
fazla kalabalık", MyNetDiary-like but original, illustrations welcome, visuals over text, only
protein / carbs / fat up front, "o alttaki bar hoşuma gidiyordu"):
1. **Bugün:** the anchor box holds a plate ring (kcal left, orange) and the four meals with their
   kcal; three macro bars; the last 7 days as bars against the 2,200 line, today orange; a bottom
   "Akşama ekle" button and a barcode button.
2. **Meal list:** search + barcode, his frequent foods for that meal, each with a food drawing,
   "350 g, 378 kcal" and a **+** that logs the last amount in one tap.
3. **Gram sheet:** drawing, his most used amounts as chips, grams, kcal, the food's protein / carbs
   / fat as one split bar; salt, sugar, fiber, sat fat and the rest under "Tüm besinler".
Open: the drawing style (A thin line, B flat greys, C flat natural colours), Tarık picks.
No stock screen in v1: the weekly Discord list covers stock (Tarık, 2026-10-20).

## After v1
- 2026-10-20: adding to the Coles/Woolworths trolley; no official API, browser automation is fragile.
- 2026-10-20: auto-checkout with a virtual card; saves one tap, adds the riskiest step. Payment stays with Tarık.
- 2026-10-20: merge with the workout app (v1.2, Tarık); body weight comes with it, not in v1 (Tarık no longer weighs in).
- 2026-10-20: Woolworths receipts, if needed (all receipts so far are Coles).

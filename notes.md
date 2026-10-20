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

## Open questions (Tarık, 2026-10-20)
- **Eating out:** how is a restaurant meal logged, and kept out of kitchen stock?
- **Calorie math:** answered: raw weight + oil as its own line (above). Per-100 g values come
  from his MyNetDiary foods if exportable, else barcode / label photo.
- **MyNetDiary history (2026-10-20):** help pages promise only a free yearly "consolidated"
  Excel (food-level detail unknown) and paid PDF/XLS reports; nothing tested. Next: Tarık signs in
  at mynetdiary.com in Opera, Eko looks at the web diary and its network calls (like Coles). What
  matters is his food list (name, per-100 g, last grams), not daily totals.
- **Stack, Eko's recommendation:** single-file PWA like Calisthenics-App (index.html + sw.js,
  localStorage, GitHub sync, GitHub Pages); Android only. Camera barcode via Chrome Android's
  built-in `BarcodeDetector` (HTTPS, `ean_13`), no library. Installs to the home screen, opens
  offline, open-sourcing is just a public repo, and the v1.2 merge is one codebase style. Native
  (Kotlin/Flutter) rejected: an APK to build and sideload, nothing v1 needs. Awaiting Tarık.
- Where it runs: Coles session lives in Tarık's Opera on the PC; can Hermes (Azure) fetch receipts?

## Screens
<Eko fills by asking, before any mockup>

## After v1
- 2026-10-20: adding to the Coles/Woolworths trolley; no official API, browser automation is fragile.
- 2026-10-20: auto-checkout with a virtual card; saves one tap, adds the riskiest step. Payment stays with Tarık.
- 2026-10-20: merge with the workout app (v1.2, Tarık).
- 2026-10-20: Woolworths receipts, if needed (all receipts so far are Coles).

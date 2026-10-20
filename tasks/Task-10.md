# Task-10: Barcode catalogue from his Coles and Woolworths purchases
> **Execution:** agent `ultracode`
> *Why:* a scanned product he has bought before should be found without typing its label, and most of what he scans comes from these two stores.

**Lane**
- OWNS: `tools/catalogue.py`, `tests/test_catalogue.py`, `tests/fixtures/catalogue/`
- MUST NOT TOUCH: `app/`, `index.html`, `sw.js`, `tools/import_mynetdiary.py`, `tests/acceptance.py`, every other test file
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_catalogue.py`)
- DEPENDS ON: none (the raw purchases are captured by the main loop before the wave starts)

## Goal
On the PC, Tarık (or Eko for him) runs one command over the raw purchase data the main loop saved from his
logged-in Opera, and gets the products he has bought at Coles and Woolworths as catalogue items the app
already understands (`doc.catalogue`: `{ barcode, name, brand?, size?, store, per100 }`, Blueprint →
Barcode catalogue), merged into his data document without touching anything else in it.

Raw input lives outside the repo in `D:/Projects/Pantry/.tmp/purchases/` (personal data: read it to learn
the real shapes, never copy it into the repo): Coles in-store and online orders as the site returns them,
Coles product data per product, Woolworths eReceipts (Everyday Rewards, GraphQL), Woolworths search results
for each receipt line and product details per stockcode, plus a `README.md` written by the main loop that
says which file is which. How Woolworths works and why its receipt lines are text only:
`reports/2026-10-21-woolworths-research.md`.

The command turns receipts into purchase lines (product, quantity, weight, price, date, store; multi-buys,
weighed items and discounts joined into the line they belong to), finds each line's product (Coles by its
product id; Woolworths by matching the line text to the captured search results), and builds one catalogue
item per product with a barcode: name, brand, pack size, store, and per 100 g values converted to the
document's units (kcal from the label's Cal when it gives one, else kJ ÷ 4.184; "1,520kJ" parses; sodium mg
kept and salt g = sodium × 2.5 ÷ 1000, as New food does; values the label leaves out, as "-" or "< 1 g",
stay absent, never filled in). A product without energy gets no catalogue item (the app refuses a
catalogue item without `per100.kcal`): it goes to the skipped list.
A Woolworths line whose match is not clear is not guessed: it goes into a review list Tarık can answer once,
and the answer is reused on the next run. Write down what "clear" means in the tool's header. Review,
answers and mapping files hold his purchases, so they live in `.tmp/purchases/`, never in the repo. When an
answer names a stockcode whose details were not captured, the tool lists the stockcodes still to capture. It writes the purchase lines to their own file outside the document, for the v1.1 stock spike.

## Why
Retires the "type the label" step for most products he scans, and gives v1.1 its bought side.

## Acceptance
- [ ] On fixture inputs (public product data from both stores in `tests/fixtures/catalogue/`, receipts built in the test code in the real shapes), the command writes the expected catalogue items: barcode, name, brand, size, store, per100 with kcal from kJ to one decimal of the label's own value.
- [ ] A Coles receipt with a multi-buy and a weighed item, and a Woolworths receipt with a discount line, become the right purchase lines (quantity, weight, price after discount).
- [ ] A Woolworths line with one clear search match gets that product; with none or several close ones it goes to the review list and gets no catalogue item; an answer saved in the review file is used on the next run.
- [ ] A product without a barcode gets no catalogue item; two receipts of the same product give one item; a label value of "-" or "< 1 g" is absent in per100.
- [ ] The merged document passes the app's own check: the test loads it in the app (`Pantry.problem()` stays null).
- [ ] `--merge <pantry-data.json>` replaces only `catalogue` and leaves (parsed-equal) foods, entries, settings and removed byte-for-byte equal; it refuses a file whose `version` it does not know.
- [ ] Run once on the real captured data in `.tmp/purchases/`: the report gives the counts (receipts, lines, products, items with barcode, review items, skipped) and the auto-match rate, with 20 sampled line → product pairs for Tarık to judge; no personal data is written inside the repo.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).

## Out of scope
- Fetching from the stores (the main loop does it in Tarık's browser), uploading to `Pantry-Data` (main loop), any app screen, stock numbers.

Fixed:
- Catalogue item shape and `store` values `coles` | `woolworths`: Blueprint → Barcode catalogue and Screens and seams.
- Personal purchase data never enters the repo (AGENTS.md); fixtures hold public product data only.
- On Windows force UTF-8 when reading and writing (`PYTHONUTF8` or explicit encoding): product names carry non-ASCII.

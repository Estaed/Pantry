"""Gate for Task-10: tools/catalogue.py, the barcode catalogue from Tarik's Coles and Woolworths purchases.

Run from the repo root: python tests/test_catalogue.py   (exit 0 = no FAIL; prints PASS or FAIL per check)

Inputs are the public product data in tests/fixtures/catalogue/ (README there) and receipts built here in the
shapes the store sites return; personal receipts never enter the repo, so every identifier, time, store, amount
and non-food line in these receipts is made up and matches none of Tarik's. The tool runs as Tarik runs it, a separate
process, on work folders under .tmp/ (git-ignored), removed at the end. Expected values are worked by hand from
the fixture labels, never taken from the tool. The merged document is loaded in the app through the gate's own
server and phone (tests/acceptance.py), so the app's own check judges it.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
TOOL = ROOT / "tools" / "catalogue.py"
FIX = ROOT / "tests" / "fixtures" / "catalogue"
check = A.check


def git_ignores(path):
    return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--", path]).returncode == 0


if git_ignores(".tmp/test_catalogue/x.json"):
    WORK = ROOT / ".tmp" / "test_catalogue"
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
else:
    WORK = Path(tempfile.mkdtemp(prefix="test_catalogue-"))


# ── receipts in the shapes the store sites return (built here, not personal: ids, times, stores, amounts made up) ──
def coles_item(pid, name, total, unit, quantity=1, weight=None, promotion=False):
    order = {"orderItemId": str(pid), "quantity": 0 if weight else quantity}
    if weight:
        order["weight"] = weight
    order.update(itemTotalPrice=total, itemSaving=0, unitPrice=unit, taxable=False, promotion=promotion)
    order["return"] = False
    return {"id": pid, "name": name, "brand": "", "size": "", "orderItem": order}


def coles_receipt(order_id, time, items, total=None):
    paid = round(sum(i["orderItem"]["itemTotalPrice"] for i in items), 2)
    return {"orderId": order_id, "transactionId": f"{order_id:0>20}", "time": time, "store": "Coles Test Store",
            "total": paid if total is None else total, "status": 200, "items": items}


def ww_line(description, amount="", prefix=None):
    return {"__typename": "ReceiptDetailsLineItem", "prefixChar": prefix, "description": description, "amount": amount}


def ww_receipt(n, when, lines, count, total, division="SUPERMARKETS", title="0000 Test Store"):
    day = datetime.strptime(when.split()[-1], "%d/%m/%Y")
    return {"id": f"receipt-{n}", "date": day.strftime("%a %d %b"), "section": day.strftime("%B %Y"), "desc": f"${total} at Test Store",
            "status": 200, "receipt": {"__typename": "ReceiptDetails", "details": [
                {"__typename": "ReceiptDetailsHeader", "title": title, "content": "", "division": division, "storeNo": "0000"},
                {"__typename": "ReceiptDetailsTotal", "total": f"${total}"},
                {"__typename": "ReceiptDetailsItems",
                 "header": {"__typename": "ReceiptDetailsLineItem", "description": "Description", "amount": "$"},
                 "items": lines},
                {"__typename": "ReceiptDetailsSummary", "discounts": [], "summaryItems": [],
                 "gst": {"__typename": "ReceiptDetailsLineItem", "prefixChar": None, "description": "#Total includes GST", "amount": "$0.03"},
                 "receiptTotal": {"__typename": "ReceiptDetailsLineItem", "prefixChar": None,
                                  "description": f"TOTAL ({count} items)", "amount": f"${total}"}},
                {"__typename": "ReceiptDetailsFooter",
                 "barcode": {"__typename": "ReceiptDetailsBarcode", "value": f"{n:020d}", "type": "Code128"},
                 "transactionDetails": f"POS  001  TRANS  {n:04d}   {when}", "abnAndStore": "ABN 00 000 000 000, STORE 0000"}]}}


COLES_RECEIPTS = [
    coles_receipt("101", "2026-03-02T18:05:00+09:30", [
        coles_item(8430488, "Coles Simply Tzatziki Dip 500g", 4.8, 4.8),
        coles_item(9185357, "Barilla Al Bronzo Pasta Penne 500g", 5.0, 3.3, quantity=2, promotion=True),  # 2 for $5
        coles_item(2263179, "RSPCA Approved Chicken Breast Fillets Large Pack per kg", 15.0, 12, weight=1.25),
        coles_item(7716500, "Western Star Spreadable Blend Original Soft 500g", 6.0, 6.0),
        coles_item(6007487, "Coles Tzatziki Dip 200g", 3.5, 3.5)]),
    coles_receipt("102", "2026-03-10T17:40:00+09:30", [
        coles_item(8430488, "Coles Simply Tzatziki Dip 500g", 4.8, 4.8),
        coles_item(8703059, "Coles Basmati Rice 1Kg", 4.2, 4.2)], total=0.0),       # $9.00 off the total, on no line
]
WW_RECEIPTS = [
    ww_receipt(1, "10:05   15/03/2026", [
        ww_line("Woolworths Paper Bag", "0.30", "#"),
        ww_line("#WW Basmati Rice Microwave Cup 2X125g", "", "^"),
        ww_line("Qty 3 @ $2.50 each", "7.50"),
        ww_line("ANY 3.00 for $6.00", "-1.50"),
        ww_line("Potato 4kg P/P Odd Bunch", "7.10"),
        ww_line("Western Star Spreadable 500g", "5.00"),
        ww_line("PRICE REDUCED BY $1.50 each", ""),
        ww_line("Macro Organic Pasta Penne 500g", "2.10")], 7, "20.50"),
    ww_receipt(2, "09:30   08/03/2026", [
        ww_line("WW Basmati Rice Microwave Cup 2X125g", "2.50"),
        ww_line("Bananas Cavendish", ""),
        ww_line("0.640 kg NET @ $4.50/kg", "2.88")], 2, "5.38"),
    ww_receipt(3, "15:45   19/01/2026", [ww_line("0000001 BATH TOWEL", "12.50", "#")], 1, "12.50",
               division="BIGW", title="0000 BIG W Test Store"),
]

# ── what the labels say, worked by hand (fixture values; kcal = kJ / 4.184 to one decimal when no Cal) ──
TZATZIKI = {"barcode": "9310645499628", "name": "Tzatziki Dip", "brand": "Coles Simply", "size": "500g", "store": "coles",
            "per100": {"kcal": 102, "protein": 5.8, "carbs": 9.9, "fat": 4, "sugars": 7.5, "satFat": 1.3, "salt": 0.79,
                       "fibre": 1.6, "sodium": 315, "transFat": 0.1}}                     # 102 Cal on the label
RICE = {"barcode": "9300601176762", "name": "Basmati Rice", "brand": "Coles", "size": "1Kg", "store": "coles",
        "per100": {"kcal": 339, "protein": 7, "carbs": 74, "fat": 0.9, "sugars": 0, "satFat": 0.17, "salt": 0,
                   "fibre": 0.8, "sodium": 1}}
PENNE = {"barcode": "8076809585705", "name": "Al Bronzo Pasta Penne", "brand": "Barilla", "size": "500g", "store": "coles",
         "per100": {"kcal": 363.3, "protein": 14, "carbs": 69.7, "fat": 2, "sugars": 3.5, "satFat": 0.4, "salt": 0.01,
                    "fibre": 3, "sodium": 5}}                                              # 1520 kJ only
SPREAD_COLES = {"barcode": "9310052122515", "name": "Spreadable Blend Original Soft", "brand": "Western Star",
                "size": "500g", "store": "coles",
                "per100": {"kcal": 614.2, "carbs": 1.2, "fat": 68.4, "sugars": 1.2, "satFat": 28, "salt": 1.22,
                           "sodium": 487}}                                                 # protein "LESS THAN 1 g", no fibre row
CUP = {"barcode": "9339687135141", "name": "Woolworths Basmati Rice Microwave Cup", "brand": "Woolworths",
       "size": "125g x 2 pack", "store": "woolworths",
       "per100": {"kcal": 161.8, "protein": 2.7, "carbs": 34.8, "fat": 0.9, "sugars": 0.1, "satFat": 0.2, "salt": 0.01,
                  "fibre": 1, "sodium": 5}}                                                # 677.0kJ
SPREAD_WW = {"barcode": "9310052122515", "name": "Western Star Original Spreadable Butter Blend Tub", "brand": "Western Star",
             "size": "500g", "store": "woolworths",
             "per100": {"kcal": 614.2, "carbs": 1.2, "fat": 68.4, "sugars": 1.2, "satFat": 28, "salt": 1.22,
                        "sodium": 487}}                                                    # protein "< 1.0g", fibre "-"
KEYS = ["barcode", "name", "brand", "size", "store", "per100"]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def purchases(name, coles_products=None, ww_products=None, ww_receipts=None):
    folder = WORK / name / "purchases"
    write(folder / "coles-receipts.json", COLES_RECEIPTS)
    write(folder / "coles-products.json", coles_products or load(FIX / "coles-products.json"))
    write(folder / "woolworths-receipts.json", ww_receipts or WW_RECEIPTS)
    write(folder / "woolworths-products.json", ww_products or load(FIX / "woolworths-products.json"))
    return folder


def run(folder, out, *extra):
    """The tool as Tarik runs it: a separate process from the repo root."""
    done = subprocess.run([sys.executable, str(TOOL), "--purchases", str(folder), "--out", str(out), *map(str, extra)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    return done.returncode, done.stdout + done.stderr


def by_code(items):
    return {i["barcode"]: i for i in items}


def line(lines, store, text, receipt_date=None):
    found = [x for x in lines if x["store"] == store and x["text"] == text and (receipt_date is None or x["date"] == receipt_date)]
    return found[0] if len(found) == 1 else {"found": len(found)}


def pick(d, *keys):
    return {k: d.get(k) for k in keys}


# ── scenarios ─────────────────────────────────────────────────────
def first_run():
    folder, out = purchases("main"), WORK / "main" / "out"
    code, said = run(folder, out)
    check("the tool runs on the fixtures and exits 0", code == 0, said[-600:])
    cat, lines = load(out / "catalogue.json"), load(out / "purchases.json")["lines"]
    review, capture, skipped = load(folder / "woolworths-review.json"), load(out / "to-capture.json"), load(out / "skipped.json")

    # catalogue items
    want = by_code([TZATZIKI, RICE, PENNE, SPREAD_COLES, CUP])
    got = by_code(cat)
    check("the catalogue holds exactly the expected items: barcode, name, brand, size, store and per100 from the label",
          got == want, {k: (got.get(k), want.get(k)) for k in set(got) | set(want) if got.get(k) != want.get(k)})
    check("each item lists its fields in the Blueprint's order (barcode, name, brand, size, store, per100)",
          all(list(i) == KEYS for i in cat), [list(i) for i in cat])

    def per100(code):
        return (got.get(code) or {}).get("per100") or {}
    check("kcal is the label's Cal when it gives one, else kJ / 4.184 to one decimal (1520 kJ -> 363.3, 677.0kJ -> 161.8)",
          per100(PENNE["barcode"]).get("kcal") == 363.3 and per100(CUP["barcode"]).get("kcal") == 161.8
          and per100(TZATZIKI["barcode"]).get("kcal") == 102, [(i.get("per100") or {}).get("kcal") for i in cat])
    spread100 = per100(SPREAD_COLES["barcode"])
    check("a label value of 'LESS THAN 1 g' or a missing row stays absent (Western Star at Coles: no protein, no fibre)",
          spread100 and "protein" not in spread100 and "fibre" not in spread100, got.get(SPREAD_COLES["barcode"]))
    check("two receipts of the same product give one item (the tzatziki, bought twice)",
          sum(1 for i in cat if i["barcode"] == TZATZIKI["barcode"]) == 1
          and sum(1 for x in lines if x["product"] == 8430488) == 2, [i["barcode"] for i in cat])
    check("a product without a barcode gets no item and is listed as skipped (the chicken sold per kg)",
          all(i["name"] != "RSPCA Approved Chicken Breast Fillets Large Pack" for i in cat)
          and {"store": "coles", "product": 2263179, "why": "no barcode"} in [pick(s, "store", "product", "why") for s in skipped],
          skipped)
    check("a product without energy gets no item and is listed as skipped (the potato with no nutrition table)",
          all(i["barcode"] != "9300633686222" for i in cat)
          and [s["why"] for s in skipped if s["product"] == 652008] == ["no per 100 g table"], skipped)
    small = line(lines, "coles", "Coles Tzatziki Dip 200g")
    check("a Coles page the bot check stopped is listed to capture; its line keeps the product id, with no barcode or item",
          capture.get("colesProductIds") == [6007487] and small.get("product") == 6007487 and "barcode" not in small,
          (capture, small))

    # purchase lines: Coles multi-buy and weighed item, Woolworths quantity, discount, reduced and weighed lines
    penne = line(lines, "coles", "Barilla Al Bronzo Pasta Penne 500g")
    check("a Coles multi-buy is one line: quantity 2, $5.00 paid, $1.60 off the shelf price",
          pick(penne, "product", "quantity", "price", "discount", "date", "match") ==
          {"product": 9185357, "quantity": 2, "price": 5.0, "discount": 1.6, "date": "2026-03-02", "match": "id"}, penne)
    chicken = line(lines, "coles", "RSPCA Approved Chicken Breast Fillets Large Pack per kg")
    check("a Coles weighed item is quantity 1 with its weight in kg and the price paid, no discount",
          pick(chicken, "quantity", "weightKg", "price", "discount") ==
          {"quantity": 1, "weightKg": 1.25, "price": 15.0, "discount": None}, chicken)
    cup = line(lines, "woolworths", "WW Basmati Rice Microwave Cup 2X125g", "2026-03-15")
    check("a Woolworths line with its Qty line and an 'ANY 3.00 for $6.00 -1.50' line is one line: quantity 3, $6.00 after the discount",
          pick(cup, "quantity", "price", "discount", "date", "time", "product", "match") ==
          {"quantity": 3, "price": 6.0, "discount": 1.5, "date": "2026-03-15", "time": "10:05", "product": 63665,
           "match": "clear"}, cup)
    spread = line(lines, "woolworths", "Western Star Spreadable 500g")
    check("'PRICE REDUCED BY $1.50 each' is kept as the line's discount; the price is what was paid",
          pick(spread, "quantity", "price", "discount") == {"quantity": 1, "price": 5.0, "discount": 1.5}, spread)
    bananas = line(lines, "woolworths", "Bananas Cavendish")
    check("a Woolworths weighed item ('0.640 kg NET @ $4.50/kg') is quantity 1, 0.64 kg, $2.88",
          pick(bananas, "quantity", "weightKg", "price") == {"quantity": 1, "weightKg": 0.64, "price": 2.88}, bananas)
    check("the leading # and ^ are dropped, follow-up lines are not lines of their own, BIG W receipts are skipped",
          sorted(x["text"] for x in lines if x["store"] == "woolworths") == sorted(
              ["Woolworths Paper Bag", "WW Basmati Rice Microwave Cup 2X125g", "Potato 4kg P/P Odd Bunch",
               "Western Star Spreadable 500g", "Macro Organic Pasta Penne 500g", "WW Basmati Rice Microwave Cup 2X125g",
               "Bananas Cavendish"]), [x["text"] for x in lines if x["store"] == "woolworths"])
    check("the report shows both Woolworths receipts add up and the Coles receipt-level discount",
          "Woolworths 2 of 2 add up" in said and "receipt-level discounts on no line: 1 receipt, $9.00" in said, said[:900])

    # matching: one clear result gets it; a tie, no fit and no search go to the review list
    open_lines = {e["line"]: e for e in review.get("lines", []) if e.get("answer") is None}
    check("a line with one clear search result gets that product (WW Basmati cup -> 63665; prepacked potato -> 652008)",
          line(lines, "woolworths", "Potato 4kg P/P Odd Bunch").get("product") == 652008 and cup.get("product") == 63665)
    tie = open_lines.get("Western Star Spreadable 500g", {})
    check("a line with several close results goes to review with them as candidates, and gets no product or item",
          "equally" in tie.get("why", "") and {199420, 69756} <= {c["stockcode"] for c in tie.get("candidates", [])}
          and spread.get("product") is None and spread.get("match") == "review"
          and got.get(SPREAD_COLES["barcode"], {}).get("store") == "coles", tie)
    none = open_lines.get("Macro Organic Pasta Penne 500g", {})
    check("a line with no fitting result goes to review and gets no product",
          "no result" in none.get("why", "") and line(lines, "woolworths", "Macro Organic Pasta Penne 500g").get("product") is None,
          none)
    check("lines with no captured search go to review and to the searches still to capture",
          {"Woolworths Paper Bag", "Bananas Cavendish"} <= set(open_lines)
          and sorted(capture.get("woolworthsLines", [])) == ["Bananas Cavendish", "Woolworths Paper Bag"], capture)
    check("clear lines are not in the review list", not {"WW Basmati Rice Microwave Cup 2X125g", "Potato 4kg P/P Odd Bunch"} & set(open_lines),
          sorted(open_lines))
    check("the report gives the counts and the auto-match rate with sampled line -> product pairs",
          all(s in said for s in ("receipts:", "purchase lines:", "products:", "with a barcode:", "catalogue items:",
                                  "review items:", "skipped:", "auto-match rate:", "Sample: ")), said[:1500])
    return folder, out, review


def answered_run(folder, out, review):
    for e in review["lines"]:
        e["answer"] = {"Western Star Spreadable 500g": 69756, "Macro Organic Pasta Penne 500g": "6034512",
                       "Woolworths Paper Bag": "none"}.get(e["line"], e["answer"])
    write(folder / "woolworths-review.json", review)
    code, said = run(folder, out)
    check("the tool runs again with answers in the review file", code == 0, said[-600:])
    cat, lines = load(out / "catalogue.json"), load(out / "purchases.json")["lines"]
    capture, again = load(out / "to-capture.json"), load(folder / "woolworths-review.json")
    spread = line(lines, "woolworths", "Western Star Spreadable 500g")
    check("an answer saved in the review file is used on the next run (Western Star -> 69756)",
          pick(spread, "product", "match") == {"product": 69756, "match": "answer"}, spread)
    got = by_code(cat)
    check("the same product from both stores is one item, from the store of the latest purchase; '< 1.0g' and '-' stay absent",
          got.get(SPREAD_WW["barcode"]) == SPREAD_WW and sum(1 for i in cat if i["barcode"] == SPREAD_WW["barcode"]) == 1
          and len(cat) == 5, got.get(SPREAD_WW["barcode"]))
    check("an answered stockcode whose details were not captured is listed to capture",
          capture.get("woolworthsStockcodes") == [6034512] and capture.get("woolworthsLines") == ["Bananas Cavendish"], capture)
    bag = line(lines, "woolworths", "Woolworths Paper Bag")
    check("a line answered 'none' leaves the review list and gets no product",
          pick(bag, "product", "match") == {"product": None, "match": "none"}, bag)
    kept = {e["line"]: e["answer"] for e in again["lines"] if e.get("answer") is not None}
    check("the review file keeps every answer, and only the unanswered line stays open",
          kept == {"Western Star Spreadable 500g": 69756, "Macro Organic Pasta Penne 500g": "6034512", "Woolworths Paper Bag": "none"}
          and [e["line"] for e in again["lines"] if e.get("answer") is None] == ["Bananas Cavendish"], again["lines"])
    code, _ = run(folder, out)
    check("a third run gives the same catalogue from the kept answers", code == 0 and load(out / "catalogue.json") == cat)
    return cat


def label_edge_cases():
    """Synthetic label values built from a fixture record: '1,520kJ', 'Approx.' and a table without energy."""
    ww = load(FIX / "woolworths-products.json")
    rows = ww["details"]["63665"]["NutritionalInformation"]
    for row in rows:
        values = row["Values"]
        values["Quantity Per 100g / 100mL"] = {"Energy": "1,520kJ", "Protein": "Approx.2.7g", "Sodium": "-"}.get(
            row["Name"], values["Quantity Per 100g / 100mL"])
    coles = load(FIX / "coles-products.json")
    for table in coles["8703059"]["nutrition"]["breakdown"]:
        table["nutrients"] = [n for n in table["nutrients"] if not n["nutrient"].startswith("Energy")]
    folder, out = purchases("labels", coles, ww), WORK / "labels" / "out"
    code, said = run(folder, out)
    got = by_code(load(out / "catalogue.json")) if code == 0 else {}
    cup = (got.get(CUP["barcode"]) or {}).get("per100") or {}
    check("'1,520kJ' parses (363.3 kcal), 'Approx.2.7g' is 2.7, sodium '-' leaves sodium and salt absent",
          cup.get("kcal") == 363.3 and cup.get("protein") == 2.7 and "sodium" not in cup and "salt" not in cup, (code, cup, said[-300:]))
    skipped = load(out / "skipped.json") if code == 0 else []
    check("a product whose table has no energy gets no item and is skipped as such",
          RICE["barcode"] not in got and [s["why"] for s in skipped if s["product"] == 8703059] == ["no energy on the label"], skipped)


def size_rule():
    """Rule 2 of 'clear' on its own: made-up carrot lines searched against the fixture's carrot results (288440
    Carrots 1.5kg, whose name is the closest; 139330 Crazy Carrots 5kg), and a copy of 288440 that states no size."""
    ww = load(FIX / "woolworths-products.json")
    results = ww["search"]["Potato 4kg P/P Odd Bunch"]["products"]
    sizeless = [{**r, "DisplayName": r["Name"], "PackageSize": None} for r in results if r["Stockcode"] == 288440]
    ww["search"].update({"Carrots 5kg": {"products": results}, "Carrots 1kg": {"products": results},
                         "Carrots 750g": {"products": sizeless}})
    receipt = ww_receipt(4, "12:00   21/03/2026", [ww_line("Carrots 5kg", "6.00"), ww_line("Carrots 1kg", "2.00"),
                                                   ww_line("Carrots 750g", "1.80")], 3, "9.80")
    folder, out = purchases("sizes", ww_products=ww, ww_receipts=[receipt]), WORK / "sizes" / "out"
    code, said = run(folder, out)
    check("the tool runs on the size-rule lines and exits 0", code == 0, said[-600:])
    lines = load(out / "purchases.json")["lines"] if code == 0 else []
    review = {e["line"]: e for e in load(folder / "woolworths-review.json")["lines"]} if code == 0 else {}

    def fits(text, stockcode):
        return [c["fits"] for c in review.get(text, {}).get("candidates", []) if c["stockcode"] == stockcode]
    five = line(lines, "woolworths", "Carrots 5kg")
    check("the pack size picks the product: 'Carrots 5kg' gets the 5kg carrots (139330), not the closer-named 1.5kg ones",
          pick(five, "product", "match") == {"product": 139330, "match": "clear"} and "Carrots 5kg" not in review, five)
    one = line(lines, "woolworths", "Carrots 1kg")
    check("a line whose size no result has goes to review with no product ('Carrots 1kg': only 1.5kg and 5kg carrots)",
          pick(one, "product", "match") == {"product": None, "match": "review"}
          and review.get("Carrots 1kg", {}).get("why") == "no result has every word of the line and its size"
          and fits("Carrots 1kg", 288440) == ["its size differs"], (one, review.get("Carrots 1kg")))
    loose = line(lines, "woolworths", "Carrots 750g")
    check("a result that states no size cannot pass a line that prints one ('Carrots 750g' against sizeless carrots)",
          pick(loose, "product", "match") == {"product": None, "match": "review"}
          and fits("Carrots 750g", 288440) == ["it states no size the line can be checked against"], (loose, review.get("Carrots 750g")))


def review_upkeep():
    """The review file keeps one entry per line: an answer that is not a Stockcode stays on its open line, and a
    line answered twice (as a file from an older run could hold) keeps the last answer that can be read."""
    folder, out = purchases("upkeep"), WORK / "upkeep" / "out"
    path = folder / "woolworths-review.json"
    code, said = run(folder, out)
    review = load(path) if code == 0 else {"lines": []}
    for e in review["lines"]:
        e["answer"] = {"Bananas Cavendish": "1234O"}.get(e["line"], e["answer"])
    write(path, review)
    code, said = run(folder, out)
    again = load(path) if code == 0 else {"lines": []}
    texts = [e["line"] for e in again["lines"]]
    bananas = [e for e in again["lines"] if e["line"] == "Bananas Cavendish"]
    check("a review answer that is not a Stockcode stays on its open line, once, with the reason, and the line still waits",
          code == 0 and len(texts) == len(set(texts)) == 4 and len(bananas) == 1 and bananas[0]["answer"] == "1234O"
          and "1234O" in bananas[0]["why"] and "review items:      4 lines waiting" in said
          and "PROBLEM: review answer '1234O' for 'Bananas Cavendish'" in said, (code, again["lines"], said[-600:]))
    before = path.read_bytes()
    code, _ = run(folder, out)
    check("the next run leaves that review file as it was", code == 0 and path.read_bytes() == before)

    # his answer on the open entry and an older typo further down; two readable answers, the later one counts
    for e in again["lines"]:
        e["answer"] = {"Western Star Spreadable 500g": 69756, "Macro Organic Pasta Penne 500g": "6034512"}.get(e["line"], e["answer"])
    again["lines"] += [{"line": "Western Star Spreadable 500g", "answer": "6975G"},
                       {"line": "Macro Organic Pasta Penne 500g", "answer": "none"}]
    write(path, again)
    code, said = run(folder, out)
    lines = load(out / "purchases.json")["lines"] if code == 0 else []
    kept = [(e["line"], e["answer"]) for e in load(path)["lines"]] if code == 0 else []
    check("a line answered twice keeps the last answer that can be read, once, and the report names the one dropped",
          pick(line(lines, "woolworths", "Western Star Spreadable 500g"), "product", "match") == {"product": 69756, "match": "answer"}
          and pick(line(lines, "woolworths", "Macro Organic Pasta Penne 500g"), "product", "match") == {"product": None, "match": "none"}
          and sorted(kept, key=lambda kv: kv[0]) == [("Bananas Cavendish", "1234O"), ("Macro Organic Pasta Penne 500g", "none"),
                                                     ("Western Star Spreadable 500g", 69756), ("Woolworths Paper Bag", None)]
          and "69756 counts and is kept, '6975G' dropped" in said and "review answer '6975G'" not in said
          and "review items:      2 lines waiting" in said, (code, kept, said[-700:]))


FOODS = [{"id": "f-1", "name": "Crème fraîche", "brand": "Coles", "per100": {"kcal": 337, "fat": 35}, "servings": [], "source": "label"},
         {"id": "v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao=", "name": "Chicken Breast Raw",
          "per100": {"kcal": 108.1, "protein": 20.33}, "servings": [], "source": "mynetdiary"}]
ENTRIES = [{"id": "2026-10-20-1", "date": "2026-10-20", "meal": "lunch", "foodId": "f-1", "amount": "30 g", "grams": 30,
            "totals": {"kcal": 101.1, "fat": 10.5}}]
SETTINGS = {"targets": {"kcal": 2200, "proteinPct": 20, "carbsPct": 45, "fatPct": 35, "salt": 5.8}}
REMOVED = [{"id": "2026-10-19-3", "at": "2026-10-19T08:00:00.000Z"}]


def compact(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def merges(folder, catalogue):
    # the phone's JSON.stringify shape, no catalogue yet: it is added after the last member
    head = '{"version":1,"foods":' + compact(FOODS) + ',"entries":' + compact(ENTRIES) + ',"settings":' + compact(SETTINGS) \
        + ',"removed":' + compact(REMOVED)
    doc_a = WORK / "merge" / "pantry-data.json"
    doc_a.parent.mkdir(parents=True, exist_ok=True)
    doc_a.write_bytes((head + "}").encode("utf-8"))
    out = WORK / "merge" / "out"
    code, said = run(folder, out, "--merge", doc_a)
    text = doc_a.read_bytes().decode("utf-8")
    middle = text[len(head):-1] if text.startswith(head) and text.endswith("}") else ""
    ok = middle.startswith(',"catalogue":') and json.loads(middle[len(',"catalogue":'):]) == catalogue
    check("--merge adds catalogue and leaves every other member byte for byte (a compact document)", code == 0 and ok,
          (code, said[-300:], text[len(head) - 40:len(head) + 60]))
    parsed = json.loads(text)
    check("--merge leaves foods, entries, settings and removed parsed-equal", all(
        parsed.get(k) == v for k, v in (("version", 1), ("foods", FOODS), ("entries", ENTRIES), ("settings", SETTINGS), ("removed", REMOVED))))

    # an indented document with CRLF line endings and an old catalogue in the middle: only that value changes
    old = [{"barcode": "9300000000000", "name": "Old", "store": "coles", "per100": {"kcal": 1}}]
    prefix = '{\r\n "version": 1,\r\n "foods": ' + json.dumps(FOODS, ensure_ascii=False, indent=1).replace("\n", "\r\n") \
        + ',\r\n "catalogue": '
    suffix = ',\r\n "entries": ' + json.dumps(ENTRIES, ensure_ascii=False, indent=1).replace("\n", "\r\n") \
        + ',\r\n "settings": ' + compact(SETTINGS) + ',\r\n "removed": ' + compact(REMOVED) + '\r\n}\r\n'
    doc_b = WORK / "merge" / "pantry-data-crlf.json"
    doc_b.write_bytes((prefix + compact(old) + suffix).encode("utf-8"))
    code, said = run(folder, out, "--merge", doc_b)
    text = doc_b.read_bytes().decode("utf-8")
    ok = text.startswith(prefix) and text.endswith(suffix) and json.loads(text[len(prefix):len(text) - len(suffix)]) == catalogue
    check("--merge replaces only the catalogue value of an indented CRLF document; every other byte is unchanged",
          code == 0 and ok and "replaced (it held 1)" in said, (code, said[-300:]))

    # a version it does not know is refused and the file is not touched
    doc_c = WORK / "merge" / "pantry-data-v2.json"
    raw = ('{"version":2,"foods":[],"entries":[],"settings":' + compact(SETTINGS) + '}').encode("utf-8")
    doc_c.write_bytes(raw)
    fresh = WORK / "merge" / "out-v2"
    code, said = run(folder, fresh, "--merge", doc_c)
    check("--merge refuses a document whose version it does not know: exit 1, the file and the outputs untouched",
          code == 1 and doc_c.read_bytes() == raw and not fresh.exists() and "version" in said, (code, said[-300:]))
    return doc_a


def in_app(doc, catalogue):
    """The merged document as the phone would hold it: the app's own check decides (Pantry.problem() stays null)."""
    text = doc.read_text(encoding="utf-8")
    srv, _, url = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            init = ("if (!sessionStorage.getItem('cat')) { sessionStorage.setItem('cat', '1'); "
                    f"localStorage.setItem('pantry.v1', {json.dumps(text)}); }}")
            ctx, page = A.phone(browser, errors, "catalogue", text=1.0, init=init)
            A.open_today(page, url)
            problem = page.evaluate("() => Pantry.problem()")
            codes = page.evaluate("() => (Pantry.doc().catalogue || []).map(c => c.barcode)")
            check("the merged document loads in the app: Pantry.problem() stays null and the catalogue is there",
                  problem is None and sorted(codes) == sorted(i["barcode"] for i in catalogue), (problem, codes))
            check("the app shows no console or page errors with the merged document", not errors, errors[:5])
            ctx.close()
            browser.close()
    finally:
        srv.shutdown()


def refusals(folder):
    inside = ROOT / "tests" / "fixtures" / "catalogue" / "out"
    stray = [FIX / "woolworths-review.json", FIX / "woolworths-mapping.json"]
    try:
        code, said = run(folder, inside)
        check("an output folder inside the repo that git does not ignore is refused (exit 2) and nothing is written",
              code == 2 and not inside.exists() and "REFUSED" in said, (code, said[-300:]))
        code, said = run(FIX, WORK / "refused" / "out")
        check("a purchases folder inside the repo is refused before its review file could be written there",
              code == 2 and not any(p.exists() for p in stray) and not (WORK / "refused").exists(), (code, said[-300:]))
    finally:  # a broken refusal must not leave files in the repo
        shutil.rmtree(inside, ignore_errors=True)
        for p in stray:
            p.unlink(missing_ok=True)
    broken = purchases("broken")
    (broken / "woolworths-review.json").write_text('{"lines": [{"line": "x", "answer": 1', encoding="utf-8")
    code, said = run(broken, WORK / "broken" / "out")
    check("a review file that cannot be read is never written over (exit 1, answers kept, nothing written)",
          code == 1 and (broken / "woolworths-review.json").read_text(encoding="utf-8") == '{"lines": [{"line": "x", "answer": 1'
          and not (WORK / "broken" / "out").exists(), (code, said[-300:]))


def guarded(name, fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 - a crash is one FAIL with its error; the other scenarios still run
        check(f"{name} ran to the end", False, f"{type(e).__name__}: {e}")
        return None


def main():
    try:
        first = guarded("first run", first_run)
        cat = guarded("answered run", answered_run, *first) if first else None
        guarded("label edge cases", label_edge_cases)
        guarded("size rule", size_rule)
        guarded("review upkeep", review_upkeep)
        if first and cat:
            doc = guarded("merge", merges, first[0], cat)
            if doc:
                guarded("app check", in_app, doc, cat)
        guarded("refusals", refusals, purchases("refusals"))
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print(f"\n{'ALL PASS' if not A.FAILS else str(len(A.FAILS)) + ' FAIL'}")
    sys.exit(1 if A.FAILS else 0)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    main()

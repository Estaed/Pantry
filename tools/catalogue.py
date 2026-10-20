"""Build Pantry's barcode catalogue from Tarik's Coles and Woolworths purchases.

Usage, from the repo root (Windows: run with PYTHONUTF8=1 or let the tool force UTF-8 itself):
    python tools/catalogue.py [--purchases .tmp/purchases] [--out .tmp/catalogue] [--merge <pantry-data.json>]

Input: the folder the main loop fills from Tarik's logged-in Opera (personal data, never in this repo; its
README.md says which file is which):
    coles-receipts.json       [{orderId, transactionId, time, store, total, items: [{id, name, orderItem}]}]
    coles-products.json       {<product id>: {id, name, brand, size, gtin, nutrition} or {missing: true}}
    woolworths-receipts.json  [{id, receipt: {details: [ReceiptDetailsHeader, ...Items, ...Summary, ...Footer]}}]
    woolworths-products.json  {search: {<line text>: {products: [top results]}}, details: {<stockcode>: detail}}

Output (every path is refused when it lies in a Pantry checkout and git does not ignore it; exit 2):
    <out>/catalogue.json      the items for doc.catalogue: {barcode, name, brand?, size?, store, per100}
    <out>/purchases.json      one purchase line per product line of a receipt, for the v1.1 stock spike
    <out>/skipped.json        the products that got no catalogue item, and why
    <out>/to-capture.json     Coles product ids, Woolworths stockcodes and Woolworths lines still to fetch
    <out>/report.txt          the report this run prints
    <purchases>/woolworths-review.json   the Woolworths lines whose product is not clear, with Tarik's answers
    <purchases>/woolworths-mapping.json  every Woolworths line text and the stockcode it was given, and how
    --merge FILE              replaces only the "catalogue" member of that data document, byte for byte
                              everything else; refuses a document whose version is not 1 (exit 1, untouched)

Purchase lines {store, date, time, receipt, text, product, name?, barcode?, match, quantity, weightKg?, price,
discount?}: price is what was paid for the line, after the discounts the receipt gives that line. Coles gives
one item per line with its product id (match "id"); a weighed item (quantity 0 and a weight) becomes quantity 1
with weightKg; discount is the shelf price times the quantity or weight minus what was paid. A Coles receipt
whose total is below the sum of its lines took a saving off the total itself: Flybuys dollars, or a multi-buy
the receipt did not put on its lines (they show itemSaving 0 and the shelf price). The receipt does not say
which lines it belongs to, so those lines keep the price the receipt gives them and the saving is only
reported. A Woolworths eReceipt prints a product line and then, below it, the lines that belong to it:
"Qty 3 @ $1.90 each" (the quantity and the line total), "0.716 kg NET @ $4.00/kg" (a weighed item), a line
with a negative amount ("ANY 2.00 for $5.00  -1.20", "<name> OFFER  -1.00", taken off the price) and "PRICE
REDUCED BY $1.50 each" (already in the price; kept as the discount). The leading # or ^ marks GST and
promotional items and is dropped. Dates come from the receipt's own text (Coles "time", the Woolworths footer
"10:05   15/03/2026"), never from the listing. BIG W receipts are not food and are skipped. Each Woolworths
receipt is checked: its lines must add up to its total and its item count.

Woolworths receipt lines carry no product id, so each distinct line text is matched to the captured search
results for that text. A match is CLEAR when exactly one result passes and is the closest:
  1. every word of the line is in the result's name: the same word or its plural, a cut word ("Multigrai"
     for "Multigrain"), the letters of an abbreviation in order and from the first ("Rst" for "Roasted",
     "Slt Vingar" for "Salt Vinegar"), or words run together ("NutCorn", "Kit Kat" for "KitKat"); WW is
     Woolworths and XL is Extra Large;
  2. its pack size agrees with the size the line prints: no stated grams, mL or pack count differs and,
     when the line prints one, at least one is the same ("Potato White Washed 2Kg" is not the loose potato);
     a multi-pack on both sides has the same count of the same size ("2X125g" is not "250g x 2 pack");
  3. when the line names the brand it names all of it ("WW Pasta Spaghetti" is not Woolworths Essentials);
  4. its name adds at most 2 words the line does not have, leaving out the brand when the line leaves it out
     and packaging words (bottle, tub, bag, punnet, ...), and every other passing result adds more.
Anything else (no search, no result passes, several close ones) goes to woolworths-review.json and gets no
product. There Tarik sets "answer" to the Stockcode he bought (a candidate's or any other) or "none" for a
line that is not a product to catalogue; the next run uses every answer, keeps it in the file, and lists an
answered stockcode whose details were not captured in to-capture.json. An answer also overrides a clear match:
add {"line": ..., "answer": ...} to the file. The file keeps one entry per line: an answer that cannot be read
stays on its open line, with the reason, until it is corrected; a line answered more than once keeps the last
answer that can be read and drops the others (the report names them).

Catalogue items, one per barcode (leading zeros ignored; a product bought at both stores is kept once, from
the store of its latest purchase): name, brand and size as the store gives them; per100 from the label's per
100 g (or 100 mL) table in the document's units: kcal from the label's Cal when it gives one, else kJ / 4.184
to one decimal; protein, carbs, fat, sugars, satFat, fibre, transFat, polyUnsatFat, monoUnsatFat in g;
sodium, calcium, iron, potassium in mg; salt g = sodium mg x 2.5 / 1000 to two decimals, as New food does.
"1,520kJ" and "Approx.5g" are read as the numbers they print. A value the label leaves out ("-", blank,
"< 1 g", "LESS THAN 1 mg") stays absent, never 0 or filled in; one that cannot be read is absent and counted.
A product without a barcode, without a per 100 g table or without energy gets no item (the app refuses a
catalogue item without per100.kcal): it is listed in skipped.json.

Exit 0: written. Exit 1: an input or the review file cannot be read, or --merge refused the document;
nothing is written. Exit 2: an output path is refused; nothing is written. Standard library only.
"""

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date as Date
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWN_VERSIONS = (1,)
STORES = ("coles", "woolworths")
INPUTS = ("coles-receipts.json", "coles-products.json", "woolworths-receipts.json", "woolworths-products.json")
REVIEW = "woolworths-review.json"
MAPPING = "woolworths-mapping.json"
NOT_FOOD_DIVISIONS = {"BIGW"}
LINE_FIELDS = ("store", "date", "time", "receipt", "text", "product", "name", "barcode", "match", "quantity", "weightKg",
               "price", "discount", "returned")
KJ_PER_KCAL = 4.184
MAX_EXTRA_WORDS = 2
SAMPLE = 20

# ── label values ───────────────────────────────────────────────────
# A label row's name, lower case with every non-letter run as one space -> (Pantry key, the document's unit).
NUTRIENTS = {
    "protein": ("protein", "g"),
    "fat": ("fat", "g"), "fat total": ("fat", "g"), "total fat": ("fat", "g"),
    "saturated": ("satFat", "g"), "fat saturated": ("satFat", "g"), "saturated fat": ("satFat", "g"),
    "carbohydrate": ("carbs", "g"), "carbohydrate total": ("carbs", "g"), "carbohydrates": ("carbs", "g"),
    "sugars": ("sugars", "g"), "sugars total": ("sugars", "g"), "sugar": ("sugars", "g"),
    "dietary fibre": ("fibre", "g"), "fibre": ("fibre", "g"), "dietary fiber": ("fibre", "g"),
    "sodium": ("sodium", "mg"),
    "fat transfat": ("transFat", "g"), "trans": ("transFat", "g"), "fat trans": ("transFat", "g"),
    "fat polyunsaturated": ("polyUnsatFat", "g"), "polyunsaturated": ("polyUnsatFat", "g"),
    "fat monounsaturated": ("monoUnsatFat", "g"), "monounsaturated": ("monoUnsatFat", "g"),
    "calcium": ("calcium", "mg"), "iron": ("iron", "mg"), "potassium": ("potassium", "mg"),
}
KEY_ORDER = ("kcal", "protein", "carbs", "fat", "sugars", "satFat", "salt", "fibre", "sodium",
             "transFat", "polyUnsatFat", "monoUnsatFat", "calcium", "iron", "potassium")
TO_G = {"g": 1, "mg": 0.001, "mcg": 0.000001, "ug": 0.000001}
VALUE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*(kj|kcal|cal|g|mg|mcg|ug)?$")
LEFT_OUT = re.compile(r"^(-+|–|—|n/?a|nil detected|not detected)$")
BELOW = re.compile(r"^(<|less than|lt\b)")


def label_value(text):
    """(number, unit) as the label prints it, or (None, why) when the label gives no number."""
    if text is None:
        return None, "blank"
    t = unicodedata.normalize("NFKC", str(text)).strip().lower().replace("µ", "u")
    if not t:
        return None, "blank"
    if LEFT_OUT.match(t):
        return None, "dash"
    if BELOW.match(t):
        return None, "below"
    t = re.sub(r"^(approx\.?|approximately|~)\s*", "", t)
    m = VALUE.match(t)
    if not m:
        return None, "unreadable"
    number = float(m.group(1).replace(",", "") + (m.group(2) or ""))
    return (int(number) if number.is_integer() else number), m.group(3)


def per100_from_rows(rows, notes):
    """per100 in the document's units from [(row name, value text)]; notes counts what stayed absent."""
    per100, kj, cal = {}, None, None
    for name, text in rows:
        key = re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(name)).lower()).strip()
        number, unit = label_value(text)
        if number is None:
            notes[unit] = notes.get(unit, 0) + 1
            if unit == "unreadable":
                notes.setdefault("unreadable values", []).append(f"{name}: {text}")
            continue
        if key.startswith("energy"):
            unit = unit or ("kj" if "kj" in key else "cal" if "cal" in key else None)
            if unit == "kj" and kj is None:
                kj = number
            elif unit in ("cal", "kcal") and cal is None:
                cal = number
            elif unit not in ("kj", "cal", "kcal"):
                notes.setdefault("unreadable values", []).append(f"{name}: {text}")
            continue
        if key not in NUTRIENTS:
            notes.setdefault("rows not used", set()).add(str(name))
            continue
        pantry, want = NUTRIENTS[key]
        if unit not in TO_G:
            notes.setdefault("unreadable values", []).append(f"{name}: {text}")
            continue
        if pantry in per100:
            continue
        value = number * TO_G[unit] / TO_G[want]
        per100[pantry] = _tidy(round(value, 6))
    if cal is not None:
        per100["kcal"] = cal
    elif kj is not None:
        per100["kcal"] = _tidy(js_round(kj / KJ_PER_KCAL, 1))
    if "sodium" in per100:
        per100["salt"] = _tidy(js_round(per100["sodium"] * 2.5 / 1000, 2))
    ordered = {key: per100[key] for key in KEY_ORDER if key in per100}
    ordered.update((key, value) for key, value in per100.items() if key not in ordered)
    return ordered


def js_round(value, digits):
    """New food's round (app/newfood.js): 12 significant digits first, then half up."""
    scale = 10 ** digits
    return math.floor(float(f"{value * scale:.12g}") + 0.5) / scale


def _tidy(number):
    return int(number) if float(number).is_integer() else number


def coles_per100(product, notes):
    nutrition = product.get("nutrition") if isinstance(product.get("nutrition"), dict) else {}
    for table in nutrition.get("breakdown") or []:
        if isinstance(table, dict) and re.match(r"per\s*100", str(table.get("title") or ""), re.I):
            return per100_from_rows([(n.get("nutrient"), n.get("value")) for n in table.get("nutrients") or []
                                     if isinstance(n, dict)], notes)
    return None


def woolworths_per100(detail, notes):
    rows = []
    for row in detail.get("NutritionalInformation") or []:
        values = row.get("Values") if isinstance(row, dict) and isinstance(row.get("Values"), dict) else {}
        key = next((k for k in values if re.match(r"quantity per 100", k, re.I)), None)
        if key is not None:
            rows.append((row.get("Name"), values[key]))
    return per100_from_rows(rows, notes) if rows else None


# ── receipts → purchase lines ──────────────────────────────────────
MONEY = re.compile(r"^(-)?\$?\s*(-)?(\d+)(?:\.(\d{1,2}))?$")
QTY = re.compile(r"^qty\s+(\d+)\s*@\s*\$?\s*(\d+(?:\.\d+)?)\s*each$", re.I)
KG = re.compile(r"^(\d+(?:\.\d+)?)\s*kg\s+net\s*@\s*\$?\s*(\d+(?:\.\d+)?)\s*/\s*kg$", re.I)
REDUCED = re.compile(r"^price\s+reduced\s+by\s+\$?\s*(\d+(?:\.\d+)?)(\s*each)?$", re.I)
FOOTER_WHEN = re.compile(r"(\d{1,2}):(\d{2})\s+(\d{1,2})/(\d{1,2})/(\d{4})")
ITEMS = re.compile(r"\((\d+)\s+items?\)", re.I)


def cents(text):
    """Whole cents from '$12.34', '-1.25', '3.50'; None for an empty amount."""
    if text is None or str(text).strip() == "":
        return None
    m = MONEY.match(str(text).strip().replace(",", ""))
    if not m:
        raise ValueError(f"amount {text!r} is not money")
    value = int(m.group(3)) * 100 + int((m.group(4) or "0").ljust(2, "0"))
    return -value if (m.group(1) or m.group(2)) else value


def dollars(c):
    return round(c / 100, 2)


def coles_lines(receipts, problems):
    lines, notes = [], {"receipts": 0, "receipt-level discounts": [], "returned": 0}
    for r, receipt in enumerate(receipts):
        where = f"Coles receipt {r + 1}"
        if not isinstance(receipt, dict) or not isinstance(receipt.get("items"), list):
            problems.append(f"{where}: no list under 'items'")
            continue
        when = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", str(receipt.get("time") or ""))
        if not when or not _real_date(when.group(1)):
            problems.append(f"{where}: time {receipt.get('time')!r} has no date")
            continue
        notes["receipts"] += 1
        paid = 0
        for item in receipt["items"]:
            order = item.get("orderItem") if isinstance(item, dict) else None
            if not isinstance(order, dict) or not isinstance(item.get("id"), (int, str)) \
                    or not isinstance(order.get("itemTotalPrice"), (int, float)):
                problems.append(f"{where}: an item without id, orderItem or itemTotalPrice")
                continue
            total = round(order["itemTotalPrice"] * 100)
            paid += total
            weight = order.get("weight")
            weighed = isinstance(weight, (int, float)) and weight > 0
            quantity = 1 if weighed else int(order.get("quantity") or 0)
            line = {"store": "coles", "date": when.group(1), "time": when.group(2),
                    "receipt": str(receipt.get("transactionId") or receipt.get("orderId")),
                    "text": str(item.get("name") or "").strip(), "product": _int(item["id"]), "match": "id",
                    "quantity": quantity}
            if weighed:
                line["weightKg"] = weight
            line["price"] = dollars(total)
            unit = order.get("unitPrice")
            if isinstance(unit, (int, float)):
                shelf = round(unit * (weight if weighed else quantity) * 100)
                if shelf - total >= 1:
                    line["discount"] = dollars(shelf - total)
            if order.get("return"):
                line["returned"] = True
                notes["returned"] += 1
            lines.append(line)
        total = receipt.get("total")
        if isinstance(total, (int, float)) and abs(round(total * 100) - paid) >= 1:
            notes["receipt-level discounts"].append((when.group(1), dollars(paid - round(total * 100))))
    return lines, notes


def woolworths_lines(receipts, problems):
    lines, notes = [], {"receipts": 0, "not food": 0, "joined": 0, "add up": 0, "do not add up": []}
    for r, entry in enumerate(receipts):
        where = f"Woolworths receipt {r + 1}"
        receipt = entry.get("receipt") if isinstance(entry, dict) else None
        parts = receipt.get("details") if isinstance(receipt, dict) else None
        if not isinstance(parts, list):
            problems.append(f"{where}: no receipt details")
            continue
        kind = {}
        for part in parts:
            if isinstance(part, dict):
                kind.setdefault(part.get("__typename"), part)
        header, items = kind.get("ReceiptDetailsHeader") or {}, kind.get("ReceiptDetailsItems")
        footer, summary = kind.get("ReceiptDetailsFooter") or {}, kind.get("ReceiptDetailsSummary") or {}
        if str(header.get("division") or "").upper().replace(" ", "") in NOT_FOOD_DIVISIONS:
            notes["not food"] += 1
            continue
        when = FOOTER_WHEN.search(str(footer.get("transactionDetails") or ""))
        day = when and f"{when.group(5)}-{int(when.group(4)):02d}-{int(when.group(3)):02d}"
        if not day or not _real_date(day):
            problems.append(f"{where}: the footer {footer.get('transactionDetails')!r} has no date")
            continue
        if not isinstance(items, dict) or not isinstance(items.get("items"), list):
            problems.append(f"{where} ({day}): no item lines")
            continue
        notes["receipts"] += 1
        barcode = (footer.get("barcode") or {}).get("value") if isinstance(footer.get("barcode"), dict) else None
        receipt_id = str(barcode or entry.get("id") or f"{day}-{r}")
        mine = []
        try:
            for item in items["items"]:
                text = str((item or {}).get("description") or "").strip()
                amount = cents((item or {}).get("amount"))
                last = mine[-1] if mine else None
                qty, kg, reduced = QTY.match(text), KG.match(text), REDUCED.match(text)
                if qty or kg or reduced or (amount is not None and amount < 0):
                    if last is None:
                        raise ValueError(f"{text!r} comes before any product line")
                    notes["joined"] += 1
                    if qty or kg:
                        if qty:
                            last["quantity"] = int(qty.group(1))
                        else:
                            last["weightKg"] = float(kg.group(1))
                        n, each = (qty or kg).group(1), (qty or kg).group(2)
                        if amount is not None:
                            last["_cents"] = amount
                        elif last["_cents"] is None:
                            last["_cents"] = round(float(n) * float(each) * 100)
                    elif reduced:
                        off = round(float(reduced.group(1)) * 100) * (last["quantity"] if reduced.group(2) else 1)
                        last["_off"] = last.get("_off", 0) + off
                        if amount:
                            last["_cents"] = (last["_cents"] or 0) + amount
                    else:
                        last["_cents"] = (last["_cents"] or 0) + amount
                        last["_off"] = last.get("_off", 0) - amount
                    continue
                mine.append({"store": "woolworths", "date": day, "time": f"{int(when.group(1)):02d}:{when.group(2)}",
                             "receipt": receipt_id, "text": re.sub(r"^[#^*\s]+", "", text), "quantity": 1,
                             "_cents": amount})
        except ValueError as error:
            problems.append(f"{where} ({day}): {error}")
            continue
        count = sum(line["quantity"] for line in mine)
        paid = sum(line["_cents"] or 0 for line in mine)
        total = summary.get("receiptTotal") if isinstance(summary.get("receiptTotal"), dict) else {}
        try:
            want_paid = cents(total.get("amount"))
        except ValueError:
            want_paid = None
        want_count = ITEMS.search(str(total.get("description") or ""))
        unpriced = [line["text"] for line in mine if line["_cents"] is None]
        if unpriced or want_paid != paid or (want_count and int(want_count.group(1)) != count):
            notes["do not add up"].append(f"{day}: lines {dollars(paid)} for {count} items, receipt "
                                          f"{total.get('amount')} {total.get('description')}"
                                          + (f"; no price for {unpriced}" if unpriced else ""))
        else:
            notes["add up"] += 1
        for line in mine:
            price, off = line.pop("_cents"), line.pop("_off", 0)
            line["price"] = None if price is None else dollars(price)
            if off >= 1:
                line["discount"] = dollars(off)
            lines.append(line)
    return lines, notes


def _real_date(text):
    try:
        Date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _int(value):
    return int(value) if isinstance(value, str) and value.isdigit() else value


# ── matching a Woolworths line to its search results ───────────────
STOP = {"a", "and", "in", "of", "the", "with", "for", "per", "pk", "pack", "packs", "pcs", "pc", "x", "each",
        "ea", "mg", "ml", "kg", "g", "l", "ltr", "litre", "litres"}
PACKAGING = {"bottle", "bottles", "can", "cans", "tin", "tins", "tub", "tubs", "bag", "bags", "jar", "jars", "box",
             "carton", "punnet", "prepacked", "pre", "loose"}
STORE_WORDS = {"woolworths"}
ALIASES = {"ww": ("woolworths",), "xl": ("extra", "large")}
MULT = re.compile(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l)(?![a-z])")
MULT_AFTER = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\s*x\s*(\d+)(?:\s*(?:pk|pack))?(?![a-z])")
AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|gm|g|ml|litres?|ltr|l)(?![a-z])")
COUNT = re.compile(r"(\d+)\s*(pk|pack|pcs|pc|ea)(?![a-z])|\b(each)\b")
LENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(cm|mm|m|metres?|meters?)(?![a-z])")  # read past, never compared


def _plain(text):
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"['`]", "", t)


def sizes(text):
    """({'mass': grams, 'volume': mL, 'count': packs, 'pack': (count, each one's size)}, the text without them).
    A multi-pack keeps its count and each one's size together, so 2 x 125g is not 250g x 2."""
    t = _plain(text)
    found = {"mass": set(), "volume": set(), "count": set(), "pack": set()}

    def put(number, unit):
        unit = "l" if unit.startswith("li") or unit == "ltr" else unit
        grams = {"kg": 1000, "g": 1, "gm": 1}.get(unit)
        if grams:
            found["mass"].add(round(number * grams, 1))
            return "mass", round(number * grams, 1)
        found["volume"].add(round(number * (1000 if unit == "l" else 1), 1))
        return "volume", round(number * (1000 if unit == "l" else 1), 1)
    for m in MULT.finditer(t):
        found["count"].add(int(m.group(1)))
        found["pack"].add((int(m.group(1)), put(float(m.group(2)), m.group(3))))
        put(int(m.group(1)) * float(m.group(2)), m.group(3))
    for m in MULT_AFTER.finditer(t):
        found["count"].add(int(m.group(3)))
        found["pack"].add((int(m.group(3)), put(float(m.group(1)), m.group(2))))
        put(int(m.group(3)) * float(m.group(1)), m.group(2))
    for m in AMOUNT.finditer(t):
        put(float(m.group(1)), m.group(2))
    for m in COUNT.finditer(t):
        found["count"].add(int(m.group(1)) if m.group(1) else 1)
    for pattern in (MULT, MULT_AFTER, AMOUNT, COUNT, LENGTH):
        t = pattern.sub(" ", t)
    return found, t


def words(text):
    _, rest = sizes(text)
    # a word keeps its digits once it has a letter: the brand A2 has to be in the name too
    return [w for w in re.findall(r"[a-z0-9]*[a-z][a-z0-9]*", rest) if len(w) >= 2 and w not in STOP]


def _forms(w):
    out = {w}
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        out.add(w[:-1])
    if len(w) > 4 and w.endswith("es"):
        out.add(w[:-2])
    if len(w) > 4 and w.endswith("ies"):
        out.add(w[:-3] + "y")
    return out


def _in_order(short, long):
    letters = iter(long)
    return all(ch in letters for ch in short)


def _like(line_word, name_word):
    """The receipt's word stands for the store's word."""
    if _forms(line_word) & _forms(name_word):
        return True
    if len(line_word) >= 3 and name_word.startswith(line_word):
        return True
    return len(name_word) > len(line_word) >= 2 and line_word[0] == name_word[0] and _in_order(line_word, name_word)


def _explain(line_words, name_words):
    """Which line words the name explains, and which name words the line explains."""
    line_ok, name_ok = [False] * len(line_words), [False] * len(name_words)

    def hits(word):
        return [j for j, nw in enumerate(name_words) if _like(word, nw)]
    for i, lw in enumerate(line_words):
        found = hits(lw)
        if not found:  # run together on the receipt: NutCorn, BeefRump
            for cut in range(3, len(lw) - 2):
                left, right = hits(lw[:cut]), hits(lw[cut:])
                if left and right:
                    found = left + right
                    break
        if found:
            line_ok[i] = True
            for j in found:
                name_ok[j] = True
    for i in range(len(line_words) - 1):  # split on the receipt: Kit Kat for KitKat
        joined = _forms(line_words[i] + line_words[i + 1])
        for j, nw in enumerate(name_words):
            if joined & _forms(nw):
                line_ok[i] = line_ok[i + 1] = name_ok[j] = True
    return line_ok, name_ok


def _size_fits(line_sizes, name_sizes):
    stated = [k for k in line_sizes if line_sizes[k]]
    if not stated:
        return True, ""
    shared = [k for k in stated if name_sizes[k]]
    differ = [k for k in shared if not line_sizes[k] & name_sizes[k]]
    if differ:
        return False, "its size differs"
    if not shared:
        return False, "it states no size the line can be checked against"
    return True, ""


def judge(line, results):
    """('clear', result, rows) or ('review', why, rows); rows explain every result, best first."""
    line_words = []
    for w in words(line):
        line_words.extend(ALIASES.get(w, (w,)))
    line_sizes, _ = sizes(line)
    rows, seen = [], set()
    for result in results:
        if not isinstance(result, dict) or result.get("Stockcode") in seen:
            continue
        seen.add(result.get("Stockcode"))
        name = " ".join(str(result.get(k)) for k in ("Name", "DisplayName") if result.get(k))
        name_words = list(dict.fromkeys(words(name)))
        brand = set(words(result.get("Brand") or ""))
        name_sizes = {k: set() for k in line_sizes}
        for text in (result.get("PackageSize"), result.get("Name"), result.get("DisplayName")):
            found, _ = sizes(text)
            for k in name_sizes:
                name_sizes[k] |= found[k]
        line_ok, name_ok = _explain(line_words, name_words)
        missing = [w for w, ok in zip(line_words, line_ok) if not ok]
        named = brand & {nw for nw, ok in zip(name_words, name_ok) if ok}
        brand_left = sorted(w for w in brand - STORE_WORDS if w in name_words and not name_ok[name_words.index(w)])
        extra = [nw for nw, ok in zip(name_words, name_ok) if not ok and nw not in PACKAGING
                 and nw not in STORE_WORDS and not (nw in brand and not named)]
        size_ok, size_why = _size_fits(line_sizes, name_sizes)
        why = ([f"the name lacks {', '.join(missing)}"] if missing else []) + ([size_why] if not size_ok else []) \
            + ([f"the line names the brand but not {', '.join(brand_left)}"] if named and brand_left else [])
        rows.append({"result": result, "passes": not why, "why": "; ".join(why), "extra": extra})
    rows.sort(key=lambda row: (not row["passes"], len(row["extra"])))
    passing = [row for row in rows if row["passes"]]
    if not results:
        return "review", "the search found nothing", rows
    if not line_words:
        return "review", "the line has no words to match", rows
    if not passing:
        return "review", "no result has every word of the line and its size", rows
    best = passing[0]
    if len(passing) > 1 and len(passing[1]["extra"]) == len(best["extra"]):
        tied = [row for row in passing if len(row["extra"]) == len(best["extra"])]
        return "review", f"{len(tied)} results fit equally well", rows
    if len(best["extra"]) > MAX_EXTRA_WORDS:
        return "review", f"the closest result adds {len(best['extra'])} words: {', '.join(best['extra'])}", rows
    return "clear", best["result"], rows


def _search_for(text, search):
    if text in search:
        return search[text]
    folded = {re.sub(r"\s+", " ", k).strip().casefold(): v for k, v in search.items()}
    return folded.get(re.sub(r"\s+", " ", text).strip().casefold())


# ── review answers ─────────────────────────────────────────────────
def answer_of(answer):
    """'none', the Stockcode, or None when the answer cannot be read."""
    if isinstance(answer, str) and answer.strip().casefold() == "none":
        return "none"
    if isinstance(answer, int) and not isinstance(answer, bool) or (isinstance(answer, str) and answer.strip().isdigit()):
        return int(answer)
    return None


def answers_given(review):
    """{line text: (the entry whose answer counts, the line's other answered entries)}: the last answer that can be
    read, else the last one given. The others are dropped from the review file."""
    given = {}
    for entry in review.get("lines") or []:
        if isinstance(entry, dict) and entry.get("answer") not in (None, ""):
            given.setdefault(str(entry.get("line") or ""), []).append(entry)
    out = {}
    for text, entries in given.items():
        keep = ([e for e in entries if answer_of(e["answer"]) is not None] or entries)[-1]
        out[text] = (keep, [e for e in entries if e is not keep])
    return out


def read_answers(review, problems):
    """{line text: stockcode or 'none'} from the review file's entries that carry an answer."""
    answers = {}
    for text, (keep, dropped) in answers_given(review).items():
        answer = answer_of(keep["answer"])
        if answer is None:
            problems.append(f"review answer {keep['answer']!r} for {text!r} is not a Stockcode or \"none\"; not used")
        else:
            answers[text] = answer
        if dropped:
            problems.append(f"review file answers {text!r} more than once: {keep['answer']!r} counts and is kept, "
                            f"{', '.join(repr(e['answer']) for e in dropped)} dropped")
    return answers


# ── catalogue ──────────────────────────────────────────────────────
def build(inputs, review):
    """Everything this run produces, as data; nothing is written here."""
    problems, label_notes = [], {}
    coles_receipts, coles_products, ww_receipts, ww_products = (inputs[name] for name in INPUTS)
    c_lines, c_notes = coles_lines(coles_receipts if isinstance(coles_receipts, list) else [], problems)
    w_lines, w_notes = woolworths_lines(ww_receipts if isinstance(ww_receipts, list) else [], problems)
    search = ww_products.get("search") if isinstance(ww_products.get("search"), dict) else {}
    details = ww_products.get("details") if isinstance(ww_products.get("details"), dict) else {}
    answers = read_answers(review, problems)

    # Woolworths: one decision per distinct line text
    decisions = {}
    for text in dict.fromkeys(line["text"] for line in w_lines):
        found = _search_for(text, search)
        results = (found or {}).get("products") if isinstance(found, dict) else None
        if text in answers:
            decisions[text] = {"how": "none" if answers[text] == "none" else "answer",
                               "stockcode": None if answers[text] == "none" else answers[text], "rows": []}
            continue
        if results is None:
            decisions[text] = {"how": "review", "why": "no search was captured for this line", "rows": []}
            continue
        verdict, what, rows = judge(text, results)
        if verdict == "clear":
            decisions[text] = {"how": "clear", "stockcode": what.get("Stockcode"), "rows": rows}
        else:
            decisions[text] = {"how": "review", "why": what, "rows": rows}
    for line in w_lines:
        d = decisions[line["text"]]
        line["product"] = d.get("stockcode")
        line["match"] = d["how"]

    # products and their catalogue items
    to_capture = {"colesProductIds": [], "woolworthsStockcodes": [], "woolworthsLines": []}
    products, skipped = {}, []
    for line in c_lines + w_lines:
        if line["product"] is None:
            continue
        key = (line["store"], line["product"])
        p = products.setdefault(key, {"lines": 0, "last": ""})
        p["lines"] += 1
        p["last"] = max(p["last"], line["date"])
    for (store, pid), p in sorted(products.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if store == "coles":
            raw = coles_products.get(str(pid)) if isinstance(coles_products, dict) else None
            if not isinstance(raw, dict) or raw.get("missing") or raw.get("status") not in (None, 200):
                to_capture["colesProductIds"].append(pid)
                p["state"] = "not captured"
                continue
            barcode, name, brand, size = raw.get("gtin"), raw.get("name"), raw.get("brand"), raw.get("size")
            p["name"] = name
            per100 = coles_per100(raw, label_notes)
        else:
            raw = details.get(str(pid))
            if not isinstance(raw, dict) or raw.get("error") or raw.get("status") not in (None, 200) \
                    or not isinstance(raw.get("Product"), dict):
                to_capture["woolworthsStockcodes"].append(pid)
                p["state"] = "not captured"
                continue
            product = raw["Product"]
            barcode, name, brand, size = (product.get(k) for k in ("Barcode", "Name", "Brand", "PackageSize"))
            p["name"] = name
            per100 = woolworths_per100(raw, label_notes)
        barcode = str(barcode).strip() if barcode not in (None, "") else ""
        why = ("no barcode" if not barcode.isdigit() else "no per 100 g table" if per100 is None
               else "no energy on the label" if "kcal" not in per100 else None)
        p["barcode"] = barcode or None
        if why:
            p["state"] = why
            skipped.append({"store": store, "product": pid, "name": name, "barcode": barcode or None, "why": why})
            continue
        item = {"barcode": barcode, "name": str(name or "").strip()}
        if isinstance(brand, str) and brand.strip():
            item["brand"] = brand.strip()
        if isinstance(size, str) and size.strip():
            item["size"] = size.strip()
        item["store"] = store
        item["per100"] = per100
        p["item"] = item
        p["state"] = "item"
    for text, d in decisions.items():
        if d["how"] == "review" and d.get("why") == "no search was captured for this line":
            to_capture["woolworthsLines"].append(text)

    by_code, both = {}, 0
    for key, p in products.items():
        if "item" not in p:
            continue
        code = p["item"]["barcode"].lstrip("0") or "0"
        held = by_code.get(code)
        if held is None:
            by_code[code] = (key, p)
            continue
        both += held[0][0] != key[0]
        if (p["last"], key[0]) > (held[1]["last"], held[0][0]):
            by_code[code] = (key, p)
    catalogue = sorted((p["item"] for _, p in by_code.values()), key=lambda i: (i["store"], i["name"].casefold(), i["barcode"]))
    for lines in (c_lines, w_lines):
        for line in lines:
            p = products.get((line["store"], line["product"])) if line["product"] is not None else None
            if p and p.get("name"):
                line["name"] = p["name"]
            if p and p.get("barcode"):
                line["barcode"] = p["barcode"]
        lines[:] = [{k: line[k] for k in LINE_FIELDS if k in line} for line in lines]

    return {"problems": problems, "coles": (c_lines, c_notes), "woolworths": (w_lines, w_notes),
            "decisions": decisions, "products": products, "catalogue": catalogue, "skipped": skipped,
            "to_capture": to_capture, "label_notes": label_notes, "both_stores": both,
            "same_barcode": sum(1 for p in products.values() if "item" in p) - len(catalogue)}


def review_file(old, decisions, w_lines):
    """The new review file, one entry per line: every unclear line first (most bought first), then every other
    line's answer (answers_given picks it)."""
    given = {text: keep for text, (keep, _) in answers_given(old).items()}
    bought = {}
    for line in w_lines:
        b = bought.setdefault(line["text"], {"bought": 0, "last": ""})
        b["bought"] += 1
        b["last"] = max(b["last"], line["date"])
    open_lines = []
    for text, d in decisions.items():
        if d["how"] != "review":
            continue
        candidates = []
        for row in d["rows"][:5]:
            r = row["result"]
            c = {"stockcode": r.get("Stockcode"), "name": r.get("DisplayName") or r.get("Name"),
                 "barcode": r.get("Barcode")}
            c["fits"] = "yes" if row["passes"] else row["why"]
            candidates.append(c)
        entry = {"line": text, "answer": None, "why": d["why"], **bought[text], "candidates": candidates}
        bad = given.pop(text, None)  # an answer that could be read would have decided the line
        if bad is not None:
            entry["answer"] = bad["answer"]
            entry["why"] = (f"the answer {json.dumps(bad['answer'], ensure_ascii=False)} is not a Stockcode or "
                            f"\"none\", so it is not used; {d['why']}")
            for key, value in bad.items():
                entry.setdefault(key, value)
        open_lines.append(entry)
    open_lines.sort(key=lambda e: (-e["bought"], e["line"]))
    return {"about": "Woolworths receipt lines whose product is not clear (tools/catalogue.py explains 'clear'). "
                     "Set \"answer\" to the Stockcode of the product bought (a candidate's, or any other from "
                     "woolworths.com.au) or to \"none\" when the line is not a product to catalogue; leave null to "
                     "decide later. The next run uses every answer and keeps it here, one entry per line. To "
                     "correct a clear match, add {\"line\": <the line>, \"answer\": <Stockcode>}.",
            "lines": open_lines + list(given.values())}


def mapping_file(decisions, details):
    out = {}
    for text in sorted(decisions):
        d = decisions[text]
        code = d.get("stockcode")
        product = (details.get(str(code)) or {}).get("Product") if code is not None else None
        out[text] = {"how": d["how"], "stockcode": code,
                     "name": (product or {}).get("DisplayName") or (product or {}).get("Name")}
    return {"about": "Every Woolworths receipt line text and the product it was given: how is clear (matched by "
                     "the rule in tools/catalogue.py), answer (woolworths-review.json), none (answered: not a "
                     "product) or review (not decided).", "lines": out}


# ── report ─────────────────────────────────────────────────────────
def report(result, folder, out, review_count, merged):
    c_lines, c_notes = result["coles"]
    w_lines, w_notes = result["woolworths"]
    decisions, products, label = result["decisions"], result["products"], result["label_notes"]
    how = {}
    for d in decisions.values():
        how[d["how"]] = how.get(d["how"], 0) + 1
    w_auto = sum(1 for line in w_lines if line["match"] == "clear")
    distinct = len(decisions)
    states = {}
    for p in products.values():
        states[p["state"]] = states.get(p["state"], 0) + 1
    per_store = {s: sum(1 for k in products if k[0] == s) for s in STORES}
    items = {s: sum(1 for i in result["catalogue"] if i["store"] == s) for s in STORES}
    with_code = sum(1 for p in products.values() if str(p.get("barcode") or "").isdigit())
    discounts = c_notes["receipt-level discounts"]
    tc = result["to_capture"]
    pct = lambda a, b: f"{100 * a / b:.0f} %" if b else "n/a"  # noqa: E731
    lines = [f"Pantry catalogue from {folder}",
             f"  receipts:          Coles {c_notes['receipts']}, Woolworths {w_notes['receipts']}"
             + (f" ({w_notes['not food']} BIG W receipts skipped: not food)" if w_notes["not food"] else ""),
             f"  purchase lines:    Coles {len(c_lines)}, Woolworths {len(w_lines)} "
             f"({w_notes['joined']} quantity, weight and discount lines joined into their product line)",
             f"  receipts checked:  Woolworths {w_notes['add up']} of {w_notes['receipts']} add up to their total and "
             f"item count; Coles {c_notes['receipts'] - len(discounts)} of {c_notes['receipts']} add up"
             + (f"; receipt-level discounts on no line: {len(discounts)} receipt{'' if len(discounts) == 1 else 's'}, "
                f"${sum(d for _, d in discounts):.2f}" if discounts else ""),
             f"  products:          {len(products)} (Coles {per_store['coles']}, Woolworths {per_store['woolworths']}); "
             f"{states.get('not captured', 0)} not captured yet",
             f"  Woolworths lines:  {distinct} distinct texts: {how.get('clear', 0)} clear, {how.get('answer', 0)} "
             f"answered, {how.get('none', 0)} answered none, {how.get('review', 0)} in review",
             f"  auto-match rate:   {pct(how.get('clear', 0), distinct)} of distinct Woolworths lines "
             f"({how.get('clear', 0)}/{distinct}); {pct(w_auto, len(w_lines))} of Woolworths purchase lines "
             f"({w_auto}/{len(w_lines)}); Coles lines carry their product id",
             f"  with a barcode:    {with_code} products",
             f"  catalogue items:   {len(result['catalogue'])} (Coles {items['coles']}, Woolworths {items['woolworths']})"
             + (f"; {result['same_barcode']} products share a barcode with another ({result['both_stores']} across "
                f"the two stores), kept once" if result["same_barcode"] else ""),
             f"  skipped:           {len(result['skipped'])} products with no item: "
             + ", ".join(f"{states.get(k, 0)} {k}" for k in ("no barcode", "no per 100 g table", "no energy on the label")),
             f"  review items:      {review_count} lines waiting for an answer in {folder / REVIEW}",
             f"  still to capture:  {len(tc['colesProductIds'])} Coles product pages, {len(tc['woolworthsStockcodes'])} "
             f"Woolworths product details, {len(tc['woolworthsLines'])} Woolworths line searches (to-capture.json)",
             f"  label values absent: {label.get('dash', 0)} given as '-', {label.get('below', 0)} given as "
             f"'less than', {label.get('blank', 0)} blank, {len(label.get('unreadable values', []))} unreadable"
             + (f" ({'; '.join(label['unreadable values'][:5])})" if label.get("unreadable values") else "")]
    if label.get("rows not used"):
        lines.append(f"  label rows not used: {', '.join(sorted(label['rows not used']))}")
    for d in w_notes["do not add up"][:10]:
        lines.append(f"  DOES NOT ADD UP: {d}")
    for p in result["problems"][:20]:
        lines.append(f"  PROBLEM: {p}")
    if merged:
        lines.append(f"  merged:            {merged}")

    clear = sorted({line["text"]: line for line in w_lines if line["match"] in ("clear", "answer")}.values(),
                   key=lambda line: line["text"])
    pick = random.Random(20261021).sample(clear, min(SAMPLE, len(clear)))
    coles_pairs = sorted({line["text"]: line for line in c_lines if line.get("name")}.values(),
                         key=lambda line: line["text"])
    pick += random.Random(20261021).sample(coles_pairs, min(SAMPLE - len(pick), len(coles_pairs)))
    lines.append("")
    lines.append(f"Sample: {len(pick)} receipt line -> product pairs to judge (Woolworths matches first)")
    for n, line in enumerate(pick, 1):
        p = products.get((line["store"], line["product"]), {})
        state = "catalogue item" if p.get("state") == "item" else p.get("state", "")
        lines.append(f"  {n:2}. {line['store']:<10} {line['match']:<6} \"{line['text']}\" -> {line['product']} "
                     f"{line.get('name') or '(details not captured)'} [{line.get('barcode') or 'no barcode'}; {state}]")
    lines.append("")
    lines.append(f"wrote {out / 'catalogue.json'} ({len(result['catalogue'])} items), purchases.json, skipped.json, "
                 f"to-capture.json, report.txt; {folder / REVIEW}, {folder / MAPPING}")
    return lines


# ── merge into the data document ───────────────────────────────────
def _skip_ws(text, i):
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def members(text):
    """{key: (start, end)} of each top-level value, and the end of the last value, read from the JSON text."""
    decoder = json.JSONDecoder()
    i = _skip_ws(text, 0)
    if i >= len(text) or text[i] != "{":
        raise ValueError("the document is not a JSON object")
    i = _skip_ws(text, i + 1)
    spans, last = {}, i
    if i < len(text) and text[i] == "}":
        return spans, i, i
    while True:
        if i >= len(text) or text[i] != '"':
            raise ValueError("the document is not a JSON object")
        key, i = json.decoder.scanstring(text, i + 1)
        i = _skip_ws(text, i)
        if i >= len(text) or text[i] != ":":
            raise ValueError("the document is not a JSON object")
        start = _skip_ws(text, i + 1)
        _, end = decoder.raw_decode(text, start)
        if key in spans:
            raise ValueError(f"the document has '{key}' twice")
        spans[key], last = (start, end), end
        i = _skip_ws(text, end)
        if i < len(text) and text[i] == ",":
            i = _skip_ws(text, i + 1)
            continue
        if i < len(text) and text[i] == "}":
            if text[i + 1:].strip():
                raise ValueError("text follows the document")
            return spans, last, i
        raise ValueError("the document is not a JSON object")


def merged_text(text, catalogue):
    """The document text with only its catalogue replaced (or added after the last member)."""
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    body = text[len(bom):]
    doc = json.loads(body)
    if not isinstance(doc, dict):
        raise ValueError("the document is not a JSON object")
    if doc.get("version") not in KNOWN_VERSIONS or isinstance(doc.get("version"), bool):
        raise ValueError(f"its version is {doc.get('version')!r}; this tool knows version "
                         f"{', '.join(map(str, KNOWN_VERSIONS))} only")
    if not isinstance(doc.get("foods"), list) or not isinstance(doc.get("entries"), list) or not isinstance(doc.get("settings"), dict):
        raise ValueError("it has no foods, entries and settings, so it is not a Pantry data document")
    spans, last, _ = members(body)
    value = json.dumps(catalogue, ensure_ascii=False, separators=(",", ":"))
    if "catalogue" in spans:
        start, end = spans["catalogue"]
        new = body[:start] + value + body[end:]
    else:
        new = body[:last] + (',"catalogue":' if spans else '"catalogue":') + value + body[last:]
    check = json.loads(new)
    want = {**doc, "catalogue": catalogue}
    if check != want or [k for k in check if k != "catalogue"] != [k for k in doc if k != "catalogue"]:
        raise ValueError("the merged text does not read back as the document with the new catalogue")
    return bom + new, len(doc.get("catalogue") or []) if isinstance(doc.get("catalogue"), list) else None


# ── files ──────────────────────────────────────────────────────────
def refuse(path):
    """Why personal data must not be written to path, or None when it may be."""
    path = Path(path).resolve()
    if any(part.casefold() == "references" for part in path.parent.parts):
        return "it is inside references/, which this tool never writes"
    if path.is_dir():
        return "it is a directory"
    anchor = path.parent
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    env.update(LC_ALL="C", LANGUAGE="C")
    try:
        top = subprocess.run(["git", "-C", str(anchor), "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, env=env)
        if top.returncode != 0:
            if "not a git repository" in top.stderr:
                return None
            return f"git could not place it in a work tree: {top.stderr.strip()}"
        root = Path(top.stdout.strip()).resolve()
        if root != ROOT and not (root / "app" / "core.js").is_file():
            return None  # another repository, such as the Pantry-Data clone a merge writes to
        relative = path.relative_to(root).as_posix()
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative],
                                 capture_output=True, text=True, env=env)
    except (OSError, ValueError) as error:
        return f"git could not check it ({error})"
    if ignored.returncode == 0:
        return None
    if ignored.returncode == 1:
        return f"it is inside the Pantry repo {root} and git does not ignore it, so the purchases could be committed"
    return f"git check-ignore failed: {ignored.stderr.strip()}"


def write_text(path, text):
    """Written whole or not at all: a temp file next to it, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def dump(value, indent=1):
    return json.dumps(value, ensure_ascii=False, indent=indent) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build Pantry's barcode catalogue from Coles and Woolworths purchases.")
    parser.add_argument("--purchases", type=Path, default=ROOT / ".tmp" / "purchases",
                        help="the raw purchases folder (default .tmp/purchases); the review file lives here too")
    parser.add_argument("--out", type=Path, default=ROOT / ".tmp" / "catalogue",
                        help="where the catalogue, purchase lines and report go (default .tmp/catalogue)")
    parser.add_argument("--merge", type=Path, help="a pantry-data.json whose catalogue is replaced")
    args = parser.parse_args(argv)
    folder, out = args.purchases.resolve(), args.out.resolve()

    targets = [out / n for n in ("catalogue.json", "purchases.json", "skipped.json", "to-capture.json", "report.txt")]
    targets += [folder / REVIEW, folder / MAPPING] + ([args.merge.resolve()] if args.merge else [])
    for target in targets:
        reason = refuse(target)
        if reason:
            print(f"REFUSED {target}: {reason}. Nothing written.", file=sys.stderr)
            return 2

    inputs = {}
    for name in INPUTS:
        try:
            inputs[name] = json.loads((folder / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            print(f"REFUSED: cannot read {folder / name}: {error}. Nothing written.", file=sys.stderr)
            return 1
    for name, kind in zip(INPUTS, (list, dict, list, dict)):
        if not isinstance(inputs[name], kind):
            print(f"REFUSED: {folder / name} is not a JSON {kind.__name__}. Nothing written.", file=sys.stderr)
            return 1
    review = {}
    if (folder / REVIEW).exists():
        try:
            review = json.loads((folder / REVIEW).read_text(encoding="utf-8-sig"))
            if not isinstance(review, dict) or not isinstance(review.get("lines", []), list):
                raise ValueError("it has no list under 'lines'")
        except (OSError, ValueError) as error:
            print(f"REFUSED: cannot read the answers in {folder / REVIEW}: {error}. Fix it by hand; nothing written, "
                  "so no answer is lost.", file=sys.stderr)
            return 1

    result = build(inputs, review)
    merge_text, merged = None, ""
    if args.merge:
        try:
            with open(args.merge, encoding="utf-8", newline="") as f:
                original = f.read()
            merge_text, before = merged_text(original, result["catalogue"])
        except (OSError, ValueError) as error:
            print(f"REFUSED --merge {args.merge}: {error}. Nothing written.", file=sys.stderr)
            return 1
        merged = (f"{args.merge}: catalogue {'added' if before is None else f'replaced (it held {before})'} with "
                  f"{len(result['catalogue'])} items; every other member byte for byte as it was")

    w_lines = result["woolworths"][0]
    new_review = review_file(review, result["decisions"], w_lines)
    review_count = sum(1 for d in result["decisions"].values() if d["how"] == "review")
    text = "\n".join(report(result, folder, out, review_count, merged)) + "\n"
    purchases = {"about": "One line per product line of a receipt (tools/catalogue.py explains the fields); built "
                          + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "lines": sorted(result["coles"][0] + w_lines, key=lambda line: (line["date"], line["time"], line["store"]))}
    write_text(out / "catalogue.json", dump(result["catalogue"]))
    write_text(out / "purchases.json", dump(purchases))
    write_text(out / "skipped.json", dump(result["skipped"]))
    write_text(out / "to-capture.json", dump(result["to_capture"]))
    write_text(out / "report.txt", text)
    write_text(folder / REVIEW, dump(new_review, indent=2))
    write_text(folder / MAPPING, dump(mapping_file(result["decisions"], inputs["woolworths-products.json"].get("details") or {})))
    if merge_text is not None:
        write_text(args.merge.resolve(), merge_text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())

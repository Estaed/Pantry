"""Checks for Task-03 and Task-08: the meal list and the gram sheet (app/log.js) and the food drawings (app/drawings.js);
Task-08's checks (11-16) are logging the MyNetDiary way: the meal so far, ticks (and how they meet the + and the sheet),
yesterday's meal, the instant +, the sheet's keys and chips, and the list at his text size 1.0. Those that need
yesterday drive the page clock.

Run from the repo root: python tests/test_log.py   (exit 0 = no FAIL; prints PASS, FAIL or SKIP per check)

Reuses the gate's server and phone from tests/acceptance.py: 360 x 780, touch, text at 150 %, Darwin, the clock at
07:00 on 2026-10-20. Screens are reached by route (Pantry.go), never through Today. Synthetic entries are built in
the page to exercise a rule; the committed fixture is the three real days of tests/fixtures/mynetdiary-slice.json,
turned into a document by tools/import_mynetdiary.py in memory. The full MyNetDiary history is personal data and
never enters the repo: when it is on this machine (MYNETDIARY_SOURCE, references/, or the main repo's references/)
it is read in memory for the ranking and drawing checks and every food is printed with its drawing for review;
otherwise those checks SKIP and say so.
"""
import collections
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import acceptance as A  # noqa: E402
import import_mynetdiary as importer  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = HERE.parent
FIXTURE = ROOT / "tests" / "fixtures" / "mynetdiary-slice.json"
HISTORY_NAME = "mynetdiary-history-2026-10-20.json"
HISTORY = [Path(p) for p in (os.environ.get("MYNETDIARY_SOURCE"), ROOT / "references" / HISTORY_NAME,
                             Path("D:/Projects/Pantry/references") / HISTORY_NAME) if p]
CHICKEN, TZATZIKI, RICE, BUTTER, POTATO = (s[0] for s in A.STARTER)
ROY = "v1.L1aeZ4jJ7z9D03z0RtXaO4j2DZBMQBEm*Qx0u8GJHBbq1MMvKI1jOH55HtE="
LOAF_NAME = "High Protein 85% Lower Carb Mixed Seeds Loaf"
TODAY = A.NOW.date()
CHECK = A.check
URL = None          # the gate's server for this run, set in main()

ROWS_JS = """() => [...document.querySelectorAll('[data-screen] .log-row')].map(r => ({
  id: r.dataset.id, name: r.querySelector('.name').textContent, sub: r.querySelector('.sub').textContent,
  kcal: r.querySelector('.k').textContent, label: r.querySelector('.log-open').getAttribute('aria-label') }))"""


def fixture_doc():
    return importer.build_document(json.loads(FIXTURE.read_text(encoding="utf-8")))


def history_source():
    for path in HISTORY:
        if path.is_file():
            return path, json.loads(path.read_text(encoding="utf-8-sig"))
    return None, None


def entry(i, food, date, meal, amount, grams, kcal=1.0):
    return {"id": f"t{i}", "date": date, "meal": meal, "foodId": food, "amount": amount, "grams": grams, "totals": {"kcal": kcal}}


def load(page, doc):
    page.evaluate("doc => Pantry.change(() => doc)", doc)


def add_entries(page, entries):
    page.evaluate("es => Pantry.change(d => { d.entries.push(...es); })", entries)


def go(page, *args):
    page.evaluate("a => Pantry.go(...a)", list(args))
    page.wait_for_selector(f'[data-screen="{args[0]}"]')


def rows(page):
    return page.evaluate(ROWS_JS)


def stored(page):
    return page.evaluate("() => Pantry.doc()")


def sheet(page):
    return page.locator(".log-layer:not(.log-out) .log-sheet")


def row_button(page, food_id, act):
    return page.locator(f'.log-row[data-id={json.dumps(food_id)}] [data-act="{act}"]')


def totals(page, food_id, grams):
    return page.evaluate("([id, g]) => Pantry.totals(Pantry.doc().foods.find(f => f.id === id), g)", [food_id, grams])


def fmt(page, n):
    return page.evaluate("n => Pantry.fmt(n)", n)


def screen_within(page, name, ms=3000):
    """True when the named screen shows within ms; a check then fails by name instead of a 30 s timeout."""
    try:
        page.wait_for_selector(f'[data-screen="{name}"]', timeout=ms)
        return True
    except Exception:  # noqa: BLE001 - Playwright's TimeoutError; the check reports it
        return False


def err_text(page):
    err = page.locator("[data-screen] .err")
    return err.inner_text().strip() if err.is_visible() else ""


# ── 1. Frequent ranks by count at the meal in 90 days; the usual amount is the most typed, not the latest ──
def check_ranking(browser, errors):
    ctx, page = A.phone(browser, errors, "ranking")
    A.open_today(page, URL)
    es = [entry(i, CHICKEN, f"2026-10-0{i}", "dinner", "350 g", 350) for i in range(1, 6)]
    es.append(entry(6, CHICKEN, "2026-10-19", "dinner", "375 g", 375))                       # the latest, typed once
    es += [entry(10 + i, TZATZIKI, f"2026-10-1{i}", "dinner", "125 g", 125) for i in range(3)]
    es.append(entry(20, RICE, "2026-10-15", "dinner", "100 g", 100))
    es.append(entry(21, CHICKEN, "2026-10-18", "breakfast", "120 g", 120))                    # his breakfast amount
    es += [entry(30 + i, POTATO, f"2026-10-0{i + 1}", "lunch", "500 g", 500) for i in range(9)]   # other meal
    es += [entry(40 + i, BUTTER, f"2026-06-0{i + 1}", "dinner", "5 g", 5) for i in range(8)]     # older than 90 days
    add_entries(page, es)
    go(page, "add", "dinner")
    got = rows(page)
    CHECK("Dinner lists the foods logged at dinner in 90 days, most often first (5 + 1, 3, 1), no other meal or older day",
          [r["id"] for r in got] == [CHICKEN, TZATZIKI, RICE], [(r["name"], r["sub"]) for r in got])
    first = got[0] if got else {}
    kcal350 = fmt(page, totals(page, CHICKEN, 350)["kcal"])
    CHECK("the first row says 350 g, the amount typed most often, not the latest 375 g, with its kcal",
          first.get("sub") == "350 g" and first.get("kcal") == kcal350, first)
    CHECK("each row's button name starts with the food name", all(r["label"].startswith(r["name"]) for r in got), [r["label"] for r in got])
    row_button(page, CHICKEN, "open").click()
    sheet(page).wait_for()
    chips = page.locator(".log-chip").all_inner_texts()
    CHECK("the gram sheet offers 350 g first, its chips are the usual amounts with no use count (no '5×')",
          page.get_by_label("Grams").input_value() == "350" and [c.replace("\n", "") for c in chips] == ["350 g", "375 g"]
          and page.locator('.log-chip[aria-pressed="true"]').inner_text() == "350 g"
          and all(page.locator(".log-chip").nth(i).get_attribute("aria-label") is None for i in range(len(chips))), chips)
    grams = page.get_by_label("Grams")
    page.get_by_role("radio", name="Breakfast").check()
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    CHECK("the Breakfast radio brings breakfast's usual grams and chips (120 g), not dinner's",
          chips == ["120 g"] and grams.input_value() == "120" and page.get_by_role("button", name="Add to breakfast").count() == 1,
          (chips, grams.input_value()))
    grams.fill("200")
    page.get_by_role("radio", name="Dinner").check()
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    CHECK("an amount he typed stays when the meal changes, and the chips follow the meal",
          grams.input_value() == "200" and chips == ["350 g", "375 g"], (chips, grams.input_value()))
    ctx.close()


# ── 2. the row's + logs the usual amount at once, the list stays, Undo deletes like any delete ──
def check_plus(browser, errors):
    ctx, page = A.phone(browser, errors, "plus")
    A.open_today(page, URL)
    add_entries(page, [entry(i, CHICKEN, f"2026-10-0{i}", "dinner", "350 g", 350) for i in range(1, 4)]
                + [entry(9, TZATZIKI, "2026-10-09", "dinner", "125 g", 125)])
    go(page, "add", "dinner", "2026-08-08")
    before = rows(page)
    n = len(stored(page)["entries"])
    want = totals(page, CHICKEN, 350)
    row_button(page, CHICKEN, "plus").click()
    page.locator("#toast .toast").wait_for()
    doc = stored(page)
    new = [e for e in doc["entries"] if e["id"] not in {f"t{i}" for i in (1, 2, 3, 9)}]
    e = new[0] if len(new) == 1 else {}
    CHECK("+ logs one entry: the usual 350 g, its totals at log time, the route's date and meal",
          len(doc["entries"]) == n + 1 and e.get("foodId") == CHICKEN and e.get("amount") == "350 g" and e.get("grams") == 350
          and e.get("date") == "2026-08-08" and e.get("meal") == "dinner" and e.get("totals") == want, e)
    CHECK("the list stays, in the same order", page.locator('[data-screen="add"]').count() == 1
          and [r["id"] for r in rows(page)] == [r["id"] for r in before])
    toast = page.locator("#toast .toast").inner_text()
    CHECK("the toast names what was added where, with Undo and the food's drawing",
          "350 g of Chicken Breast Raw added to dinner on 8 Aug" in toast and "Undo" in toast
          and page.locator("#toast .toast-art svg").count() == 1, toast)
    page.evaluate(f"() => Pantry.change(d => {{ d.foods.find(f => f.id === {json.dumps(CHICKEN)}).per100.kcal = 999; }})")
    kept = next((x for x in stored(page)["entries"] if x["id"] == e.get("id")), {})
    CHECK("the entry keeps its totals when the food changes later", kept.get("totals") == want, kept)
    page.get_by_role("button", name="Undo").click()
    doc = stored(page)
    removed = [r for r in doc.get("removed", []) if r["id"] == e.get("id")]
    stamp_ok = bool(removed) and datetime.datetime.fromisoformat(removed[0]["at"].replace("Z", "+00:00")).tzinfo is not None
    CHECK("Undo removes the entry and adds its removed line { id, at }",
          all(x["id"] != e.get("id") for x in doc["entries"]) and len(removed) == 1 and stamp_ok, doc.get("removed"))
    row_button(page, CHICKEN, "plus").click()
    page.locator("#toast .toast").wait_for()
    page.wait_for_selector("#toast .toast", state="detached", timeout=7000)
    CHECK("after the toast is gone, the entry stays", len(stored(page)["entries"]) == n + 1)
    ctx.close()


# ── 3. the gram sheet: live kcal, chips, plain errors, back gesture, Add to <meal> ──
def check_sheet(browser, errors):
    ctx, page = A.phone(browser, errors, "sheet")
    A.open_today(page, URL)
    add_entries(page, [entry(1, CHICKEN, "2026-10-01", "dinner", "350 g", 350), entry(2, CHICKEN, "2026-10-02", "dinner", "350 g", 350),
                       entry(3, CHICKEN, "2026-10-03", "dinner", "375 g", 375)])
    go(page, "add", "dinner")
    row_button(page, CHICKEN, "open").click()
    sheet(page).wait_for()
    grams = page.get_by_label("Grams")
    kcal = page.locator('[data-test="portion-kcal"]')
    CHECK("tapping a row opens the gram sheet over the list on the same screen",
          page.locator('[data-screen="add"] .log-sheet').count() == 1 and grams.input_value() == "350")
    grams.fill("375")
    want = fmt(page, totals(page, CHICKEN, 375)["kcal"])
    CHECK(f"typing 375 shows Pantry.totals(food, 375).kcal rounded ({want})", kcal.inner_text().strip() == want, kcal.inner_text())
    grams.fill("300")
    page.locator(".log-chip", has_text="375 g").click()
    CHECK("a chip sets the grams", grams.input_value() == "375"
          and page.locator('.log-chip[aria-pressed="true"]').inner_text().startswith("375 g"), grams.input_value())
    n = len(stored(page)["entries"])
    said = {}
    for typed in ("", "0", "abc"):
        grams.fill(typed)
        page.get_by_role("button", name="Add to dinner").click()
        said[typed] = err_text(page)
    CHECK("an empty, zero or non-number amount says so in words and logs nothing",
          "Type the grams" in said[""] and "more than 0" in said["0"] and "not a number" in said["abc"]
          and len(stored(page)["entries"]) == n and page.locator('[data-screen="add"]').count() == 1, said)
    page.go_back()
    page.wait_for_selector(".log-layer:not(.log-out)", state="detached")
    CHECK("the phone's back gesture closes the sheet and stays on the list",
          page.locator('[data-screen="add"] .log-row').count() > 0 and sheet(page).count() == 0)
    row_button(page, CHICKEN, "open").click()
    sheet(page).wait_for()
    page.get_by_role("radio", name="Lunch").check()
    lunch = page.get_by_role("button", name="Add to lunch").count() == 1
    page.get_by_role("radio", name="Dinner").check()
    grams.fill("375")
    page.get_by_role("button", name="Add to dinner").click()
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    CHECK("the meal radios rename the button; Add to dinner logs today's dinner and returns to Today",
          lunch and e["meal"] == "dinner" and e["date"] == TODAY.isoformat() and e["amount"] == "375 g" and e["grams"] == 375
          and e["totals"] == totals(page, CHICKEN, 375) and len(stored(page)["entries"]) == n + 1, e)
    toast = page.locator("#toast .toast")
    CHECK("Today shows the toast with Undo", toast.count() == 1 and "375 g of Chicken Breast Raw added to dinner" in toast.inner_text(), toast.count())
    page.go_back()
    page.wait_for_selector('[data-screen] .log-row')
    where = page.evaluate("location.hash")
    armed = sheet(page).count()
    page.go_back()
    home = screen_within(page, "today")
    CHECK("Back from Today after Add shows the dinner list, not the sheet armed again; one more Back is Today",
          where == "#/add/dinner" and armed == 0 and home and len(stored(page)["entries"]) == n + 1, (where, armed, home))
    ctx.close()


# ── 4. a food with only servings ──
def check_servings(browser, errors):
    ctx, page = A.phone(browser, errors, "servings")
    A.open_today(page, URL)
    doc = fixture_doc()
    roy_entry = next(e for e in doc["entries"] if e["foodId"] == ROY)
    load(page, doc)
    go(page, "add", "lunch", "2026-08-08")
    r = next((x for x in rows(page) if x["id"] == ROY), {})
    row_button(page, ROY, "plus").click()
    page.locator("#toast .toast").wait_for()
    e = stored(page)["entries"][-1]
    toast = page.locator("#toast .toast").inner_text()
    CHECK("the serving food's row reads '1 serving' (stored as MyNetDiary's '1 servings') and + logs it at its totals; "
          "the toast cuts the long name after a word",
          r.get("sub") == "Roy Rogers, 1 serving" and r.get("kcal") == "350" and e.get("amount") == "1 servings"
          and "1 serving of Sandwiches Roast Beef Sand… added to lunch" in toast and e.get("grams") is None
          and e.get("totals") == roy_entry["totals"], (r, e, toast))

    go(page, "food", ROY, "lunch", "2026-08-08")
    field = page.get_by_label("Number of servings")
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    unit = page.locator('[data-test="unit"]').inner_text()
    CHECK("a food with no per100 offers its servings, not grams; the chip and the unit both say '1 serving'",
          field.count() == 1 and page.get_by_label("Grams").count() == 0 and "350 kcal per serving" in sheet(page).inner_text()
          and unit == "serving" and chips == ["1 serving"],
          (sheet(page).inner_text()[:200], unit, chips))
    field.fill("2")
    shown = page.locator('[data-test="portion-kcal"]').inner_text().strip()
    page.get_by_role("button", name="Add to lunch").click()
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    t = e.get("totals", {})
    doubled = all(abs(t.get(k, -1) - 2 * v) <= 0.0051 for k, v in roy_entry["totals"].items()) and set(t) == set(roy_entry["totals"])
    CHECK("2 servings of the Roy Rogers sandwich store grams null and 2 x that entry's totals (700 kcal, protein 78)",
          shown == "700" and e.get("grams") is None and e.get("amount") == "2 servings" and e.get("foodId") == ROY
          and e.get("date") == "2026-08-08" and e.get("meal") == "lunch" and t.get("kcal") == 700 and t.get("protein") == 78 and doubled, e)
    page.go_back()
    page.wait_for_selector('[data-screen] .log-row')
    where = page.evaluate("location.hash")
    CHECK("Back from Today after Add on a food route shows that meal's list, not the sheet again",
          where == "#/add/lunch/2026-08-08" and sheet(page).count() == 0, (where, sheet(page).count()))

    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-tablet', name: 'Test Tablet', servings: [
        { label: '1 tablet', grams: null, kcal: 5 }], source: 'label' }); })""")
    go(page, "food", "test-tablet", "snacks")
    page.get_by_label("Number of tablets").fill("2")
    page.get_by_role("button", name="Add to snacks").click()
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    CHECK("a serving food with no entry gets kcal only, from its serving",
          e.get("foodId") == "test-tablet" and e.get("totals") == {"kcal": 10} and e.get("grams") is None and e.get("amount") == "2 tablets", e)

    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-bottle', name: 'Test Cola', servings: [
        { label: '250 ml', grams: null, kcal: 105 }], source: 'label' }); })""")
    go(page, "food", "test-bottle", "snacks")
    page.locator(".log-sheet input[name=amount], [data-screen] form input[name=amount]").last.fill("1250")
    page.get_by_role("button", name="Add to snacks").click()
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    CHECK("an ml drink logs a whole 1.25 l bottle: 1250 ml, kcal from its 250 ml serving (525)",
          e.get("foodId") == "test-bottle" and e.get("amount") == "1250 ml" and e.get("totals") == {"kcal": 525}, e)
    ctx.close()


# ── 5. search, and the starter document ──
def check_search(browser, errors):
    ctx, page = A.phone(browser, errors, "search")
    A.open_today(page, URL)
    go(page, "add", "dinner")
    got = rows(page)
    CHECK("with no entries, Frequent shows the five starter foods in order with Brand, N g",
          [r["name"] for r in got] == [s[1] for s in A.STARTER]
          and [r["sub"] for r in got] == [(f"{b}, " if b else "") + f"{g} g" for _, _, b, _, g in A.STARTER], got)
    q = page.get_by_label("Search food or brand")
    found = {}
    for typed in ("tza", "coles", "COLES", "rice coles"):
        q.fill(typed)
        found[typed] = sorted(r["name"] for r in rows(page))
    CHECK('search "tza" finds Classic Tzatziki Dip and "coles" lists the two Coles foods, any case, every word',
          found["tza"] == ["Classic Tzatziki Dip"] and found["coles"] == ["Classic Tzatziki Dip", "Indian Basmati Rice"]
          and found["COLES"] == found["coles"] and found["rice coles"] == ["Indian Basmati Rice"], found)
    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-accent', name: 'Crème Fraîche', brand: "O'Brien",
        per100: { kcal: 300 }, servings: [], source: 'label' }); })""")
    folded = {}
    for typed in ("creme fraiche", "obrien", "o'brien"):
        q.fill(typed)
        folded[typed] = [r["name"] for r in rows(page)]
    CHECK("search ignores accents and apostrophes", all(v == ["Crème Fraîche"] for v in folded.values()), folded)
    q.fill("zzzq")
    empty = page.locator(".log-empty")
    said = empty.inner_text() if empty.count() else ""
    scan = page.locator(".log-list").get_by_role("button", name="Scan a barcode")
    CHECK("no match says so and offers Scan", not rows(page) and "No food matches" in said and scan.count() == 1, said)
    scan.click()
    page.wait_for_selector('[data-screen="scan"]')
    CHECK("Scan opens the scan screen", page.locator('[data-screen="scan"]').count() == 1)
    ctx.close()


# ── 6. routes ──
def check_routes(browser, errors):
    ctx, page = A.phone(browser, errors, "routes")
    A.open_today(page, URL)
    go(page, "add", "dinner", "2026-08-08")
    head = (page.locator('[data-screen="add"] .title').inner_text(), page.locator('[data-screen="add"] .eyebrow').first.inner_text())
    CHECK("add meal date shows that meal and day", head == ("Dinner", "Saturday, 8 August"), head)
    page.evaluate("location.hash = '#/add'")
    page.wait_for_function("document.querySelector('[data-screen=\"add\"] .title')?.textContent === 'Breakfast'")
    CHECK("add with no meal or date is the clock's meal (breakfast at 07:00) today",
          page.locator('[data-screen="add"] .eyebrow').first.inner_text() == "Tuesday, 20 October")
    go(page, "food", CHICKEN, "lunch")
    CHECK("food id meal opens the gram sheet for that food and meal",
          sheet(page).count() == 1 and page.get_by_role("radio", name="Lunch").is_checked()
          and page.get_by_role("button", name="Add to lunch").count() == 1 and page.get_by_label("Grams").input_value() == "350")
    page.locator(".log-scrim").click(position={"x": 180, "y": 8})
    page.wait_for_selector('[data-screen="add"]')
    CHECK("closing a sheet opened by route goes back", page.locator('[data-screen="food"]').count() == 0)
    go(page, "food", "no-such-food", "dinner")
    banner = page.locator('[data-screen="food"] .banner')
    CHECK("a bad food id shows a plain message", banner.count() == 1 and "not in your list" in banner.inner_text(), banner.count())
    page.get_by_role("button", name="Back").click()
    page.wait_for_selector('[data-screen="add"]')
    CHECK("and a way back", page.locator('[data-screen="food"]').count() == 0)
    go(page, "add", "brunch")
    CHECK("a meal that does not exist says so", "no meal called" in page.locator('[data-screen="add"] .banner').inner_text())
    ctx.close()


# ── 7. drawings: the fixture's foods, no catch-all, and the full history when present ──
def check_drawings(browser, errors):
    ctx, page = A.phone(browser, errors, "drawings")
    A.open_today(page, URL)
    doc = fixture_doc()
    kinds = page.evaluate("foods => foods.map(f => [f.name, PantryDrawing.kind(f)])", doc["foods"])
    CHECK("every food of the fixture gets its own drawing, not the generic pack", all(k != "pack" for _, k in kinds), kinds)
    nonsense = page.evaluate("() => [PantryDrawing.kind({ name: 'Xyzzy Qwerty' }), PantryDrawing.kind({ name: '' }), PantryDrawing.kind(null)]")
    keys = page.evaluate("() => PantryDrawing.keys.map(k => [k, /<path /.test(PantryDrawing.named(k, 32))])")
    CHECK("no catch-all: an unknown name gets the pack; every drawing key draws", nonsense == ["pack"] * 3 and all(ok for _, ok in keys), (nonsense, keys))
    inside = page.evaluate("""() => [PantryDrawing.kind({ name: 'Sliced Loaf', brand: 'Buttercup Bakery' }), PantryDrawing.kind({ name: 'Shortbread' }),
        PantryDrawing.kind({ name: 'Stuffed Eggplant' }), PantryDrawing.kind({ name: 'Tuna Sandwich Style' })]""")
    CHECK("a word inside another word picks nothing (Buttercup is no butter, shortbread no bread, eggplant no egg)",
          inside == ["bread", "pack", "pack", "tin"], inside)

    path, source = history_source()
    if not source:
        print(f"SKIP drawings on the full history: {HISTORY_NAME} is not on this machine ({', '.join(map(str, HISTORY))})")
        ctx.close()
        return
    full = importer.build_document(source)
    kinds = dict(page.evaluate("foods => foods.map(f => [f.id, PantryDrawing.kind(f)])", full["foods"]))
    count = collections.Counter(e["foodId"] for e in full["entries"])
    own = sum(n for fid, n in count.items() if kinds.get(fid) != "pack")
    share = own / sum(count.values())
    print(f"Drawing per food of the full history ({path}), most logged first:")
    for food in sorted(full["foods"], key=lambda f: -count[f["id"]]):
        print(f"  {kinds[food['id']]:<9}{count[food['id']]:>5}  {food['name']}" + (f" ({food['brand']})" if food.get("brand") else ""))
    CHECK(f"at least 90 % of the history's entries get their own drawing ({share:.1%} of {sum(count.values())})", share >= 0.9, share)
    ctx.close()


# ── 8. the full history: Dinner's ranking against counts computed here ──
def check_history(browser, errors):
    path, source = history_source()
    if not source:
        print(f"SKIP Dinner ranking on the full history: {HISTORY_NAME} is not on this machine")
        return
    full = importer.build_document(source)
    since = (TODAY - datetime.timedelta(days=90)).isoformat()
    window = [e for e in full["entries"] if e["meal"] == "dinner" and since <= e["date"] <= TODAY.isoformat()]
    count = collections.Counter(e["foodId"] for e in window)
    ctx, page = A.phone(browser, errors, "history")
    A.open_today(page, URL)
    load(page, full)
    go(page, "add", "dinner")
    got = rows(page)
    order = [count[r["id"]] for r in got]
    CHECK(f"with the full history, Dinner lists the {len(count)} foods of the last 90 days by count ({order[:8]}...)",
          {r["id"] for r in got} == set(count) and order == sorted(order, reverse=True), (len(got), len(count), order))
    top = got[0]["id"] if got else None
    amounts = collections.Counter(e["amount"] for e in window if e["foodId"] == top)
    best = max(amounts.values()) if amounts else 0
    latest = {a: max(e["date"] for e in window if e["foodId"] == top and e["amount"] == a) for a in amounts}
    usual = max((a for a in amounts if amounts[a] == best), key=lambda a: latest[a]) if amounts else None
    CHECK(f"the first row shows its most typed dinner amount ({usual})",
          bool(got) and (got[0]["sub"] == usual or got[0]["sub"].endswith(f", {usual}")), got[0] if got else None)
    ctx.close()


# ── 9. 360 x 780 at 150 % text and 240 px: fits, ellipsis, both themes ──
HINT_JS = """() => { const i = document.querySelector('[data-screen] .log-field input'), cs = getComputedStyle(i);
  const c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  return { hint: i.placeholder, value: i.value, hintPx: Math.round(c.measureText(i.placeholder).width), fieldPx: i.clientWidth,
           input: cs.textOverflow, placeholder: getComputedStyle(i, '::placeholder').textOverflow }; }"""


def check_layout(browser, errors):
    for scheme, canvas, surface in (("dark", "rgb(14, 14, 14)", "rgb(25, 25, 25)"), ("light", "rgb(247, 247, 247)", "rgb(255, 255, 255)")):
        ctx = browser.new_context(**A.PHONE, color_scheme=scheme)
        ctx.clock.set_fixed_time(A.NOW)
        page = ctx.new_page()
        A.watch(page, errors, f"layout-{scheme}")
        A.set_text(page, A.BIG_TEXT)
        A.open_today(page, URL)
        load(page, fixture_doc())
        go(page, "add", "snacks")
        page.get_by_role("tab", name="My foods").click()
        A.fits(page, f"meal list, My foods, 150 % text, {scheme}")
        A.rows_single_line(page, f"meal list ({scheme})")
        cut = page.evaluate("n => { const el = [...document.querySelectorAll('.log-row .name')].find(e => e.textContent === n); return el ? el.scrollWidth > el.clientWidth : null; }", LOAF_NAME)
        CHECK(f"the long loaf name is cut by the ellipsis at 150 % text ({scheme})", cut is True, cut)
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        CHECK(f"{scheme} theme renders the canvas ({bg})", page.evaluate("document.documentElement.dataset.theme") == scheme and bg == canvas, bg)
        row_button(page, next(f["id"] for f in fixture_doc()["foods"] if f["name"] == LOAF_NAME), "open").click()
        sheet(page).wait_for()
        page.wait_for_timeout(400)
        A.fits(page, f"gram sheet, 150 % text, {scheme}")
        sbg = page.evaluate("getComputedStyle(document.querySelector('.log-sheet')).backgroundColor")
        CHECK(f"{scheme} gram sheet stands on surface-1 ({sbg})", sbg == surface, sbg)
        page.locator(".log-more").click()
        A.fits(page, f"gram sheet with all nutrients, 150 % text, {scheme}")
        add = page.get_by_role("button", name="Add to snacks").bounding_box()
        CHECK(f"Add to snacks stays on screen with all nutrients open ({scheme})", add and add["y"] + add["height"] <= 780, add)
        if scheme == "dark":
            page.go_back()
            page.wait_for_selector(".log-layer", state="detached")
            page.set_viewport_size({"width": 240, "height": 520})
            page.wait_for_timeout(200)
            h = page.evaluate(HINT_JS)
            CHECK("at 240 px and 150 % text the search hint has no room and ends in an ellipsis, not mid-letter",
                  not h["value"] and h["hintPx"] > h["fieldPx"] and h["input"] == h["placeholder"] == "ellipsis", h)
            A.set_text(page, 1.0)
            page.reload()
            page.wait_for_selector('[data-screen="add"] .log-row')
            A.fits(page, "meal list at 240 px")
            A.rows_single_line(page, "meal list at 240 px")
            page.locator(".log-row .log-open").first.click()
            sheet(page).wait_for()
            page.wait_for_timeout(400)
            A.fits(page, "gram sheet at 240 px")
        ctx.close()


# ── 10. the usual amount is never cut, the brand gives way; the tab labels stay on one line ──
AMOUNTS_JS = """() => [...document.querySelectorAll('[data-screen] .log-row')].map(r => {
  const s = r.querySelector('.sub'), a = s.querySelector('.a'), b = s.querySelector('.b');
  const sr = s.getBoundingClientRect(), ar = a && a.getBoundingClientRect();
  return { name: r.querySelector('.name').textContent, sub: s.textContent, amount: a ? a.textContent : null,
           full: !a || (a.scrollWidth <= a.clientWidth && ar.right <= sr.right + 0.5 && s.scrollWidth <= s.clientWidth),
           brand: !b ? '' : b.hidden ? 'gone' : b.scrollWidth > b.clientWidth ? 'short' : 'full',
           longer: !!a && a.scrollWidth > sr.width + 0.5 && r.querySelector('.log-open').classList.contains('log-long') };
})"""
TABS_JS = """() => [...document.querySelectorAll('.log-tab')].map(t => {
  const range = document.createRange(); range.selectNodeContents(t);
  return { tab: t.textContent, top: Math.round(t.getBoundingClientRect().top),
           lines: new Set([...range.getClientRects()].map(x => Math.round(x.top))).size };
})"""


def check_amounts(browser, errors):
    for text, width, height in ((A.BIG_TEXT, 360, 780), (1.0, 240, 520)):
        where = f"{width} px, text {round(text * 100)} %"
        ctx = browser.new_context(**{**A.PHONE, "viewport": {"width": width, "height": height}})
        ctx.clock.set_fixed_time(A.NOW)
        page = ctx.new_page()
        A.watch(page, errors, f"amounts-{width}")
        A.set_text(page, text)
        A.open_today(page, URL)
        load(page, fixture_doc())
        seen, cut, longer = {}, [], []
        for meal in ("dinner", "lunch", "breakfast", "snacks"):
            go(page, "add", meal)
            if meal == "dinner":
                tabs = page.evaluate(TABS_JS)
                CHECK(f"the three tab labels sit on one row, each on one line ({where})",
                      len(tabs) == 3 and all(t["lines"] == 1 for t in tabs) and len({t["top"] for t in tabs}) == 1, tabs)
            for tab in ("Frequent", "Recent", "My foods"):
                page.get_by_role("tab", name=tab).click()
                for r in page.evaluate(AMOUNTS_JS):
                    seen[(meal, r["name"])] = r
                    if r["longer"]:
                        longer.append((meal, tab, r))
                    elif not r["full"]:
                        cut.append((meal, tab, r))
        CHECK(f"every row's usual amount shows in full, never in the ellipsis ({where}, {len(seen)} rows)", seen and not cut, cut or None)
        if longer:
            print(f"  note ({where}): amounts longer than the whole line, cut at their end: {[(m, r['sub']) for m, _, r in longer]}")
        if width == 360:
            potato = seen.get(("dinner", "Washed White Potato"), {})
            CHECK("Woolworths, 1000 g at dinner: the brand is shortened so 1000 g shows whole (150 % text)",
                  potato.get("sub") == "Woolworths, 1000 g" and potato.get("amount") == "1000 g" and potato.get("brand") == "short"
                  and potato.get("full") is True, potato)
            roy = seen.get(("lunch", "Sandwiches Roast Beef Sand Whole Grain"), {})
            CHECK("Roy Rogers, 1 serving at lunch: the brand is shortened so 1 serving shows whole (150 % text)",
                  roy.get("sub") == "Roy Rogers, 1 serving" and roy.get("brand") == "short" and roy.get("full") is True, roy)
        ctx.close()


# ── Task-08: logging the MyNetDiary way ──
CHECK_PATH = "M5 12l5 5 9-10"            # core's check icon
BUZZ_JS = """Object.defineProperty(Navigator.prototype, 'vibrate', { configurable: true,
  value(pattern) { (window.__buzz = window.__buzz || []).push(pattern); return true; } });"""
SETTLE_JS = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 300))))"


def settle(page):
    """Two frames and the 250 ms fallback of a deferred save: whatever a tap was going to save is saved by now."""
    page.evaluate(SETTLE_JS)


def wait_toast(page, text):
    page.wait_for_function("t => (document.querySelector('#toast .toast') || {}).textContent?.includes(t)", arg=text)
    return page.locator("#toast .toast").inner_text()


def tick(page, food_id):
    page.locator(f'[data-screen] .log-row[data-id={json.dumps(food_id)}] [data-act="tick"]').check()


def ticked(page):
    return page.evaluate("""() => [...document.querySelectorAll('[data-screen] .log-row [data-act="tick"]')]
        .filter(b => b.checked).map(b => b.closest('.log-row').dataset.id)""")


def summary(page):
    """The line under the title, once a changed number has finished its swap."""
    page.wait_for_function("""() => { const n = document.querySelector('[data-test="log-sum"] .log-num');
        return !n || (n.textContent === n.dataset.to && !n.getAnimations().length); }""")
    return page.locator('[data-test="log-sum"]').inner_text().strip()


def marks(page):
    """food id -> the count its row's check shows (0: no check)."""
    return page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('[data-screen] .log-row')].map(r => {
        const m = r.querySelector('.log-mark'); return [r.dataset.id, m.hidden ? 0 : Number(m.textContent) || 1]; }))""")


def new_entries(page, old_ids):
    return [e for e in stored(page)["entries"] if e["id"] not in old_ids]


def food_id(doc, name):
    return next(f["id"] for f in doc["foods"] if f["name"] == name)


# ── 11. the list says what is in the meal on the shown day, and follows a + without leaving ──
def check_meal_line(browser, errors):
    ctx, page = A.phone(browser, errors, "meal-line", text=1.0)
    A.open_today(page, URL)
    day = TODAY.isoformat()
    chicken, tzatziki, rice = totals(page, CHICKEN, 350), totals(page, TZATZIKI, 125), totals(page, RICE, 100)
    add_entries(page, [
        {"id": "m1", "date": day, "meal": "dinner", "foodId": CHICKEN, "amount": "350 g", "grams": 350, "totals": chicken},
        {"id": "m2", "date": day, "meal": "dinner", "foodId": TZATZIKI, "amount": "125 g", "grams": 125, "totals": tzatziki},
        {"id": "m3", "date": day, "meal": "lunch", "foodId": RICE, "amount": "100 g", "grams": 100, "totals": rice},
        {"id": "m4", "date": "2026-10-18", "meal": "dinner", "foodId": RICE, "amount": "100 g", "grams": 100, "totals": rice}])
    go(page, "add", "dinner")
    want = fmt(page, chicken["kcal"] + tzatziki["kcal"])
    said = summary(page)
    CHECK(f"under the title: what dinner holds today, 'In dinner: 2 foods, {want} kcal' (not lunch's rice, not another day's)",
          said == f"In dinner: 2 foods, {want} kcal", said)
    got = marks(page)
    CHECK("rows already in today's dinner carry a check (chicken, tzatziki); rice (lunch today, dinner another day) has none",
          got.get(CHICKEN) == 1 and got.get(TZATZIKI) == 1 and got.get(RICE) == 0, got)
    where = page.evaluate("location.hash")
    row_button(page, RICE, "plus").click()
    wait_toast(page, "100 g of Indian Basmati Rice added to dinner")
    want = fmt(page, chicken["kcal"] + tzatziki["kcal"] + rice["kcal"])
    said, got = summary(page), marks(page)
    CHECK(f"after a + on rice, still on the list: the line reads 3 foods, {want} kcal and rice's row carries the check",
          said == f"In dinner: 3 foods, {want} kcal" and got.get(RICE) == 1 and page.evaluate("location.hash") == where
          and page.locator('[data-screen="add"]').count() == 1, (said, got))
    row_button(page, CHICKEN, "plus").click()
    wait_toast(page, "350 g of Chicken Breast Raw added to dinner")
    shown = page.locator(f'.log-row[data-id={json.dumps(CHICKEN)}] .log-mark').inner_text().strip()
    CHECK("a second chicken at dinner: its check counts 2", marks(page).get(CHICKEN) == 2 and shown == "2", shown)
    go(page, "add", "lunch")
    lunch = summary(page)
    go(page, "add", "breakfast", "2026-10-18")
    CHECK("lunch's list counts lunch only; a meal with nothing says so",
          lunch == f"In lunch: 1 food, {fmt(page, rice['kcal'])} kcal" and summary(page) == "Nothing in breakfast yet", (lunch, summary(page)))
    ctx.close()


# ── 12. tick several foods, one Add, one Undo ──
def check_ticks(browser, errors):
    ctx, page = A.phone(browser, errors, "ticks", text=1.0)
    A.open_today(page, URL)
    add_entries(page, [entry(1, CHICKEN, "2026-10-01", "dinner", "350 g", 350), entry(2, CHICKEN, "2026-10-02", "dinner", "375 g", 375),
                       entry(3, CHICKEN, "2026-10-03", "dinner", "350 g", 350), entry(4, RICE, "2026-10-04", "dinner", "100 g", 100),
                       entry(5, BUTTER, "2026-10-05", "dinner", "5 g", 5), entry(6, BUTTER, "2026-10-06", "lunch", "10 g", 10),
                       entry(7, BUTTER, "2026-10-07", "lunch", "10 g", 10), entry(8, TZATZIKI, "2026-10-08", "dinner", "125 g", 125)])
    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-new', name: 'Test Oats', per100: { kcal: 380 }, servings: [],
        source: 'label' }); })""")
    go(page, "add", "dinner", "2026-08-08")
    # what a single + logs for chicken, then undone: the reference for the ticked chicken
    ids = {e["id"] for e in stored(page)["entries"]}
    row_button(page, CHICKEN, "plus").click()
    wait_toast(page, "350 g of Chicken Breast Raw added to dinner on 8 Aug")
    one = new_entries(page, ids)
    page.get_by_role("button", name="Undo").click()
    art = page.locator(f'[data-screen] .log-row[data-id={json.dumps(CHICKEN)}] .log-food').bounding_box()
    page.touchscreen.tap(art["x"] + art["width"] / 2, art["y"] + art["height"] / 2)
    by_drawing = ticked(page) == [CHICKEN] and sheet(page).count() == 0
    tick(page, RICE)
    page.get_by_role("tab", name="My foods").click()
    tick(page, BUTTER)
    bar = page.locator('[data-screen] [data-act="add-ticked"]')
    CHECK("a tap on a row's drawing ticks it (no sheet); ticks hold across tabs: three ticked, the bar offers 'Add 3 to dinner'",
          by_drawing and sorted(ticked(page)) == sorted([CHICKEN, RICE, BUTTER]) and bar.is_visible() and bar.inner_text() == "Add 3 to dinner",
          (by_drawing, ticked(page), bar.is_visible()))
    oats = page.locator('[data-screen] .log-row[data-id="test-new"]')
    no_tick = oats.locator('[data-act="tick"]').count() == 0
    oats.locator(".log-food").click()                    # no tick over it: the drawing is part of the row
    by_art = sheet(page).count() == 1
    page.go_back()
    page.wait_for_selector(".log-layer:not(.log-out)", state="detached")
    row_button(page, "test-new", "plus").click()
    opened = sheet(page).count() == 1
    page.go_back()
    page.wait_for_selector(".log-layer:not(.log-out)", state="detached")
    CHECK("a food with no usual amount has no tick: its drawing and its + open the gram sheet; the ticks stay",
          no_tick and by_art and opened and len(ticked(page)) == 3, (no_tick, by_art, opened, ticked(page)))
    before = stored(page)
    ids = {e["id"] for e in before["entries"]}
    bar.click()
    toast = wait_toast(page, "3 foods added to dinner on 8 Aug")
    new = new_entries(page, ids)
    usual = {f: page.evaluate("f => Pantry.usualAmounts(f, 'dinner')[0]", f) for f in (RICE, BUTTER)}
    want = [(CHICKEN, one[0]["amount"] if one else None, one[0]["grams"] if one else None, one[0]["totals"] if one else None)] + [
        (f, usual[f]["amount"], usual[f]["grams"], totals(page, f, usual[f]["grams"])) for f in (RICE, BUTTER)]
    CHECK("Add logs three entries in tick order, each at its usual amount (butter's dinner 5 g, not lunch's 10 g) with the "
          "totals a + logs, on the route's day and meal",
          len(one) == 1 and [(e["foodId"], e["amount"], e["grams"], e["totals"]) for e in new] == want
          and all(e["date"] == "2026-08-08" and e["meal"] == "dinner" for e in new), (new, want))
    CHECK("after Add the ticks are clear, the bar is gone and the three rows carry their check",
          not ticked(page) and bar.is_hidden() and all(marks(page).get(f) == 1 for f in (CHICKEN, RICE, BUTTER)), (ticked(page), marks(page)))
    CHECK("the toast says 3 foods with Undo and draws them together",
          "Undo" in toast and page.locator("#toast .toast-art svg svg").count() == 3, toast)
    page.get_by_role("button", name="Undo").click()
    after = stored(page)
    gone = {r["id"] for r in after.get("removed", [])} - {r["id"] for r in before.get("removed", [])}
    CHECK("one Undo removes exactly those three (the log is as before) and adds their removed lines",
          after["entries"] == before["entries"] and gone == {e["id"] for e in new}, gone)
    n = len(after["entries"])
    page.evaluate("() => document.querySelector('[data-screen] [data-act=\"add-ticked\"]').click()")
    settle(page)
    CHECK("with nothing ticked, Add logs nothing", len(stored(page)["entries"]) == n and bar.is_hidden())
    tick(page, CHICKEN)
    tick(page, TZATZIKI)
    page.evaluate("() => { const b = document.querySelector('[data-screen] [data-act=\"add-ticked\"]'); b.click(); b.click(); }")
    wait_toast(page, "2 foods added to dinner")
    settle(page)
    twice = new_entries(page, {e["id"] for e in after["entries"]})
    CHECK("Add tapped twice fast logs one set (two entries), and the ticks are clear",
          sorted(e["foodId"] for e in twice) == sorted([CHICKEN, TZATZIKI]) and not ticked(page), twice)
    ctx.close()


# ── 12b. ticks meet the + and the sheet: nothing ticked is dropped, nothing is logged twice ──
def check_ticks_meet(browser, errors):
    ctx, page = A.phone(browser, errors, "ticks-meet", text=1.0)
    A.open_today(page, URL)
    add_entries(page, [entry(1, CHICKEN, "2026-10-01", "dinner", "350 g", 350), entry(2, RICE, "2026-10-02", "dinner", "100 g", 100),
                       entry(3, BUTTER, "2026-10-03", "dinner", "5 g", 5)])
    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-new', name: 'Test Oats', per100: { kcal: 380 }, servings: [],
        source: 'label' }); })""")
    go(page, "add", "dinner", "2026-08-08")
    ids = {e["id"] for e in stored(page)["entries"]}
    bar = page.locator('[data-screen] [data-act="add-ticked"]')
    tick(page, CHICKEN)
    row_button(page, CHICKEN, "plus").click()
    wait_toast(page, "350 g of Chicken Breast Raw added to dinner on 8 Aug")
    settle(page)
    CHECK("a + on a ticked food logs it once and unticks it: no 'Add 1 to dinner' is left to log it a second time",
          not ticked(page) and bar.is_hidden() and [e["foodId"] for e in new_entries(page, ids)] == [CHICKEN],
          (ticked(page), bar.is_hidden(), new_entries(page, ids)))
    before = stored(page)
    ids = {e["id"] for e in before["entries"]}
    tick(page, RICE)
    tick(page, BUTTER)
    page.get_by_role("tab", name="My foods").click()
    row_button(page, "test-new", "plus").click()        # no usual amount: its + opens the sheet over the two ticks
    sheet(page).wait_for()
    add = page.get_by_role("button", name="Add 3 to dinner")
    named = add.count() == 1
    page.get_by_label("Grams").fill("60")
    if named:
        add.click()
    else:
        page.locator(".log-sheet [type=submit]").click()
    page.wait_for_selector('[data-screen="today"]')
    toast = wait_toast(page, "added to dinner on 8 Aug")
    new = new_entries(page, ids)
    usual = {f: page.evaluate("f => Pantry.usualAmounts(f, 'dinner')[0]", f) for f in (RICE, BUTTER)}
    want = [(f, usual[f]["amount"], usual[f]["grams"], totals(page, f, usual[f]["grams"])) for f in (RICE, BUTTER)] + [
        ("test-new", "60 g", 60, totals(page, "test-new", 60))]
    CHECK("with rice and butter ticked, the sheet's button reads 'Add 3 to dinner' and logs the ticked two at their usual "
          "amounts with the oats at 60 g, on 8 Aug at dinner, under one toast ('3 foods')",
          named and [(e["foodId"], e["amount"], e["grams"], e["totals"]) for e in new] == want
          and all(e["date"] == "2026-08-08" and e["meal"] == "dinner" for e in new) and "3 foods added to dinner" in toast,
          (named, new, toast))
    page.get_by_role("button", name="Undo").click()
    CHECK("its one Undo removes all three", stored(page)["entries"] == before["entries"], len(stored(page)["entries"]) - len(before["entries"]))
    # the sheet's radio sends its own food to lunch: the ticked butter still goes to dinner at dinner's 5 g (as its +
    # on this list would log it, not lunch's 10 g), and the button and the toast say both meals
    add_entries(page, [entry(4, BUTTER, "2026-10-04", "lunch", "10 g", 10), entry(5, BUTTER, "2026-10-05", "lunch", "10 g", 10)])
    go(page, "add", "dinner", "2026-08-08")
    ids = {e["id"] for e in stored(page)["entries"]}
    tick(page, BUTTER)
    row_button(page, CHICKEN, "open").click()
    sheet(page).wait_for()
    page.get_by_role("radio", name="Lunch").check()
    label = page.locator(".log-sheet [type=submit]").inner_text()
    page.locator(".log-sheet [type=submit]").click()
    page.wait_for_selector('[data-screen="today"]')
    toast = wait_toast(page, "added to lunch")
    new = new_entries(page, ids)
    want = [(BUTTER, "dinner", "5 g", 5, totals(page, BUTTER, 5)), (CHICKEN, "lunch", "350 g", 350, totals(page, CHICKEN, 350))]
    CHECK("with butter ticked on the dinner list and the sheet's radio on Lunch, the button reads 'Add to lunch, 1 to dinner'; "
          "butter goes to dinner at its dinner 5 g, chicken to lunch, under one toast ('2 foods added to lunch and dinner')",
          label == "Add to lunch, 1 to dinner" and [(e["foodId"], e["meal"], e["amount"], e["grams"], e["totals"]) for e in new] == want
          and "2 foods added to lunch and dinner on 8 Aug" in toast, (label, new, toast))
    # a ticked food deleted from another tab or device: the bar counts what is left, and Add logs exactly that
    go(page, "add", "dinner", "2026-08-08")
    ids = {e["id"] for e in stored(page)["entries"]}
    tick(page, CHICKEN)
    tick(page, RICE)
    page.evaluate("id => Pantry.change(d => { d.foods = d.foods.filter(f => f.id !== id); })", RICE)
    said = bar.inner_text() if bar.is_visible() else None
    bar.click()
    wait_toast(page, "350 g of Chicken Breast Raw added to dinner on 8 Aug")
    new = new_entries(page, ids)
    CHECK("chicken and rice ticked, then rice deleted elsewhere: the bar reads 'Add 1 to dinner' and Add logs chicken alone",
          said == "Add 1 to dinner" and [e["foodId"] for e in new] == [CHICKEN], (said, new))
    ctx.close()


# ── 13. "Same as yesterday's <meal>" ──
def check_yesterday(browser, errors):
    ctx, page = A.phone(browser, errors, "yesterday", text=1.0)
    A.open_today(page, URL)
    doc = fixture_doc()
    load(page, doc)
    potato, grilled = food_id(doc, "Washed White Potato"), food_id(doc, "Chicken Grilled")
    go(page, "add", "dinner", "2026-08-08")
    CHECK("no 'Same as yesterday' when 7 Aug has no dinner", page.locator(".log-again").count() == 0)
    y = [{"id": "y1", "date": "2026-08-07", "meal": "dinner", "foodId": potato, "amount": "750 g", "grams": 750,
          "totals": {"kcal": 442.2, "protein": 17.03, "carbs": 111.0}},
         {"id": "y2", "date": "2026-08-07", "meal": "dinner", "foodId": grilled, "amount": "1 piece", "grams": 192,
          "totals": {"kcal": 296, "protein": 60, "fat": 6.2}},
         {"id": "y3", "date": "2026-08-07", "meal": "lunch", "foodId": grilled, "amount": "2 pieces", "grams": 384, "totals": {"kcal": 592}}]
    add_entries(page, y)
    page.evaluate("id => Pantry.change(d => { const f = d.foods.find(x => x.id === id); f.per100.kcal = 999; f.per100.protein = 50; })", potato)
    go(page, "add", "dinner", "2026-08-08")
    again = page.get_by_role("button", name=re.compile("^Same as yesterday's dinner"))
    label = again.get_attribute("aria-label") if again.count() == 1 else ""
    seen = [page.locator(f".log-again {c}").inner_text() for c in (".name", ".sub", ".k")] if again.count() == 1 else []
    CHECK("7 Aug had dinner: 8 Aug's dinner list offers 'Same as yesterday's dinner' with its 2 foods and kcal (738), "
          "the meal and both foods on the screen, not only in its name",
          again.count() == 1 and "2 foods: Washed White Potato, Chicken Grilled" in label and label.endswith("738 kcal")
          and seen == ["Same as yesterday's dinner", "738 kcal: Washed White Potato, Chicken Grilled", "738"], (label, seen))
    ids = {e["id"] for e in stored(page)["entries"]}
    page.evaluate("() => { const b = document.querySelector('[data-act=\"again\"]'); b.click(); b.click(); }")
    wait_toast(page, "2 foods from yesterday added to dinner on 8 Aug")
    settle(page)
    new = new_entries(page, ids)
    CHECK("tapped twice fast it logs one set: one new entry per 7 Aug dinner entry, not its lunch", len(new) == 2, new)
    CHECK("each copy has the amount, grams and totals logged on 7 Aug (not recomputed from the potato's changed per100), "
          "a new id, 8 Aug, dinner",
          [(e["foodId"], e["amount"], e["grams"], e["totals"]) for e in new] == [(x["foodId"], x["amount"], x["grams"], x["totals"]) for x in y[:2]]
          and all(e["date"] == "2026-08-08" and e["meal"] == "dinner" and e["id"] not in ids for e in new)
          and len({e["id"] for e in new}) == 2, new)
    state = page.evaluate("""() => { const b = document.querySelector('.log-again');
        return [b.getAttribute('aria-disabled'), b.querySelector('.name').textContent, b.querySelector('.sub').textContent,
                b.querySelector('.log-plus').classList.contains('log-done')]; }""")
    n = len(stored(page)["entries"])
    page.locator(".log-again").click(force=True)        # aria-disabled: Playwright would wait for it to be enabled
    settle(page)
    CHECK("the row then reads as added (\"Yesterday's dinner added\", its foods still named, a check) and another tap logs nothing",
          state == ["true", "Yesterday's dinner added", "738 kcal: Washed White Potato, Chicken Grilled", True]
          and len(stored(page)["entries"]) == n, state)
    page.get_by_role("button", name="Undo").click()
    left = {e["id"] for e in stored(page)["entries"]}
    CHECK("one Undo removes both copies, and the row offers yesterday's dinner again",
          left == ids and page.locator(".log-again").get_attribute("aria-disabled") == "false", left - ids)
    # he logs yesterday's two foods one by one at the same amounts (as two + would): the row did not copy them, so it
    # still offers yesterday's dinner, and its tap still copies
    add_entries(page, [dict(x, id=f"by-hand-{x['id']}", date="2026-08-08") for x in y[:2]])
    settle(page)
    offered = page.evaluate("""() => { const b = document.querySelector('.log-again');
        return [b.getAttribute('aria-disabled'), b.querySelector('.name').textContent]; }""")
    ids = {e["id"] for e in stored(page)["entries"]}
    copies = []
    if offered[0] == "false":                          # a row reading as added would make the click wait for nothing
        page.locator(".log-again").click()
        wait_toast(page, "2 foods from yesterday added to dinner on 8 Aug")
        copies = new_entries(page, ids)
        page.get_by_role("button", name="Undo").click()
    CHECK("today's dinner holding yesterday's foods by hand does not make the row read as added; its own tap still copies them",
          offered == ["false", "Same as yesterday's dinner"] and len(copies) == 2, (offered, copies))
    # the app reopens with the copy still logged (Android kills a PWA in the background): the row still reads as added
    # and its tap logs nothing, though no Undo is left
    ids = {e["id"] for e in stored(page)["entries"]}
    page.locator(".log-again").click()
    wait_toast(page, "2 foods from yesterday added to dinner on 8 Aug")
    settle(page)
    copies = new_entries(page, ids)
    page.reload()
    page.wait_for_selector('[data-screen="add"] .log-again')
    reopened = page.evaluate("""() => { const b = document.querySelector('.log-again');
        return [b.getAttribute('aria-disabled'), b.querySelector('.name').textContent]; }""")
    page.locator(".log-again").click(force=True)
    settle(page)
    CHECK("after a reload with the copy still logged, the row still reads \"Yesterday's dinner added\" and a tap logs nothing",
          len(copies) == 2 and reopened == ["true", "Yesterday's dinner added"] and len(new_entries(page, ids)) == 2,
          (reopened, len(new_entries(page, ids))))
    # he moves both copies to lunch on the entry screen (design 8: Move to lunch, Save), which keeps their ids: dinner
    # holds no copy now, so the row offers yesterday's dinner again and its tap copies it into dinner
    for c in copies:
        page.evaluate("id => Pantry.go('entry', id)", c["id"])
        page.wait_for_selector('[data-screen="entry"]')
        page.get_by_role("button", name="Move to lunch").click()
        page.get_by_role("button", name="Save").click()
        page.wait_for_selector('[data-screen="today"]')
    moved = [(e["id"], e["meal"]) for e in stored(page)["entries"] if e["id"] in {c["id"] for c in copies}]
    go(page, "add", "dinner", "2026-08-08")
    offered = page.evaluate("""() => { const b = document.querySelector('.log-again');
        return [b.getAttribute('aria-disabled'), b.querySelector('.name').textContent]; }""")
    ids = {e["id"] for e in stored(page)["entries"]}
    recopied = []
    if offered[0] == "false":                          # a row reading as added would make the click wait for nothing
        page.locator(".log-again").click()
        wait_toast(page, "2 foods from yesterday added to dinner on 8 Aug")
        recopied = new_entries(page, ids)
    CHECK("both copies moved to lunch on the entry screen (their ids kept): the dinner list no longer reads as added, "
          "and its tap copies yesterday's dinner into dinner again",
          moved == [(c["id"], "lunch") for c in copies] and offered == ["false", "Same as yesterday's dinner"]
          and [(e["date"], e["meal"]) for e in recopied] == [("2026-08-08", "dinner")] * 2, (moved, offered, recopied))
    page.evaluate("ids => Pantry.change(d => { d.entries = d.entries.filter(e => !ids.includes(e.id)); })", [e["id"] for e in copies + recopied])
    offers = {}
    for meal, date in (("breakfast", "2026-08-08"), ("dinner", "2026-08-10"), ("dinner", "2026-08-09")):
        go(page, "add", meal, date)
        offers[(meal, date)] = page.locator(".log-again").count()
    CHECK("only the shown day − 1 counts: no row for 8 Aug breakfast (none on 7 Aug) or 10 Aug dinner, one for 9 Aug dinner",
          offers == {("breakfast", "2026-08-08"): 0, ("dinner", "2026-08-10"): 0, ("dinner", "2026-08-09"): 1}, offers)
    page.clock.set_fixed_time(datetime.datetime(2026, 8, 8, 19, 30, tzinfo=A.DARWIN))
    page.evaluate("location.hash = '#/add'")
    page.wait_for_function("document.querySelector('[data-screen=\"add\"] [data-test=\"log-day\"]')?.textContent === 'Saturday, 8 August'"
                           " && document.querySelector('[data-screen=\"add\"] .title').textContent === 'Dinner'")
    label = page.locator(".log-again").get_attribute("aria-label") if page.locator(".log-again").count() else ""
    CHECK("with the page clock at 8 Aug 19:30, today's dinner (no date in the route) offers 7 Aug's dinner",
          label.startswith("Same as yesterday's dinner, 2 foods"), label)
    page.get_by_label("Search food or brand").fill("pot")
    CHECK("a search hides the row", page.locator(".log-yday").is_hidden())
    ctx.close()


# ── 14. the + answers before the save ──
def check_instant(browser, errors):
    ctx, page = A.phone(browser, errors, "instant", text=1.0, init=BUZZ_JS)
    A.open_today(page, URL)
    add_entries(page, [entry(1, CHICKEN, "2026-10-01", "dinner", "350 g", 350)])
    go(page, "add", "dinner")
    got = page.evaluate("""([id, check]) => {
      const b = window.__plus = document.querySelector(`[data-screen] .log-row[data-id="${CSS.escape(id)}"] [data-act="plus"]`);
      const before = JSON.stringify(Pantry.doc());
      window.__buzz = [];
      b.click();
      const path = b.querySelector('svg path');
      return { check: b.classList.contains('log-done') && !!path && path.getAttribute('d') === check,
               same: JSON.stringify(Pantry.doc()) === before, buzz: window.__buzz.slice(), n: Pantry.doc().entries.length };
    }""", [CHICKEN, CHECK_PATH])
    CHECK("when the +'s click handler returns, the check shows, Pantry.haptic('tap') has pulsed (10 ms) and the document is unchanged",
          got["check"] and got["buzz"] == [10] and got["same"], got)
    saved = page.evaluate("""() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() =>
        r({ n: Pantry.doc().entries.length, kept: window.__plus.isConnected && window.__plus.classList.contains('log-done') }))))""")
    CHECK("the entry is saved on the next frame, and the check that answered stays (the row is not redrawn under it)",
          saved == {"n": got["n"] + 1, "kept": True}, (saved, got["n"]))
    wait_toast(page, "350 g of Chicken Breast Raw added to dinner")
    page.evaluate("() => { window.__buzz = []; }")
    page.get_by_role("button", name="Undo").click()
    back = page.evaluate("() => [window.__buzz, window.__plus.classList.contains('log-done')]")
    CHECK("Undo pulses too and the + comes back", back == [[10], False] and len(stored(page)["entries"]) == got["n"], back)
    # a finger's double tap (120 ms apart), then a tap on the check 300 ms later: the check is the answer, not a second +
    before = stored(page)["entries"]
    ids = {e["id"] for e in before}
    box = row_button(page, CHICKEN, "plus").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.touchscreen.tap(x, y)
    page.wait_for_timeout(120)
    page.touchscreen.tap(x, y)
    settle(page)
    double = len(new_entries(page, ids))
    page.wait_for_timeout(300)
    page.touchscreen.tap(x, y)
    settle(page)
    later = len(new_entries(page, ids))
    said = row_button(page, CHICKEN, "plus").get_attribute("aria-disabled")
    page.get_by_role("button", name="Undo").click()
    CHECK("a double tap on the + logs one entry, a tap on its check logs nothing (it says it is disabled), and the one Undo "
          "leaves the log as before",
          double == 1 and later == 1 and said == "true" and stored(page)["entries"] == before, (double, later, said))
    ctx.close()


# ── 15. the gram sheet: amount selected, Enter logs, chips with the pack, macros carbs / protein / fat ──
def check_sheet_keys(browser, errors):
    ctx, page = A.phone(browser, errors, "sheet-keys", text=1.0)
    A.open_today(page, URL)
    add_entries(page, [entry(1, CHICKEN, "2026-10-01", "dinner", "350 g", 350)])
    go(page, "add", "dinner")
    row_button(page, CHICKEN, "open").click()
    sheet(page).wait_for()
    sel = page.evaluate("() => { const i = document.activeElement; return [i.name, i.value, i.selectionStart, i.selectionEnd]; }")
    CHECK("the gram sheet opens with the amount focused and selected", sel == ["amount", "350", 0, 3], sel)
    shade = page.evaluate("""() => { const i = document.activeElement, c = document.createElement('canvas').getContext('2d');
        const rgba = v => { c.clearRect(0, 0, 1, 1); c.fillStyle = '#f00'; c.fillStyle = v; c.fillRect(0, 0, 1, 1); return [...c.getImageData(0, 0, 1, 1).data]; };
        const s = getComputedStyle(i, '::selection'); return { bg: s.backgroundColor, rgba: rgba(s.backgroundColor) }; }""")
    px = shade["rgba"]
    CHECK("the selected amount is marked in a grey of the ink (no hue: not the browser's blue), and visibly",
          max(px[:3]) - min(px[:3]) <= 2 and px[3] > 0, shade)
    n = len(stored(page)["entries"])
    page.keyboard.type("abc")
    page.keyboard.press("Enter")
    grams = page.get_by_label("Grams")
    CHECK("typing replaces the amount; Enter with 'abc' says why and logs nothing",
          grams.input_value() == "abc" and "not a number" in err_text(page) and len(stored(page)["entries"]) == n and sheet(page).count() == 1,
          (grams.input_value(), err_text(page)))
    grams.fill("")
    grams.press("Enter")
    empty_said = err_text(page)
    grams.fill("200")
    grams.press("Enter")
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    CHECK("Enter on an empty amount asks for it; Enter on 200 logs like Add: 200 g at dinner today, back on Today",
          "Type the grams" in empty_said and len(stored(page)["entries"]) == n + 1 and e["amount"] == "200 g" and e["grams"] == 200
          and e["meal"] == "dinner" and e["date"] == TODAY.isoformat() and e["totals"] == totals(page, CHICKEN, 200), (empty_said, e))

    page.evaluate("""() => Pantry.change(d => { d.foods.push({ id: 'test-pack', name: 'Test Yoghurt Tub', per100: { kcal: 97, protein: 9,
        carbs: 3.6, fat: 5 }, servings: [{ label: '1 pack', grams: 170, kcal: 164.9 }], source: 'label' }); })""")
    add_entries(page, [entry(11, "test-pack", "2026-10-01", "breakfast", "150 g", 150), entry(12, "test-pack", "2026-10-02", "breakfast", "150 g", 150)])
    go(page, "food", "test-pack", "breakfast")
    chips = page.locator(".log-chip").all_inner_texts()
    macros = page.evaluate("() => [...document.querySelectorAll('.log-macros > span')].map(s => s.firstChild.textContent.trim())")
    bars = page.evaluate("() => [...document.querySelectorAll('.log-bars > span')].map(s => s.title.split(' ')[0])")
    CHECK("the chips are his usual 150 g, then the pack size (170 g pack), no use counts; the macros read carbs, protein, fat",
          chips == ["150 g", "170 g pack"] and macros == ["Carbs", "Protein", "Fat"] and bars == macros, (chips, macros, bars))
    page.locator(".log-chip", has_text="pack").click()
    page.get_by_role("button", name="Add to breakfast").click()
    page.wait_for_selector('[data-screen="today"]')
    e = stored(page)["entries"][-1]
    CHECK("the pack chip logs '1 pack' with the pack's 170 g and their totals",
          e["foodId"] == "test-pack" and e["amount"] == "1 pack" and e["grams"] == 170 and e["totals"] == totals(page, "test-pack", 170), e)
    go(page, "food", "test-pack", "breakfast")
    chips = page.locator(".log-chip").all_inner_texts()
    CHECK("once logged, the pack is still one chip", chips == ["150 g", "170 g pack"], chips)
    ctx.close()


# ── 16. 360 x 780 at text 1.0 (his phone): ticks, checks, yesterday's row and the Add bar fit, both themes ──
def check_comfort_layout(browser, errors):
    for scheme, canvas in (("dark", "rgb(14, 14, 14)"), ("light", "rgb(247, 247, 247)")):
        ctx = browser.new_context(**A.PHONE, color_scheme=scheme)
        ctx.clock.set_fixed_time(A.NOW)
        page = ctx.new_page()
        A.watch(page, errors, f"comfort-{scheme}")
        A.set_text(page, 1.0)
        A.open_today(page, URL)
        doc = fixture_doc()
        load(page, doc)
        where = f"360 px, text 100 %, {scheme}"
        go(page, "add", "dinner")
        whole = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('[data-screen] .log-row .name')]
          .map(e => [e.textContent, e.scrollWidth <= e.clientWidth]))""")
        CHECK(f"the tick costs the names no width: his dinner foods 'Margherita Family Pizza' and 'Washed White Potato' show whole, "
              f"as on design 2 ({where})",
              whole.get("Margherita Family Pizza") is True and whole.get("Washed White Potato") is True, whole)
        pair = page.evaluate("""() => { const b = document.querySelector('.log-again'); if (!b) return null;
          const r = s => b.querySelector(s).getBoundingClientRect(), n = r('.name'), s = r('.sub'), p = r('.log-plus');
          const tenth = v => Math.round(v * 10) / 10;
          return { gap: tenth(s.top - n.bottom), off: tenth((n.top + s.bottom) / 2 - (p.top + p.bottom) / 2),
                   lines: Math.round(s.height / parseFloat(getComputedStyle(b.querySelector('.sub')).lineHeight)) }; }""")
        CHECK(f"yesterday's row with one food (his pizza): its name sits directly over its one kcal line, as in the rows below, "
              f"and the pair is centred on its circle ({where})",
              bool(pair) and pair["lines"] == 1 and abs(pair["gap"]) <= 1 and abs(pair["off"]) <= 2, pair)
        go(page, "add", "breakfast")
        page.get_by_role("tab", name="My foods").click()
        loaf = food_id(doc, LOAF_NAME)
        tick(page, loaf)
        tick(page, food_id(doc, "Washed White Potato"))
        A.fits(page, f"meal list with yesterday's row, checks, two ticks and the Add bar ({where})")
        A.rows_single_line(page, f"meal list with ticks ({where})")
        settle(page)                                     # the check's scale-in has finished
        look = page.evaluate("""n => { const name = [...document.querySelectorAll('.log-row .name')].find(e => e.textContent === n);
          const li = document.querySelector('.log-row:has(.log-tick input:checked)'), tick = li.querySelector('.log-tick').getBoundingClientRect();
          const box = li.querySelector('.log-box').getBoundingClientRect(), art = li.querySelector('.log-food').getBoundingClientRect();
          const round = b => [b.left, b.top, b.width, b.height].map(Math.round);
          return { loafCut: name.scrollWidth > name.clientWidth, tick: [Math.round(tick.width), Math.round(tick.height), li.clientHeight],
                   over: JSON.stringify(round(box)) === JSON.stringify(round(art)),
                   bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme }; }""", LOAF_NAME)
        CHECK(f"the long loaf name ends in an ellipsis, the tick's target is at least 44 px wide and the row's height, its "
              f"check fills the drawing's circle, the {scheme} canvas renders ({where})",
              look["loafCut"] and look["tick"][0] >= 44 and look["tick"][1] == look["tick"][2] and look["over"]
              and look["bg"] == canvas and look["theme"] == scheme, look)
        again = page.evaluate("""() => { const b = document.querySelector('.log-again'); if (!b) return null;
          const name = b.querySelector('.name'), sub = b.querySelector('.sub'), s = getComputedStyle(sub);
          return { name: name.textContent, nameWhole: name.scrollWidth <= name.clientWidth, sub: sub.textContent,
                   subWhole: sub.scrollHeight <= sub.clientHeight + 1, lines: Math.round(sub.clientHeight / parseFloat(s.lineHeight)),
                   artLeft: Math.round(b.querySelector('.log-art, .log-food').getBoundingClientRect().left),
                   rowArtLeft: Math.round(document.querySelector('.log-row .log-food').getBoundingClientRect().left) }; }""")
        CHECK(f"yesterday's row shows 'Same as yesterday's breakfast' whole and names every food of its 3 in at most four lines; "
              f"its drawing stands in the rows' drawing column ({where})",
              bool(again) and again["name"] == "Same as yesterday's breakfast" and again["nameWhole"] and again["subWhole"]
              and again["sub"].count(", ") == 2 and 1 <= again["lines"] <= 4 and again["artLeft"] == again["rowArtLeft"], again)
        page.locator('[data-screen] [data-act="add-ticked"]').click()
        wait_toast(page, "2 foods added to breakfast")
        A.fits(page, f"meal list with the toast after Add ({where})")
        ctx.close()


def main():
    global URL
    srv, site, URL = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn in (("ranking", check_ranking), ("plus", check_plus), ("sheet", check_sheet), ("servings", check_servings),
                             ("search", check_search), ("routes", check_routes), ("drawings", check_drawings),
                             ("history", check_history), ("layout", check_layout), ("amounts", check_amounts),
                             ("meal line", check_meal_line), ("ticks", check_ticks), ("ticks meet", check_ticks_meet),
                             ("yesterday", check_yesterday),
                             ("instant", check_instant), ("sheet keys", check_sheet_keys), ("comfort layout", check_comfort_layout)):
                A.guarded(f"{name} scenario", fn, browser, errors)
            browser.close()
        CHECK("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    print(f"\n{'ALL PASS' if not A.FAILS else str(len(A.FAILS)) + ' FAIL'}")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())

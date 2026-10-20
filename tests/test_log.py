"""Checks for Task-03: the meal list and the gram sheet (app/log.js) and the food drawings (app/drawings.js).

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
    CHECK("the gram sheet offers 350 g first, its chips are the usual amounts with how often",
          page.get_by_label("Grams").input_value() == "350" and [c.replace("\n", "") for c in chips] == ["350 g5×", "375 g1×"]
          and page.locator('.log-chip[aria-pressed="true"]').inner_text().startswith("350 g"), chips)
    grams = page.get_by_label("Grams")
    page.get_by_role("radio", name="Breakfast").check()
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    CHECK("the Breakfast radio brings breakfast's usual grams and chips (120 g), not dinner's",
          chips == ["120 g1×"] and grams.input_value() == "120" and page.get_by_role("button", name="Add to breakfast").count() == 1,
          (chips, grams.input_value()))
    grams.fill("200")
    page.get_by_role("radio", name="Dinner").check()
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    CHECK("an amount he typed stays when the meal changes, and the chips follow the meal",
          grams.input_value() == "200" and chips == ["350 g5×", "375 g1×"], (chips, grams.input_value()))
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
    CHECK("the toast says what was added where, with Undo", "350 g added to dinner on 8 Aug" in toast and "Undo" in toast, toast)
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
    CHECK("Today shows the toast with Undo", toast.count() == 1 and "375 g added to dinner" in toast.inner_text(), toast.count())
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
    e = stored(page)["entries"][-1]
    toast = page.locator("#toast .toast").inner_text()
    CHECK("the serving food's row reads '1 serving' (stored as MyNetDiary's '1 servings') and + logs it at its totals",
          r.get("sub") == "Roy Rogers, 1 serving" and r.get("kcal") == "350" and e.get("amount") == "1 servings"
          and "1 serving added to lunch" in toast and e.get("grams") is None and e.get("totals") == roy_entry["totals"], (r, e, toast))

    go(page, "food", ROY, "lunch", "2026-08-08")
    field = page.get_by_label("Number of servings")
    chips = [c.replace("\n", "") for c in page.locator(".log-chip").all_inner_texts()]
    unit = page.locator('[data-test="unit"]').inner_text()
    CHECK("a food with no per100 offers its servings, not grams; the chip and the unit both say '1 serving'",
          field.count() == 1 and page.get_by_label("Grams").count() == 0 and "350 kcal per serving" in sheet(page).inner_text()
          and unit == "serving" and bool(chips) and all(c.rstrip("0123456789×") == "1 serving" for c in chips),
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


def main():
    global URL
    srv, site, URL = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn in (("ranking", check_ranking), ("plus", check_plus), ("sheet", check_sheet), ("servings", check_servings),
                             ("search", check_search), ("routes", check_routes), ("drawings", check_drawings),
                             ("history", check_history), ("layout", check_layout), ("amounts", check_amounts)):
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

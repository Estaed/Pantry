"""Checks for Scan and New food (tasks/Task-04.md): his foods, the store catalogue, Open Food Facts, the label form.

Run from the repo root: python tests/test_scan.py   (exit 0 = no FAIL). Reuses the gate's server, phone and fake camera
and barcode reader from tests/acceptance.py. Open Food Facts is never called: every request to world.openfoodfacts.org
is answered here and recorded, from the real answers saved under tests/fixtures/scan/ (URL and fetch date inside).
Synthetic barcodes (in-store '2' prefix), answers and catalogue lines built in code exercise a rule; committed fixtures
stay real. Screens are reached by route (Pantry.go), never through another feature's DOM; the gram sheet is another
feature, so opening it is checked by its route in the address.
Set PANTRY_SCAN_SHOTS=<folder> to also save screenshots of each screen for a look.
"""
import copy
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

FIX = A.ROOT / "tests" / "fixtures" / "scan"
OFF_HIT = json.loads((FIX / "off-9312726072232.json").read_text(encoding="utf-8"))
OFF_MISS = json.loads((FIX / "off-9300000000026.json").read_text(encoding="utf-8"))
CATALOGUE = json.loads((FIX / "catalogue-woolworths-tzatziki.json").read_text(encoding="utf-8"))["item"]
OFF_ORIGIN = "https://world.openfoodfacts.org/"
LISTED = {"kcal", "protein", "carbs", "sugars", "fat", "satFat", "salt", "fibre"}
UNLISTED_WORDS = ["Iron", "Caffeine", "Vitamin", "Zinc", "Copper", "Selenium", "Starch", "Choline", "Magnesium", "Sodium",
                  "Phosphorus", "Manganese", "Nova", "Added sugars"]
TZATZIKI, CHICKEN = A.STARTER[1][0], A.STARTER[0][0]
EAN, EAN_BAD = A.EAN, A.EAN_BAD          # the Willow Farm tzatziki of design/screens.html, and a wrong check digit
MISS = OFF_MISS["body"]["code"]          # 9300000000026: a valid code Open Food Facts does not know
SHOTS = os.environ.get("PANTRY_SCAN_SHOTS")


def ean(first12):
    d = [int(c) for c in first12]
    return first12 + str((10 - sum(v * (3 if i % 2 else 1) for i, v in enumerate(d)) % 10) % 10)


OWN, ZERO, KCAL, DOWN, CUT, OFFLINE, SALT = (ean(f"2000000000{n:02d}") for n in (1, 2, 3, 4, 5, 6, 7))
PLUS = "M5 12h14M12 5v14"                # core's plus icon, drawn before "Save and choose grams" in design 6 and 6b


class Off:
    """Open Food Facts stand-in: code -> (status, body) or 'abort'; unknown codes get the real not-found answer."""

    def __init__(self):
        self.answers = {EAN: (OFF_HIT["status"], OFF_HIT["body"]), MISS: (OFF_MISS["status"], OFF_MISS["body"])}
        self.asked = []

    def handle(self, route):
        url = route.request.url
        self.asked.append(url)
        m = re.search(r"/api/v2/product/(\d+)\.json", url)
        code = m.group(1) if m else ""
        answer = self.answers.get(code) or (404, {**OFF_MISS["body"], "code": code})
        if answer == "abort":
            route.abort()
            return
        route.fulfill(status=answer[0], headers={"Access-Control-Allow-Origin": "*"},
                      content_type="application/json; charset=utf-8", body=json.dumps(answer[1]))


def watch(page, errors, tag):
    """The gate's error watch, except Chrome's own line for an Open Food Facts 404 or 503 (a miss, not an app error)."""
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))

    def console(m):
        if m.type != "error":
            return
        if m.text.startswith("Failed to load resource") and (m.location or {}).get("url", "").startswith(OFF_ORIGIN):
            return
        errors.append(f"[{tag}] console: {m.text}")
    page.on("console", console)


class Phone:
    def __init__(self, browser, url, errors, tag, reads=(), off=None, text=A.BIG_TEXT, formats=("ean_13", "qr_code"),
                 viewport=None):
        cfg = {"formats": list(formats) if formats else None, "reads": [list(r) for r in reads] or [[]]}
        self.off = off or Off()
        self.url = url
        self.ctx = browser.new_context(**{**A.PHONE, **({"viewport": viewport} if viewport else {})})
        self.ctx.clock.set_fixed_time(A.NOW)
        self.ctx.add_init_script(A.FAKES_JS % json.dumps(cfg))
        self.ctx.route(OFF_ORIGIN + "**", self.off.handle)
        self.requests = []
        self.ctx.on("request", lambda r: self.requests.append(r.url))
        self.page = self.ctx.new_page()
        watch(self.page, errors, tag)
        A.set_text(self.page, text)
        A.open_today(self.page, url)
        self.tag = tag

    def outside(self):
        local = self.url.split("/Pantry/")[0]
        return [u for u in self.requests if u.startswith("http") and not u.startswith(local)]

    def go(self, *args):
        self.page.evaluate("a => Pantry.go(...a)", list(args))

    def hash(self):
        return self.page.evaluate("location.hash")

    def wait_hash(self, prefix):
        self.page.wait_for_function("p => location.hash.startsWith(p)", arg=prefix, timeout=10000)
        return self.hash()

    def food_hash(self, food_id, meal, date):
        return self.page.evaluate("a => '#/' + ['food', ...a].map(encodeURIComponent).join('/')", [food_id, meal, date])

    def doc(self):
        return self.page.evaluate("() => Pantry.doc()")

    def tracks(self):
        return self.page.evaluate(A.TRACKS_JS)

    def fields(self):
        return self.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('[data-screen="newfood"] form input[name]')]
            .filter(i => i.type !== 'hidden').map(i => [i.name, i.value]))""")

    def unit(self, name, want):
        """Tap the unit beside a field until it shows want (one tap switches to the other unit)."""
        box = self.page.locator(f'[data-screen="newfood"] input[type="hidden"][name="{name}"]')
        for _ in range(2):
            if box.input_value() == want:
                return
            self.page.locator(f'[data-screen="newfood"] [data-unit="{name}"]').click()
        raise AssertionError(f"{name} never showed {want}")

    def fill(self, values):
        for name, value in values.items():
            self.page.locator(f'[data-screen="newfood"] input[name="{name}"]').fill(value)

    def save(self):
        self.page.get_by_role("button", name="Save and choose grams").click()

    def error(self):
        """What the form says is wrong: the messages under its fields, in the form's order."""
        return " ".join(t.strip() for t in self.page.locator('[data-screen="newfood"] .newfood-msg').all_inner_texts())

    def text(self):
        return self.page.locator('[data-screen]').inner_text()

    def shot(self, name):
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=True)

    def close(self):
        self.ctx.close()


def themes(ph, name, selector, dark_bg, light_bg):
    """Dark and light both render: the theme follows the phone and the element takes the token of each."""
    page = ph.page
    got = {}
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function("s => document.documentElement.dataset.theme === s", arg=scheme)
        got[scheme] = page.evaluate("s => { const el = document.querySelector(s); return el && [getComputedStyle(el).backgroundColor, getComputedStyle(document.body).color]; }", selector)
        ph.shot(f"{name}-{scheme}")
    A.check(f"{name}: renders in dark and in light with the theme's tokens",
            got["dark"] and got["light"] and got["dark"][0] == dark_bg and got["light"][0] == light_bg
            and got["dark"][1] == "rgb(238, 238, 238)" and got["light"][1] == "rgb(18, 18, 18)", got)


BOXES_JS = """keys => Object.fromEntries(keys.map(k => {
  const r = document.querySelector(`[data-screen="newfood"] [data-field="${k}"] .newfood-in`).getBoundingClientRect();
  return [k, [Math.round(r.top), Math.round(r.height)]]; }))"""
FOUND_ORDER_JS = """() => [...document.querySelectorAll('[data-screen="newfood"] .newfood-src, [data-screen="newfood"] .newfood-picks, [data-screen="newfood"] [data-field]')]
  .map(el => el.dataset.field ? [el.dataset.field, el.querySelector('label').textContent.trim()] : [el.className.split(' ')[0]])"""
FOUND_ORDER = [["newfood-src"], ["newfood-picks"], ["kcal", "Energy"], ["carbs", "Carbs"], ["protein", "Protein"], ["fat", "Fat"],
               ["sugars", "Sugars"], ["satFat", "Saturated fat"], ["pack", "Pack size"], ["name", "Name in your foods"]]
BAR_JS = """() => { const r = document.querySelector('[data-screen="newfood"] .bottom').getBoundingClientRect();
  const m = document.querySelector('[data-screen="newfood"] .newfood-msg'), q = m && m.getBoundingClientRect();
  return { bar: [Math.round(r.top), Math.round(r.height)], msg: q && [Math.round(q.top), Math.round(q.bottom)],
           focus: document.activeElement && document.activeElement.name }; }"""


def level(ph, pairs, what):
    """Two fields side by side keep their boxes level and the same height, whatever a label or a message under one does."""
    boxes = ph.page.evaluate(BOXES_JS, sorted({k for pair in pairs for k in pair}))
    A.check(f"{what}: the boxes beside each other stay level and keep their height ({', '.join(' | '.join(p) for p in pairs)})",
            all(boxes[a] == boxes[b] for a, b in pairs), boxes)


def new_food(before, after):
    old = {f["id"] for f in before["foods"]}
    return [f for f in after["foods"] if f["id"] not in old]


def held(ph, where, length, what):
    """Back on Scan with the pack still in view: the reader returns the same code on every pass, and Scan stays."""
    page = ph.page
    start = page.evaluate("window.__fake.detect")
    page.wait_for_function("a => window.__fake.detect >= a[0] || location.hash !== a[1]", arg=[start + 12, where], timeout=10000)
    hint = page.evaluate("() => { const s = document.querySelector('[data-test=\"scan-status\"]'); return s ? s.textContent.trim() : null; }")
    got = (ph.hash(), page.evaluate("history.length"), ph.tracks()[-1:], hint)
    A.check(f"back on Scan with the pack still in view, the code that opened {what} does not open it again "
            "(12 reads later: still on Scan, the camera live, no new history entry, asking for another barcode)",
            got == (where, length, ["live"], "Point at another barcode"), (got, length))


# ── scenarios ─────────────────────────────────────────────────────
def own_food(browser, url, errors):
    ph = Phone(browser, url, errors, "own", reads=[[], [OWN]])
    ph.page.evaluate("a => Pantry.change(d => { d.foods.find(f => f.id === a[0]).barcode = a[1]; })", [CHICKEN, OWN])
    ph.go("scan", "dinner", "2026-10-19")
    got = ph.wait_hash("#/food/")
    A.check("a code saved with one of his foods opens food <id> <meal> <date> from the route",
            got == ph.food_hash(CHICKEN, "dinner", "2026-10-19"), got)
    A.check("... with no lookup request and no other request off the phone", not ph.off.asked and not ph.outside(), ph.outside())
    A.check("... and the camera is stopped on the way out", ph.tracks() and set(ph.tracks()) == {"ended"}, ph.tracks())
    length = ph.page.evaluate("history.length")
    ph.page.go_back()                                              # the pack stays in view: the reader keeps returning it
    code = ph.page.locator('[data-screen="scan"] [data-test="scan-code"]')
    code.wait_for(state="visible")
    A.check("back on Scan (the back gesture), the code it read is shown with how long the read took",
            re.sub(r"\D", "", code.inner_text()) == OWN
            and re.search(r"Read in \d+\.\d s", ph.page.locator('[data-screen="scan"]').inner_text()) is not None,
            ph.page.locator('[data-screen="scan"]').inner_text())
    held(ph, "#/scan/dinner/2026-10-19", length, "his food's gram sheet")
    ph.shot("scan-held")
    ph.page.get_by_role("button", name="Open it again").click()
    got = ph.wait_hash("#/food/")
    A.check('... "Open it again" opens that gram sheet once more, with no new history entry',
            got == ph.food_hash(CHICKEN, "dinner", "2026-10-19") and ph.page.evaluate("history.length") == length, got)
    ph.page.go_back()
    ph.page.wait_for_selector('[data-screen="scan"] [data-test="scan-code"]')
    ph.page.go_back()
    ph.page.wait_for_selector('[data-screen="today"]')
    A.check("... and the next Back leaves Scan for Today, the camera stopped", set(ph.tracks()) == {"ended"}, ph.tracks())
    ph.page.evaluate("a => { window.__cfg.reads = [[a]]; }", OWN)
    ph.go("scan")
    got = ph.wait_hash(ph.food_hash(CHICKEN, "breakfast", "2026-10-20"))
    A.check("opened with no meal and date (Today's scan button), it passes the clock's meal and today",
            got == ph.food_hash(CHICKEN, "breakfast", "2026-10-20"), got)
    ph.close()


def catalogue(browser, url, errors):
    ph = Phone(browser, url, errors, "catalogue", reads=[[], [EAN]])
    ph.page.evaluate("item => Pantry.change(d => { d.catalogue = [item]; })", CATALOGUE)
    before = ph.doc()
    ph.go("scan", "lunch", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    src = ph.page.locator('[data-screen="newfood"] .newfood-src').inner_text()
    A.check("a catalogue code shows Found with the product's name, per 100 g kcal and its store tag",
            "Willow Farm Dip Tzatziki 200g" in src and "108 kcal per 100 g" in src
            and ph.page.locator(".newfood-tag").inner_text().strip() == "Woolworths", src)
    want = {"kcal": "108", "protein": "5.7", "carbs": "8.4", "sugars": "3.4", "fat": "5.5", "satFat": "2.2", "pack": "200",
            "name": "Willow Farm Dip Tzatziki"}
    A.check("Found holds the catalogue's six values, its pack size and the name for his list", ph.fields() == want, ph.fields())
    order = ph.page.evaluate(FOUND_ORDER_JS)
    A.check('Found keeps design 6\'s order (the product, the six values, the pack size) with the macros as carbs, protein, fat '
            '(Pantry.MACROS), "This is my …" under the product and the name for his list last', order == FOUND_ORDER, order)
    eyebrow = ph.page.locator('[data-screen="newfood"] .top .eyebrow').inner_text().strip()
    A.check("Found names the barcode in its eyebrow and is titled New food",
            eyebrow == f"Barcode {EAN}" and ph.page.locator('[data-screen="newfood"] h1').inner_text().strip() == "New food", eyebrow)
    A.check("a catalogue hit makes no network request", not ph.off.asked and not ph.outside(), ph.outside())
    A.check("the camera is stopped when Scan opens Found", set(ph.tracks()) == {"ended"}, ph.tracks())
    A.fits(ph.page, "Found from the catalogue, 150 % text")
    A.rows_single_line(ph.page, "Found, This is my")
    ph.shot("found-catalogue")

    length = ph.page.evaluate("history.length")
    ph.page.go_back()
    ph.page.wait_for_selector('[data-screen="scan"] [data-test="scan-code"]')
    held(ph, "#/scan/lunch/2026-10-20", length, "Found")
    ph.page.get_by_role("button", name="Open it again").click()
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    A.check('... "Open it again" opens Found once more, with no new history entry and no request',
            ph.hash() == f"#/newfood/{EAN}/lunch/2026-10-20" and ph.page.evaluate("history.length") == length
            and not ph.off.asked and not ph.outside(), (ph.hash(), ph.outside()))

    ph.save()
    got = ph.wait_hash("#/food/")
    after = ph.doc()
    added = new_food(before, after)
    food = added[0] if len(added) == 1 else {}
    A.check("saving adds one food: source woolworths, the barcode, the catalogue's per100, the pack as a serving",
            len(added) == 1 and food == {"id": food.get("id"), "name": "Willow Farm Dip Tzatziki", "barcode": EAN,
                                         "per100": CATALOGUE["per100"], "servings": [{"label": "1 pack", "grams": 200, "kcal": 216}],
                                         "source": "woolworths"}, added)
    A.check("... and opens its gram sheet for the meal and day he came from", got == ph.food_hash(food.get("id"), "lunch", "2026-10-20"), got)

    ph.go("scan", "lunch", "2026-10-20")
    got = ph.wait_hash("#/food/")
    A.check("scanning a saved product again opens the same food and stores nothing new",
            got == ph.food_hash(food.get("id"), "lunch", "2026-10-20") and len(ph.doc()["foods"]) == len(after["foods"]), got)
    A.check("... with no request", not ph.off.asked and not ph.outside(), ph.outside())

    ph.go("newfood", EAN, "lunch", "2026-10-20")       # the back gesture from the gram sheet lands here
    ph.page.get_by_role("button", name="Choose grams").wait_for()
    A.check("New food for a code that is now saved says so and offers that food's gram sheet",
            "already saved" in ph.text() and "Willow Farm Dip Tzatziki" in ph.text())
    A.fits(ph.page, "New food, code already saved, 150 % text")
    ph.page.get_by_role("button", name="Choose grams").click()
    got = ph.wait_hash("#/food/")
    A.check("... and Choose grams opens it", got == ph.food_hash(food.get("id"), "lunch", "2026-10-20"), got)
    ph.close()


def open_food_facts(browser, url, errors):
    ph = Phone(browser, url, errors, "off", reads=[[], [EAN]])
    before = ph.doc()
    ph.go("scan", "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    A.check("a code in neither his foods nor the catalogue asks Open Food Facts once, at the task's URL",
            ph.off.asked == [OFF_HIT["url"]], ph.off.asked)
    src = ph.page.locator('[data-screen="newfood"] .newfood-src').inner_text()
    A.check("Found shows the brand and 108 kcal per 100 g from Open Food Facts, tagged as such",
            "Willow Farm, 108 kcal per 100 g" in src and ph.page.locator(".newfood-tag").inner_text().strip() == "Open Food Facts", src)
    want = {"kcal": "108", "protein": "5.5", "carbs": "8.5", "sugars": "3.5", "fat": "5.5", "satFat": "2", "pack": "", "name": "Tzatziki dip"}
    A.check("Found holds the six listed values, Energy in whole kcal (107.55 shows as 108, as the line above it says); "
            "the pack size (no quantity) stays empty", ph.fields() == want, ph.fields())
    shown = [w for w in UNLISTED_WORDS if w.lower() in ph.text().lower()]
    A.check("none of the fields Open Food Facts reports as 0 without knowing them is shown", not shown, shown)
    picks = [t.strip() for t in ph.page.locator(".newfood-picks .fr .name").all_inner_texts()]
    A.check('"This is my …" lists his tzatziki for "tzatziki dip" on the starter document', picks == ["Classic Tzatziki Dip"], picks)
    A.fits(ph.page, "Found from Open Food Facts, 150 % text")
    ph.shot("found-off")
    themes(ph, "Found", '[data-screen="newfood"] .newfood-in', "rgb(35, 35, 35)", "rgb(240, 240, 240)")

    ph.save()
    got = ph.wait_hash("#/food/")
    added = new_food(before, ph.doc())
    food = added[0] if len(added) == 1 else {}
    per100 = food.get("per100", {})
    A.check("saved per100 holds only the listed fields, unknown ones stay absent",
            per100 and set(per100) <= LISTED and "fibre" not in per100, per100)
    n = OFF_HIT["body"]["product"]["nutriments"]
    source = {"kcal": n["energy-kcal_100g"], "protein": n["proteins_100g"], "carbs": n["carbohydrates_100g"], "fat": n["fat_100g"],
              "sugars": n["sugars_100g"], "satFat": n["saturated-fat_100g"], "salt": n["salt_100g"]}
    A.check("saving with no edit gives source off with Open Food Facts' own numbers, unrounded (107.55258126195 kcal, not the 108 "
            "shown), salt kept as it came", per100 == source and food.get("source") == "off" and food.get("barcode") == EAN
            and food.get("name") == "Tzatziki dip" and food.get("brand") == "Willow Farm" and food.get("servings") == [], food)
    A.check("... and opens its gram sheet", got == ph.food_hash(food.get("id"), "dinner", "2026-10-20"), got)
    ph.close()


def listed_zero(browser, url, errors):
    """A synthetic answer from the real one: carbohydrates 0 (real for meat) and no energy-kcal (kJ only)."""
    off = Off()
    body = copy.deepcopy(OFF_HIT["body"])
    body["code"] = ZERO
    n = body["product"]["nutriments"]
    n["carbohydrates_100g"] = 0
    del n["energy-kcal_100g"], n["energy-kcal"]
    off.answers[ZERO] = (200, body)
    ph = Phone(browser, url, errors, "zero", reads=[[], [ZERO]], off=off)
    before = ph.doc()
    ph.go("scan", "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    f = ph.fields()
    src = ph.page.locator('[data-screen="newfood"] .newfood-src').inner_text()
    A.check("a listed 0 from Open Food Facts is shown as 0; energy in kJ only becomes kcal ÷ 4.184 (441.5 kJ: 106 kcal), "
            "the same number in the line above and in the Energy box",
            f.get("carbs") == "0" and f.get("kcal") == "106" and "106 kcal per 100 g" in src, (f, src))
    ph.fill({"kcal": ""})
    ph.save()
    A.check("Found with Energy cleared says so in words and saves nothing", "energy" in ph.error().lower() and ph.doc() == before, ph.error())
    level(ph, [("kcal", "carbs"), ("protein", "fat"), ("sugars", "satFat")], "Found at 150 % text with Energy cleared")
    ph.fill({"kcal": "106", "fat": "5,8", "sugars": ""})        # energy typed back as shown, fat changed, sugars cleared
    ph.save()
    ph.wait_hash("#/food/")
    added = new_food(before, ph.doc())
    per100 = added[0]["per100"] if len(added) == 1 else {}
    A.check("a listed 0 is kept in per100 (0 g carbs is real)", per100.get("carbs") == 0 and "carbs" in per100, per100)
    A.check("kJ-only energy is stored as kJ ÷ 4.184, unrounded, when the box is left as shown", per100.get("kcal") == 441.5 / 4.184, per100)
    A.check("a changed value is stored as typed, a cleared one is dropped, the rest keep the source's numbers",
            per100.get("fat") == 5.8 and "sugars" not in per100 and per100.get("protein") == 5.5 and per100.get("satFat") == 2
            and per100.get("salt") == 0.95, per100)
    ph.close()


def this_is_my(browser, url, errors):
    ph = Phone(browser, url, errors, "mine", reads=[[], [EAN]])
    before = ph.doc()
    ph.go("scan", "dinner", "2026-10-20")
    pick = ph.page.get_by_role("button", name=re.compile("^This is my Classic Tzatziki Dip"))
    pick.wait_for()
    pick.click()
    got = ph.wait_hash("#/food/")
    after = ph.doc()
    old = next(f for f in before["foods"] if f["id"] == TZATZIKI)
    new = next(f for f in after["foods"] if f["id"] == TZATZIKI)
    A.check('picking "This is my Classic Tzatziki Dip" adds the barcode to that food and nothing else',
            new == {**old, "barcode": EAN} and len(after["foods"]) == len(before["foods"]), new)
    A.check("... makes no new food and opens its gram sheet", not new_food(before, after)
            and got == ph.food_hash(TZATZIKI, "dinner", "2026-10-20"), got)
    asked = len(ph.off.asked)
    ph.go("scan", "dinner", "2026-10-20")
    got = ph.wait_hash("#/food/")
    A.check("scanning it again opens his tzatziki with no lookup", got == ph.food_hash(TZATZIKI, "dinner", "2026-10-20")
            and len(ph.off.asked) == asked and len(ph.doc()["foods"]) == len(before["foods"]), (got, ph.off.asked))
    ph.close()


def label_form(browser, url, errors):
    ph = Phone(browser, url, errors, "label", reads=[[], [MISS]])
    before = ph.doc()
    ph.go("scan", "snacks", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    eyebrow = ph.page.locator('[data-screen="newfood"] .top .eyebrow').inner_text().strip()
    A.check("a code found nowhere shows From the label, saying it was not found",
            ph.page.locator('[data-screen="newfood"] h1').inner_text().strip() == "From the label"
            and eyebrow == "Not found in any catalogue" and ph.off.asked == [OFF_MISS["url"]], (eyebrow, ph.off.asked))
    shown = ph.page.evaluate("""() => [...document.querySelectorAll('[data-screen="newfood"] [data-field]')]
        .filter(b => b.getClientRects().length).map(b => [b.dataset.field, b.querySelector('label').textContent.trim()])""")
    A.check("From the label asks what design 6b shows: name, brand, pack size, energy (kJ or kcal), then the macros as "
            "carbs, protein, fat (Pantry.MACROS), with 6b's kJ line; sugars, salt and fibre wait behind one button",
            shown == [["name", "Name"], ["brand", "Brand"], ["pack", "Pack size"], ["energy", "Energy (kJ or kcal)"],
                      ["carbs", "Carbs"], ["protein", "Protein"], ["fat", "Fat"]]
            and "kJ is turned into kcal." in ph.text()
            and ph.page.get_by_role("button", name="Add sugars, salt and fibre").is_visible(), shown)
    ph.shot("label-empty")
    ph.save()
    A.check("saving with no name says so in words and saves nothing", "Type the name" in ph.error() and ph.doc() == before, ph.error())
    ph.fill({"name": "Greek yoghurt"})
    ph.save()
    A.check("saving with no energy says so in words and saves nothing", "energy" in ph.error().lower() and ph.doc() == before, ph.error())
    level(ph, [("energy", "carbs"), ("protein", "fat")], "From the label at 150 % text with no energy")
    ph.fill({"energy": "about 450"})
    ph.save()
    A.check("energy that is not a number is refused in words", "type a number" in ph.error() and ph.doc() == before, ph.error())
    ph.unit("energyUnit", "kcal")
    ph.fill({"energy": "2000"})
    ph.save()
    A.check("2,000 kcal per 100 g is refused as more than pure fat (kJ typed as kcal)", "more than pure fat" in ph.error()
            and ph.doc() == before, ph.error())
    A.fits(ph.page, "From the label with an error, 150 % text")
    ph.shot("label-error")
    ph.unit("energyUnit", "kJ")
    ph.fill({"energy": "452", "brand": "Willow Farm", "pack": "200", "protein": "5.5", "fat": "5,5", "carbs": "8.5"})
    ph.page.get_by_role("button", name="Add sugars, salt and fibre").click()
    ph.unit("saltUnit", "mg")
    salt_label = ph.page.locator('[data-screen="newfood"] label[for="newfood-salt"]').inner_text().strip()
    A.check("salt can be typed as the sodium an Australian label prints: its unit switches to mg and the field says Sodium",
            salt_label == "Sodium", salt_label)
    ph.fill({"sugars": "3.5", "salt": "380"})
    A.fits(ph.page, "From the label with sugars, salt and fibre open, 150 % text")
    ph.shot("label-more")
    ph.save()
    got = ph.wait_hash("#/food/")
    added = new_food(before, ph.doc())
    food = added[0] if len(added) == 1 else {}
    per100 = food.get("per100", {})
    A.check("energy typed in kJ is stored as kcal = kJ ÷ 4.184", abs(per100.get("kcal", 0) - 452 / 4.184) <= 0.05, per100)
    A.check("the label food keeps what was typed (sodium 380 mg as salt 0.95 g, a comma as a decimal point) with source label",
            len(added) == 1 and food.get("source") == "label" and food.get("barcode") == MISS and food.get("name") == "Greek yoghurt"
            and {k: v for k, v in per100.items() if k != "kcal"} == {"protein": 5.5, "carbs": 8.5, "fat": 5.5, "sugars": 3.5, "salt": 0.95}
            and food.get("servings") == [{"label": "1 pack", "grams": 200, "kcal": round(per100.get("kcal", 0) * 2, 1)}], food)
    A.check("... and opens its gram sheet", got == ph.food_hash(food.get("id"), "snacks", "2026-10-20"), got)

    ph.go("newfood", KCAL, "snacks", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    before = ph.doc()
    ph.unit("energyUnit", "kcal")
    ph.fill({"name": "Protein bar", "energy": "380"})
    ph.save()
    ph.wait_hash("#/food/")
    added = new_food(before, ph.doc())
    A.check("energy typed in kcal is stored as typed, and nothing else is filled in",
            len(added) == 1 and added[0]["per100"] == {"kcal": 380} and added[0]["servings"] == [] and "brand" not in added[0], added)

    ph.go("newfood", SALT, "snacks", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    before = ph.doc()
    ph.fill({"name": "Rice crackers", "energy": "1650"})
    ph.page.get_by_role("button", name="Add sugars, salt and fibre").click()
    ph.fill({"salt": "0.8"})
    ph.save()
    ph.wait_hash("#/food/")
    added = new_food(before, ph.doc())
    A.check("salt typed in g (the unit it opens with) is stored as typed",
            len(added) == 1 and added[0]["per100"] == {"kcal": round(1650 / 4.184, 1), "salt": 0.8}, added)
    ph.close()


def down_and_offline(browser, url, errors):
    off = Off()
    off.answers[DOWN] = (503, {"status": 0, "status_verbose": "service unavailable"})
    off.answers[CUT] = "abort"
    ph = Phone(browser, url, errors, "down", off=off)
    for code, why in ((DOWN, "answered with an error (503)"), (CUT, "could not be reached")):
        ph.go("newfood", code, "dinner", "2026-10-20")
        ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
        A.check(f"Open Food Facts down ({why}) shows the label form and says so",
                "Open Food Facts did not answer" in ph.text() and why in ph.text(), ph.text()[:300])
    A.fits(ph.page, "From the label after Open Food Facts failed, 150 % text")

    asked = len(off.asked)
    ph.ctx.set_offline(True)
    ph.go("newfood", OFFLINE, "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    A.check("offline, the lookup skips Open Food Facts and says so", len(off.asked) == asked
            and ph.page.locator('[data-screen="newfood"] .top .eyebrow').inner_text().strip() == "Offline"
            and "offline, so Open Food Facts was not checked" in ph.text(), (off.asked, ph.text()[:300]))
    ph.shot("label-offline")
    ph.ctx.set_offline(False)
    off.answers[OFFLINE] = (OFF_HIT["status"], {**OFF_HIT["body"], "code": OFFLINE})
    ph.page.wait_for_function("navigator.onLine")
    ph.page.get_by_role("button", name="Try Open Food Facts again").click()
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    A.check("back online, Try again looks it up and shows Found", len(off.asked) == asked + 1 and ph.fields().get("kcal") == "108", ph.fields())
    ph.close()


def check_digit_and_typing(browser, url, errors):
    ph = Phone(browser, url, errors, "digits", reads=[[EAN_BAD]])
    ph.go("scan", "dinner", "2026-10-20")
    ph.page.wait_for_function("() => window.__fake.detect >= 12")
    A.check("an EAN-13 with a wrong check digit is ignored: not looked up, not shown, the camera keeps looking",
            ph.hash() == "#/scan/dinner/2026-10-20" and not ph.off.asked and not ph.outside()
            and ph.page.locator('[data-test="scan-code"]').is_hidden() and ph.tracks() == ["live"], (ph.hash(), ph.off.asked, ph.tracks()))
    A.fits(ph.page, "Scan with the camera live, 150 % text")
    ph.shot("scan-live")
    themes(ph, "Scan", '[data-screen="scan"] .scan-sheet', "rgb(25, 25, 25)", "rgb(255, 255, 255)")
    sheet = ph.page.locator('[data-screen="scan"] .scan-sheet').inner_text()
    A.check("the sheet says which meal it scans for and the lookup order", "Scanning for Dinner" in sheet
            and "Looks in your foods, then Coles and Woolworths, then Open Food Facts." in sheet, sheet)

    ph.page.get_by_role("button", name="Type the barcode").click()
    box = ph.page.get_by_label("Barcode", exact=True)
    for typed, said in ((EAN_BAD, "do not add up"), ("93127260", "do not add up"), ("12345", "13 digits"), ("93127x6072232", "digits only")):
        box.fill(typed)
        ph.page.get_by_role("button", name="Look it up").click()
        err = ph.page.locator(".scan-err")
        A.check(f"typed {typed}: refused in words, not looked up", err.is_visible() and said in err.inner_text()
                and ph.hash() == "#/scan/dinner/2026-10-20" and not ph.off.asked, err.inner_text())
    A.fits(ph.page, "Scan with a typed barcode refused, 150 % text")
    ph.shot("scan-typed-error")
    box.fill("9 312726 072232")
    ph.page.get_by_role("button", name="Look it up").click()
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    A.check("typed digits (spaces as printed) open Found for that code, and the camera stops",
            ph.hash().startswith(f"#/newfood/{EAN}/dinner/2026-10-20") and set(ph.tracks()) == {"ended"}, (ph.hash(), ph.tracks()))
    ph.page.go_back()
    ph.page.wait_for_selector('[data-screen="scan"] [data-test="scan-code"]')
    A.check("back on Scan, the last code is shown", re.sub(r"\D", "", ph.page.locator('[data-test="scan-code"]').inner_text()) == EAN)
    ph.close()


def camera(browser, url, errors):
    """Task-00's camera checks under the real flow: every track stops when Scan is left by any route."""
    ph = Phone(browser, url, errors, "camera-missing", formats=None)
    ph.go("scan")
    ph.page.wait_for_function("() => /BarcodeDetector/.test(document.querySelector('[data-test=\"scan-status\"]').textContent)")
    st = ph.page.locator('[data-test="scan-status"]').inner_text()
    A.check("without BarcodeDetector it says so in plain words, opens no camera and opens the barcode field",
            "no built-in barcode reader" in st and "BarcodeDetector is missing" in st and ph.page.evaluate("window.__fake.gum") == 0
            and ph.page.get_by_label("Barcode", exact=True).is_visible(), st)
    A.fits(ph.page, "Scan with no reader, 150 % text")
    ph.shot("scan-no-reader")
    ph.close()

    ph = Phone(browser, url, errors, "camera-noean", formats=("qr_code", "code_128"))
    ph.go("scan")
    ph.page.wait_for_function("() => /EAN-13/.test(document.querySelector('[data-test=\"scan-status\"]').textContent)")
    st = ph.page.locator('[data-test="scan-status"]').inner_text()
    A.check("a reader without ean_13 says so and opens no camera", "cannot read EAN-13" in st and "qr_code" in st
            and ph.page.evaluate("window.__fake.gum") == 0, st)
    ph.close()

    ph = Phone(browser, url, errors, "camera", reads=[[], ["QR-NOT-A-PACK"]])
    page = ph.page
    ph.go("scan")
    page.wait_for_function("() => window.__fake.tracks.length === 1 && window.__fake.tracks[0].readyState === 'live' && window.__fake.detect > 3")
    fake = page.evaluate("() => ({ formats: window.__fake.formats, source: window.__fake.source, facing: window.__fake.constraints.video.facingMode })")
    A.check("Scan opens the rear camera and asks the reader for ean_13 from the video",
            fake == {"formats": ["ean_13"], "source": "VIDEO", "facing": {"ideal": "environment"}}, fake)
    page.get_by_role("button", name="Back").click()
    page.wait_for_selector('[data-screen="today"]')
    A.check("leaving with Back stops every camera track", ph.tracks() == ["ended"], ph.tracks())

    ph.go("scan")
    page.wait_for_function("() => window.__fake.tracks.length === 2 && window.__fake.tracks[1].readyState === 'live'")
    page.go_back()
    page.wait_for_selector('[data-screen="today"]')
    A.check("leaving with the phone's back gesture stops every camera track", ph.tracks() == ["ended"] * 2, ph.tracks())

    ph.go("scan")
    page.wait_for_function("() => window.__fake.tracks.length === 3 && window.__fake.tracks[2].readyState === 'live'")
    page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }")
    hidden = ph.tracks()
    page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }")
    page.wait_for_function("() => window.__fake.tracks.length === 4 && window.__fake.tracks[3].readyState === 'live'")
    A.check("the app going to the background stops the camera; coming back starts it again", hidden == ["ended"] * 3, hidden)

    page.get_by_role("button", name="Back").click()
    page.wait_for_selector('[data-screen="today"]')
    page.evaluate("() => { window.__cfg.delay = 600; }")
    ph.go("scan")
    page.get_by_role("button", name="Back").click()
    page.wait_for_function("() => window.__fake.tracks.length === 5", timeout=5000)
    page.wait_for_timeout(200)
    A.check("leaving while the camera is still starting stops it when it arrives", ph.tracks() == ["ended"] * 5, ph.tracks())
    ph.close()


def narrow(browser, url, errors):
    """Chrome's zoom at 150 %: 240 CSS px."""
    ph = Phone(browser, url, errors, "narrow", reads=[[]], text=1.0, viewport={"width": 240, "height": 520})
    ph.go("scan", "dinner", "2026-10-20")
    ph.page.wait_for_function("() => window.__fake.tracks.length === 1 && window.__fake.tracks[0].readyState === 'live'")
    ph.page.get_by_role("button", name="Type the barcode").click()
    A.fits(ph.page, "Scan at 240 px")
    ph.shot("scan-240")
    ph.go("newfood", EAN, "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    A.fits(ph.page, "Found at 240 px")
    A.rows_single_line(ph.page, "Found at 240 px")
    ph.shot("found-240")
    ph.go("newfood", MISS, "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    clean = ph.page.evaluate(BAR_JS)
    ph.fill({"name": "Greek yoghurt"})
    ph.page.evaluate("scrollTo(0, 0)")
    ph.save()
    got = ph.page.evaluate(BAR_JS)
    A.check("From the label at 240 px, Save with no energy: the Save bar keeps its size, and the energy field comes into view "
            "with its message above the bar, focused", got["bar"] == clean["bar"] and got["msg"] and 0 <= got["msg"][0]
            and got["msg"][1] <= got["bar"][0] and got["focus"] == "energy", (clean, got))
    ph.fill({"name": ""})
    ph.save()
    A.fits(ph.page, "From the label with errors at 240 px")
    ph.shot("label-240")
    themes(ph, "From the label", '[data-screen="newfood"] .newfood-in', "rgb(35, 35, 35)", "rgb(240, 240, 240)")
    ph.close()


def normal_text(browser, url, errors):
    """Text at 100 % on the 360 px phone (design 6 and 6b are drawn there), and the no-reader page at 240 px with 150 % text."""
    ph = Phone(browser, url, errors, "text100", reads=[[]], text=1.0)
    ph.page.evaluate("item => Pantry.change(d => { d.catalogue = [item]; })", CATALOGUE)
    ph.go("newfood", EAN, "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] .newfood-tag')
    name = ph.page.evaluate("""() => { const i = document.querySelector('[data-screen="newfood"] input[name="name"]');
        return { value: i.value, whole: i.scrollWidth <= i.clientWidth, field: Math.round(i.closest('.newfood-field').getBoundingClientRect().width),
                 body: Math.round(i.closest('.newfood-body').getBoundingClientRect().width) }; }""")
    A.check("Found at 360 px with text at 100 %: the name he checks once is shown whole, across the full width",
            name["value"] == "Willow Farm Dip Tzatziki" and name["whole"] and name["field"] == name["body"], name)
    A.check('Found: "Save and choose grams" carries the plus icon of design 6',
            PLUS in ph.page.get_by_role("button", name="Save and choose grams").inner_html())
    first = ph.page.evaluate("""() => { scrollTo(0, 0); const bar = document.querySelector('[data-screen="newfood"] .bottom').getBoundingClientRect().top;
        const parts = [...document.querySelectorAll('[data-screen="newfood"] .newfood-src, [data-screen="newfood"] .newfood-picks .fr, [data-screen="newfood"] [data-field] .newfood-in')];
        return { bar: Math.round(bar), picks: document.querySelectorAll('[data-screen="newfood"] .newfood-picks .fr').length,
                 under: parts.filter(el => el.getBoundingClientRect().bottom > bar).map(el => (el.closest('[data-field]') || el).dataset.field || el.className) }; }""")
    A.check('Found at 360 x 780 with text at 100 %: the product, "This is my …", the six values and the pack size all sit above '
            "the Save bar, as design 6 shows them on one screen", first["picks"] == 1 and not [u for u in first["under"] if u != "name"], first)
    A.fits(ph.page, "Found, 100 % text")
    ph.shot("found-text100")

    ph.go("newfood", MISS, "dinner", "2026-10-20")
    ph.page.wait_for_selector('[data-screen="newfood"] input[name="energy"]')
    at = ph.page.evaluate("""() => Object.fromEntries(['energy', 'protein', 'carbs', 'fat'].map(k => {
        const r = document.querySelector(`[data-screen="newfood"] [data-field="${k}"] .newfood-in`).getBoundingClientRect();
        return [k, [Math.round(r.left), Math.round(r.top)]]; }))""")
    A.check("From the label at 360 px with text at 100 %: energy and carbs, then protein and fat, two across as in 6b",
            at["energy"][1] == at["carbs"][1] < at["protein"][1] == at["fat"][1]
            and at["energy"][0] == at["protein"][0] < at["carbs"][0] == at["fat"][0], at)
    A.check('From the label: "Save and choose grams" carries the plus icon of design 6b',
            PLUS in ph.page.get_by_role("button", name="Save and choose grams").inner_html())
    A.fits(ph.page, "From the label, 100 % text")
    ph.shot("label-text100")
    ph.fill({"name": "Greek yoghurt"})
    ph.save()
    level(ph, [("energy", "carbs"), ("protein", "fat")], "From the label at 100 % text with no energy")
    ph.fill({"energy": "452", "pack": "a tub"})
    ph.save()
    A.check("a pack size that is not grams is refused in words", "pack size in grams" in ph.error(), ph.error())
    level(ph, [("brand", "pack")], "From the label at 100 % text with the pack size refused")
    ph.close()

    ph = Phone(browser, url, errors, "noreader-240", formats=None, viewport={"width": 240, "height": 520})
    ph.go("scan")
    ph.page.wait_for_function("() => /BarcodeDetector/.test(document.querySelector('[data-test=\"scan-status\"]').textContent)")
    A.fits(ph.page, "Scan with no reader at 240 px, 150 % text")
    ph.shot("scan-no-reader-240")
    ph.close()


def main():
    srv, site, url = A.start_site()
    registry = (A.ROOT / "app" / "registry.js").read_bytes()
    if b"'app/newfood.js'" not in registry:          # until the orchestrator appends the line (Task-04 report)
        site.overlay[A.BASE + "app/registry.js"] = registry + b"PANTRY_FEATURES.push('app/newfood.js');\n"
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, fn in (("own food", own_food), ("catalogue", catalogue), ("Open Food Facts", open_food_facts),
                         ("listed zero", listed_zero), ("This is my", this_is_my), ("label form", label_form),
                         ("down and offline", down_and_offline), ("check digit and typing", check_digit_and_typing),
                         ("camera", camera), ("240 px", narrow), ("100 % text", normal_text)):
            A.guarded(f"{name} scenario", fn, browser, url, errors)
        browser.close()
    srv.shutdown()
    A.check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

"""Checks for Task-05: edit, move and delete an entry (app/entry.js, route '#/entry/<id>').

Run from the repo root: python tests/test_entry.py   (exit 0 = no FAIL). Reuses the gate's server and phone from
tests/acceptance.py (360 x 780, text at 150 %, Darwin, clock fixed at 2026-10-20 07:00). The document is the
committed fixture (tests/fixtures/mynetdiary-slice.json, days design/screens.html shows) run through
tools/import_mynetdiary.py, so the entries are imported MyNetDiary ones with MyNetDiary's own totals. Expected
values come from that fixture and hand-worked numbers, never from the app. Screens are reached by route, and the
day's meal totals are read from the document, not from Today's DOM.
Until app/registry.js lists app/entry.js (the orchestrator appends it at integration), the test serves a registry
with that line added.
"""
import copy
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
FIXTURE = ROOT / "tests" / "fixtures" / "mynetdiary-slice.json"
LINE = "PANTRY_FEATURES.push('app/entry.js');"
POTATO = "v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg="
DAY = "2026-08-08"
DINNER = "2026-08-08-301"      # Washed White Potato, 1000 g, 590 kcal, protein 22.6666667 (MyNetDiary's, not per100)
LUNCH = "2026-08-08-201"       # Roy Rogers roast beef sandwich, grams null, "1 servings", 350 kcal, protein 39
BREAKFAST = "2026-08-08-102"   # Chicken Grilled, "3 pieces" = 576 g, 888 kcal
SNACK = "2026-08-08-401"       # the longest name: High Protein 85% Lower Carb Mixed Seeds Loaf
AT = A.NOW.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")   # the fixed clock, as toISOString()
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
MEALS = ("breakfast", "lunch", "dinner", "snacks")


def imported_doc():
    """The fixture as the import tool writes it; the output goes to .tmp/ (git-ignored) and is removed."""
    if subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", ".tmp/test-entry.json"]).returncode == 0:
        (ROOT / ".tmp").mkdir(exist_ok=True)
        work = tempfile.mkdtemp(prefix="test-entry-", dir=ROOT / ".tmp")
    else:
        work = tempfile.mkdtemp(prefix="pantry-test-entry-")
    try:
        out = Path(work) / "pantry-data.json"
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "import_mynetdiary.py"), str(FIXTURE), "-o", str(out)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
        if done.returncode != 0:
            raise RuntimeError(f"import_mynetdiary.py exit {done.returncode}: {done.stdout}{done.stderr}")
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def serve_entry(site):
    registry = (ROOT / "app" / "registry.js").read_bytes()
    if LINE.encode() not in registry:
        site.overlay[A.BASE + "app/registry.js"] = registry.rstrip(b"\n") + b"\n" + LINE.encode() + b"\n"


def start(browser, url, errors, tag, doc, text=A.BIG_TEXT):
    ctx, page = A.phone(browser, errors, tag, text=text)
    A.open_today(page, url)
    page.evaluate("d => { Pantry.change(() => d, { dirty: false }); }", doc)
    return ctx, page


def open_entry(page, entry_id):
    page.evaluate("id => Pantry.go('entry', id)", entry_id)
    page.wait_for_selector('[data-screen="entry"] h1')


def save(page):
    page.locator('[data-screen="entry"]').get_by_role("button", name="Save").click()
    page.wait_for_selector('[data-screen="today"]')


def screen_text(page):
    return page.locator('[data-screen="entry"]').inner_text()


def kcal(page):
    return page.locator('[data-screen="entry"] [data-test="entry-kcal"]').inner_text().strip()


def raw(page):
    return page.evaluate("() => localStorage.getItem('pantry.v1')")


def find(doc, entry_id):
    return next((e for e in doc["entries"] if e["id"] == entry_id), None)


def index(doc, entry_id):
    return next((i for i, e in enumerate(doc["entries"]) if e["id"] == entry_id), None)


def meal_kcal(doc, date):
    """What Today's corners add up for a day: kcal per meal."""
    out = {m: 0 for m in MEALS}
    for e in doc["entries"]:
        if e["date"] == date:
            out[e["meal"]] += e["totals"]["kcal"]
    return out


def scaled(new, own, factor):
    return set(new) == set(own) and all(abs(new[k] - v * factor) < 1e-9 for k, v in own.items())


# ── scenarios ─────────────────────────────────────────────────────
def check_show(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-show", doc)
    open_entry(page, DINNER)
    text = screen_text(page)
    grams = page.get_by_label("Grams")
    under = page.locator('[data-screen="entry"] .entry-name + .entry-meta').inner_text()
    A.check("entry <id> shows the 2026-08-08 potato entry: food, meal, date, amount as the reference writes it (1,000) and its kcal",
            "Washed White Potato" in text and grams.input_value() == "1,000" and kcal(page) == "590", (text, grams.input_value(), kcal(page)))
    A.check("meal and date share the line under the name, as design 8 writes it ('Dinner, 8 Aug')", under == "Dinner, 8 Aug", under)
    A.check("the entry screen carries the food's drawing",
            page.locator('[data-screen="entry"] .entry-hero svg.drawing').count() == 1)
    chip = page.locator('[data-screen="entry"]').get_by_role("button", name="1,000 g", exact=True)
    A.check("his usual amount is a chip, pressed while it is the amount", chip.get_attribute("aria-pressed") == "true")
    A.fits(page, "entry screen, 360 px, 150 % text")

    open_entry(page, LUNCH)
    text = screen_text(page)
    servings = page.get_by_label("Amount in servings")
    A.check("an entry logged without grams is edited in servings (1 servings, 350 kcal)",
            servings.input_value() == "1" and kcal(page) == "350" and "servings" in text and "Lunch" in text,
            (servings.input_value(), kcal(page), text))
    open_entry(page, BREAKFAST)
    text = screen_text(page)
    A.check("an entry typed in pieces is edited in its grams and still says how it was logged",
            page.get_by_label("Grams").input_value() == "576" and kcal(page) == "888" and "Breakfast, 8 Aug, 3 pieces" in text,
            (page.get_by_label("Grams").input_value(), kcal(page), text))
    open_entry(page, SNACK)
    A.fits(page, "entry screen with the longest food name, 360 px, 150 % text")
    add_entry(page, {"id": "synthetic-last-year", "date": "2025-08-08", "meal": "dinner", "foodId": POTATO,
                     "amount": "100 g", "grams": 100, "totals": {"kcal": 59}})
    open_entry(page, "synthetic-last-year")
    under = page.locator('[data-screen="entry"] .entry-meta').inner_text()
    A.check("an entry from another year says its year ('Dinner, 8 Aug 2025')", under == "Dinner, 8 Aug 2025", under)

    # A sync pull or another tab changes the document while the screen is open.
    open_entry(page, DINNER)
    page.get_by_label("Grams").fill("700")
    page.evaluate(f"""() => Pantry.change(d => {{ d.entries.push({{ id: 'synthetic-other', date: '2026-10-02', meal: 'lunch',
        foodId: {json.dumps(POTATO)}, amount: '100 g', grams: 100, totals: {{ kcal: 59 }} }}); }})""")
    A.check("a change elsewhere in the log keeps what he is typing", page.get_by_label("Grams").input_value() == "700")
    page.evaluate(f"() => Pantry.change(d => {{ d.entries = d.entries.filter(e => e.id !== {json.dumps(DINNER)}); }})")
    page.wait_for_selector('[data-screen="entry"] .note')
    A.check("the entry deleted elsewhere while open turns into the plain not-in-your-log message",
            "not in your log" in screen_text(page) and page.locator('[data-screen="entry"] input').count() == 0, screen_text(page))

    page.evaluate("() => Pantry.home()")
    page.wait_for_selector('[data-screen="today"]')
    open_entry(page, "no-such-entry")
    text = screen_text(page)
    back = page.locator('[data-screen="entry"]').get_by_role("button", name="Back")
    A.check("an unknown id shows a plain message and a way back",
            "not in your log" in text and back.count() == 1 and page.locator('[data-screen="entry"] input').count() == 0, text)
    A.fits(page, "entry screen for an unknown id, 360 px, 150 % text")
    back.click()
    page.wait_for_selector('[data-screen="today"]')
    A.check("Back from an unknown id returns to the day it was opened from", page.locator('[data-screen="today"]').count() == 1)
    ctx.close()


def check_scale(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-scale", doc)
    page.evaluate(f"() => Pantry.change(d => {{ d.foods.find(f => f.id === {json.dumps(POTATO)}).per100.kcal = 999; }})")
    before = A.stored(page)
    own = find(before, DINNER)
    open_entry(page, DINNER)
    page.get_by_label("Grams").fill("500")
    A.check("the kcal beside the amount follows the typing (500 g: 295)", kcal(page) == "295", kcal(page))
    save(page)
    after = A.stored(page)
    e = find(after, DINNER) or {}
    A.check("Save returns with Pantry.go('today', entry.date)", page.evaluate("location.hash") == f"#/today/{DAY}",
            page.evaluate("location.hash"))
    A.check("1,000 g -> 500 g gives kcal 295 although the potato's per100.kcal is now 999",
            e.get("totals", {}).get("kcal") == 295, e.get("totals"))
    protein = e.get("totals", {}).get("protein", 0)
    A.check("protein is exactly half the entry's own (11.333...), not 11.35 from per100",
            abs(protein - own["totals"]["protein"] / 2) < 1e-9 and abs(protein - 11.35) > 1e-3, protein)
    A.check("every total is scaled by 500 / 1000; grams 500, amount '500 g'; id, date, meal and place stay",
            scaled(e.get("totals", {}), own["totals"], 0.5) and e.get("grams") == 500 and e.get("amount") == "500 g"
            and (e.get("id"), e.get("date"), e.get("meal")) == (DINNER, DAY, "dinner") and index(after, DINNER) == index(before, DINNER), e)
    A.check("the other entries are untouched",
            [x for x in after["entries"] if x["id"] != DINNER] == [x for x in before["entries"] if x["id"] != DINNER])

    own = find(after, LUNCH)
    open_entry(page, LUNCH)
    page.get_by_label("Amount in servings").fill("2")
    save(page)
    e = find(A.stored(page), LUNCH) or {}
    A.check("an entry with grams null changes by servings: 1 -> 2 doubles its own totals (700 kcal, protein 78)",
            e.get("grams", 0) is None and e.get("amount") == "2 servings" and e.get("totals", {}).get("kcal") == 700
            and e.get("totals", {}).get("protein") == 78 and scaled(e.get("totals", {}), own["totals"], 2), e)

    # A synthetic dinner of 350 g makes a second usual amount: its chip sets the amount, Save keeps the scaling.
    page.evaluate(f"""() => Pantry.change(d => {{ d.entries.push({{ id: 'synthetic-350', date: '2026-10-01', meal: 'dinner',
        foodId: {json.dumps(POTATO)}, amount: '350 g', grams: 350, totals: {{ kcal: 206.5 }} }}); }})""")
    own = find(A.stored(page), DINNER)
    open_entry(page, DINNER)
    entry = page.locator('[data-screen="entry"]')
    entry.get_by_role("button", name="350 g", exact=True).click()
    pressed = [entry.get_by_role("button", name=n, exact=True).get_attribute("aria-pressed") for n in ("350 g", "500 g")]
    A.check("tapping a usual-amount chip sets the amount and its kcal (350 g: 207)",
            page.get_by_label("Grams").input_value() == "350" and kcal(page) == "207" and pressed == ["true", "false"],
            (page.get_by_label("Grams").input_value(), kcal(page), pressed))
    save(page)
    e = find(A.stored(page), DINNER) or {}
    A.check("saving a chip's amount scales the entry again (500 g -> 350 g: kcal 206.5)",
            e.get("grams") == 350 and e.get("amount") == "350 g" and scaled(e.get("totals", {}), own["totals"], 0.7), e)
    ctx.close()


def check_move(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-move", doc)
    before = A.stored(page)
    own = find(before, DINNER)
    open_entry(page, DINNER)
    move = page.locator('[data-screen="entry"]').get_by_role("button", name="Move to lunch")
    move.click()
    on = move.get_attribute("aria-pressed")
    move.click()
    A.check("a move chip presses, and a second tap takes it back", on == "true" and move.get_attribute("aria-pressed") == "false")
    kept = raw(page)
    save(page)
    A.check("Save with nothing changed returns to the day and saves nothing",
            raw(page) == kept and page.evaluate("location.hash") == f"#/today/{DAY}")

    open_entry(page, DINNER)
    page.locator('[data-screen="entry"]').get_by_role("button", name="Move to lunch").click()
    save(page)
    after = A.stored(page)
    e = find(after, DINNER)
    A.check("moving dinner -> lunch keeps the id, date, amount, grams and totals, and its place in the log",
            e == {**own, "meal": "lunch"} and index(after, DINNER) == index(before, DINNER), e)
    A.check("the day's meal totals (Today's corners) follow: lunch 350 -> 940, dinner 590 -> 0",
            meal_kcal(before, DAY) == {"breakfast": 888, "lunch": 350, "dinner": 590, "snacks": 148}
            and meal_kcal(after, DAY) == {"breakfast": 888, "lunch": 940, "dinner": 0, "snacks": 148},
            (meal_kcal(before, DAY), meal_kcal(after, DAY)))
    A.check("moving writes no removed line and leaves the other entries", "removed" not in after
            and [x for x in after["entries"] if x["id"] != DINNER] == [x for x in before["entries"] if x["id"] != DINNER])
    ctx.close()


def check_delete(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-delete", doc)
    before = A.stored(page)
    open_entry(page, DINNER)
    page.locator('[data-screen="entry"]').get_by_role("button", name="Delete").click()
    page.wait_for_selector('[data-screen="today"]')
    after = A.stored(page)
    A.check("Delete returns with Pantry.go('today', entry.date)", page.evaluate("location.hash") == f"#/today/{DAY}",
            page.evaluate("location.hash"))
    removed = after.get("removed")
    A.check("Delete removes the entry and appends { id, at } (ISO time) to doc.removed",
            find(after, DINNER) is None and len(after["entries"]) == len(before["entries"]) - 1
            and removed == [{"id": DINNER, "at": AT}] and ISO.match(removed[0]["at"]) is not None, removed)
    toast = page.locator("#toast .toast")
    A.check("the toast says what was deleted and offers Undo on the day screen after the return",
            page.locator('[data-screen="today"]').count() == 1 and toast.count() == 1
            and "Washed White Potato" in toast.inner_text() and toast.get_by_role("button", name="Undo").count() == 1,
            toast.all_inner_texts())
    toast.get_by_role("button", name="Undo").click()
    back = A.stored(page)
    A.check("Undo puts the same entry back at the same index (deep equal) and removes that line",
            back["entries"] == before["entries"] and not any(r["id"] == DINNER for r in back.get("removed", [])),
            (index(back, DINNER), back.get("removed")))
    A.check("after Undo the document is what it was before the delete", back == before)

    open_entry(page, DINNER)
    page.locator('[data-screen="entry"]').get_by_role("button", name="Delete").click()
    page.wait_for_selector('[data-screen="today"]')
    page.wait_for_selector("#toast .toast", state="detached", timeout=8000)
    A.reload_to(page, "today")
    gone = A.stored(page)
    A.check("after the toast is gone, the deletion stands (and survives a reload)",
            find(gone, DINNER) is None and gone.get("removed") == [{"id": DINNER, "at": AT}], gone.get("removed"))
    ctx.close()


def check_invalid(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-invalid", doc)
    open_entry(page, DINNER)
    kept = raw(page)
    err = page.locator('[data-screen="entry"] .entry-err')
    for typed, words in (("", "Type the grams"), ("0", "more than 0 g"), ("abc", "is not a number"),
                         ("-5", "more than 0 g"), ("12abc", "is not a number")):
        page.get_by_label("Grams").fill(typed)
        page.locator('[data-screen="entry"]').get_by_role("button", name="Save").click()
        said = err.is_visible() and words in err.inner_text()
        A.check(f"an amount of {typed!r} is said in words ('{words}') and nothing is saved",
                said and raw(page) == kept and page.locator('[data-screen="entry"]').count() == 1,
                err.inner_text() if err.is_visible() else "no message")
    A.check("an invalid amount shows no kcal", kcal(page) == "–", kcal(page))
    A.fits(page, "entry screen with its error, 360 px, 150 % text")
    open_entry(page, LUNCH)
    page.get_by_label("Amount in servings").fill("")
    page.locator('[data-screen="entry"]').get_by_role("button", name="Save").click()
    A.check("an empty servings amount is said in words and nothing is saved",
            err.is_visible() and "Type the amount in servings" in err.inner_text() and raw(page) == kept,
            err.inner_text() if err.is_visible() else "no message")
    ctx.close()


def add_entry(page, entry):
    page.evaluate("e => Pantry.change(d => { d.entries.push(e); })", entry)


def check_amount_forms(browser, url, errors, doc):
    """Amounts written other ways than '<n> <unit>', as synthetic entries on the fixture day."""
    ctx, page = start(browser, url, errors, "entry-amounts", doc)
    entry = page.locator('[data-screen="entry"]')
    own = {"kcal": 300, "protein": 30}
    base = {"date": DAY, "meal": "lunch", "foodId": POTATO, "grams": None, "totals": own}

    for n, amount in enumerate(("a bowl", "1-2 pieces")):
        add_entry(page, {**base, "id": f"synthetic-fixed-{n}", "amount": amount})
        open_entry(page, f"synthetic-fixed-{n}")
        text = screen_text(page)
        A.check(f"an amount with no single number ({amount!r}) is shown as logged and the screen says only the meal can change",
                amount in text and "cannot be scaled" in text and "without an amount" not in text and "servings" not in text
                and entry.locator("input").count() == 0 and kcal(page) == "300", text)
    A.fits(page, "entry screen for an amount with no single number, 360 px, 150 % text")
    entry.get_by_role("button", name="Move to dinner").click()
    save(page)
    e = find(A.stored(page), "synthetic-fixed-1") or {}
    A.check("that entry still moves: meal dinner, amount and totals as logged",
            e == {**base, "id": "synthetic-fixed-1", "amount": "1-2 pieces", "meal": "dinner"}, e)

    for n, (amount, shown, unit, typed, saved, factor) in enumerate((
            ("1 1/2 cups", "1.5", "cups", "2", "2 cups", 2 / 1.5),
            ("1/2 cup", "0.5", "cup", "1", "1 cup", 2),
            ("1½ cups", "1.5", "cups", "3", "3 cups", 2),
            ("1,000 ml", "1,000", "ml", "250", "250 ml", 0.25),
            ("250 ml", "250", "ml", "300", "300 ml", 1.2))):
        add_entry(page, {**base, "id": f"synthetic-amount-{n}", "amount": amount})
        open_entry(page, f"synthetic-amount-{n}")
        field = page.get_by_label(f"Amount in {unit}", exact=True)
        got = field.input_value() if field.count() == 1 else None
        if got is not None:
            field.fill(typed)
            save(page)
        e = find(A.stored(page), f"synthetic-amount-{n}") or {}
        A.check(f"{amount!r} is edited as {shown} {unit}; {typed} saves {saved!r} with its own totals x {factor:g}",
                got == shown and e.get("amount") == saved and e.get("grams", 0) is None
                and scaled(e.get("totals", {}), own, factor), (got, e))

    # An amount the field rounds: 28.35 g shows as 28.4, and leaving it there changes nothing.
    add_entry(page, {**base, "id": "synthetic-decimal", "amount": "1 oz", "grams": 28.35, "totals": {"kcal": 100}})
    open_entry(page, "synthetic-decimal")
    got = page.get_by_label("Grams").input_value()
    entry.get_by_role("button", name="Move to dinner").click()
    save(page)
    e = find(A.stored(page), "synthetic-decimal") or {}
    A.check("28.35 g shows as 28.4; a move alone keeps grams 28.35, amount '1 oz' and the totals",
            got == "28.4" and e.get("meal") == "dinner" and e.get("grams") == 28.35 and e.get("amount") == "1 oz"
            and e.get("totals") == {"kcal": 100}, (got, e))
    ctx.close()


def check_elsewhere(browser, url, errors, doc):
    """Another tab or a sync pull changes the open entry itself."""
    ctx, page = start(browser, url, errors, "entry-elsewhere", doc)
    entry = page.locator('[data-screen="entry"]')
    move = f"m => Pantry.change(d => {{ d.entries.find(e => e.id === {json.dumps(DINNER)}).meal = m; }})"
    open_entry(page, DINNER)
    page.evaluate(move, "lunch")
    meta = entry.locator(".entry-meta").inner_text()
    A.check("a move made elsewhere before he touches anything shows on the open screen (Lunch, a Move to dinner chip)",
            meta == "Lunch, 8 Aug" and entry.get_by_role("button", name="Move to dinner").count() == 1, meta)
    page.get_by_label("Grams").fill("500")
    page.evaluate(move, "breakfast")
    A.check("once he has typed, a change elsewhere keeps his typing", page.get_by_label("Grams").input_value() == "500")
    save(page)
    e = find(A.stored(page), DINNER) or {}
    A.check("a grams-only Save keeps the meal changed elsewhere (breakfast) and scales the amount (500 g: kcal 295)",
            e.get("meal") == "breakfast" and e.get("grams") == 500 and e.get("totals", {}).get("kcal") == 295, e)
    ctx.close()


def check_layout(browser, url, errors, doc):
    ctx, page = start(browser, url, errors, "entry-240", doc, text=1.0)
    page.set_viewport_size({"width": 240, "height": 520})
    for entry_id, label in ((DINNER, "grams"), (LUNCH, "servings"), (SNACK, "longest name"), ("no-such-entry", "unknown id")):
        open_entry(page, entry_id)
        A.fits(page, f"entry screen at 240 px ({label})")
    open_entry(page, DINNER)
    page.get_by_label("Grams").fill("abc")
    page.locator('[data-screen="entry"]').get_by_role("button", name="Save").click()
    A.fits(page, "entry screen at 240 px with its error")
    ctx.close()

    ctx, page = start(browser, url, errors, "entry-themes", doc)
    open_entry(page, DINNER)
    for scheme, canvas, ink in (("dark", "rgb(14, 14, 14)", "rgb(238, 238, 238)"), ("light", "rgb(247, 247, 247)", "rgb(18, 18, 18)")):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"() => document.documentElement.dataset.theme === '{scheme}'")
        got = page.evaluate("""() => ({ canvas: getComputedStyle(document.body).backgroundColor,
            ink: getComputedStyle(document.querySelector('[data-screen="entry"] .entry-name')).color,
            height: document.querySelector('[data-screen="entry"] .entry-body').getBoundingClientRect().height })""")
        A.check(f"the entry screen renders in {scheme}: the theme's canvas and ink", got["canvas"] == canvas
                and got["ink"] == ink and got["height"] > 200, got)
        A.fits(page, f"entry screen in {scheme}, 360 px, 150 % text")
    ctx.close()


SCENARIOS = [("entry screen scenario", check_show), ("scaling scenario", check_scale), ("move scenario", check_move),
             ("delete scenario", check_delete), ("invalid amount scenario", check_invalid),
             ("amount forms scenario", check_amount_forms), ("changed elsewhere scenario", check_elsewhere),
             ("layout scenario", check_layout)]


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    doc = imported_doc()
    srv, site, url = A.start_site()
    serve_entry(site)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn in SCENARIOS:
                A.guarded(name, fn, browser, url, errors, copy.deepcopy(doc))
            browser.close()
        A.check("no console errors or page errors on the entry screens", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    print(f"\n{'ALL PASS' if not A.FAILS else str(len(A.FAILS)) + ' FAIL'}")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

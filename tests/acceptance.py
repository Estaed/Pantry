"""Pantry acceptance gate. Run from the repo root:  python tests/acceptance.py

Serves the repo under /Pantry/ (the GitHub Pages path) from a local server and drives Chromium as Tarik's
phone: 360 x 780, touch, text at 150 %, timezone Australia/Darwin, clock at 07:00 local. Then runs every
tests/test_*.py as `python <file>` from the repo root; a file's exit code is its verdict.
Prints PASS or FAIL per check and exits 1 on any FAIL.

Text at 150 % is the browser's default font size raised from 16 px to 24 px: what the text-scale meta tag in
index.html asks Chrome to do with the phone's font size, where Chrome supports it. Every app font size is in
rem, so all text scales; a check below fails when one does not. Chrome's own zoom slider is full-page zoom: at 150 % a 360 px phone has 240 CSS px, which
is checked too.

Hooks the gate relies on (keep them when a screen is redrawn): window.Pantry (the app/core.js API);
data-test="kcal-left" on Today; the buttons "Add food", "Scan a barcode" and "Back"; food rows whose
accessible name starts with the food name; the "Grams" field and the "Add to <meal>" button;
data-test="scan-status" and data-test="scan-code" on the scan screen.
"""
import datetime
import functools
import hashlib
import http.server
import json
import mimetypes
import os
import pathlib
import re
import socketserver
import struct
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASARIM = pathlib.Path("D:/TarikOS/.brain/skills/tasarim")
BASE = "/Pantry/"
DARWIN = datetime.timezone(datetime.timedelta(hours=9, minutes=30))
NOW = datetime.datetime(2026, 10, 20, 7, 0, tzinfo=DARWIN)       # 07:00 in Darwin is 21:30 the day before in UTC
PHONE = dict(viewport={"width": 360, "height": 780}, device_scale_factor=3, is_mobile=True, has_touch=True,
             timezone_id="Australia/Darwin", locale="en-AU")
BIG_TEXT = 1.5
FAILS = []

# The starter foods exactly as tasks/Task-00.md (Fixed) gives them: id, name, brand, per 100 g, usual grams.
STARTER = [
    ("v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao=", "Chicken Breast Raw", None,
     dict(kcal=108.1, protein=20.33, carbs=0, fat=3.0, sugars=0, satFat=0.54, salt=0.43, fibre=0), 350),
    ("v1.nWY1wUENSPOyu4Pt9ojJcGQKyXNwC+i8TqtlZmsYpNIdi2IepiE5wgTOo1g=", "Classic Tzatziki Dip", "Coles",
     dict(kcal=90.0, protein=4.75, carbs=12.0, fat=3.25, sugars=7.25, satFat=2.5, salt=0.8, fibre=2.5), 125),
    ("v1.d6DR1H5K+qWQUAWwc3j8qf3M2Hc3hKdn3YcTs5+OuZghSHwXFrx2D3cMe9c=", "Indian Basmati Rice", "Coles",
     dict(kcal=360.0, protein=8.4, carbs=80.0, fat=0.6, sugars=0, satFat=0.2, salt=0, fibre=2.0), 100),
    ("v1.aKW*42YP1j2TAk0bfGM*EM*zCxIsoQLSdlyVsH9Lzqk1scOD*H2WCHxRDw==", "Original Spreadable Butter", "Western Star",
     dict(kcal=616.6, protein=20.0, carbs=20.0, fat=60.0, sugars=20.0, satFat=28.0, salt=1.2), 5),
    ("v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg=", "Washed White Potato", "Woolworths",
     dict(kcal=59.0, protein=2.27, carbs=14.8, fat=0.13, sugars=0.67, satFat=0.13, salt=0.01, fibre=1.87), 500),
]
TARGETS = dict(kcal=2200, proteinPct=20, carbsPct=45, fatPct=35, salt=5.8)
CHICKEN = STARTER[0]
EAN = "9312726072232"            # the scanned tzatziki in design/screens.html
EAN_BAD = "9312726072233"        # the same digits with a wrong check digit


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"), flush=True)
    if not ok:
        FAILS.append(name)
    return ok


# ── a GitHub Pages stand-in: the repo under /Pantry/, with overlays and a switch that cuts the network ──
class Site:
    """Every response says Cache-Control: no-cache, so the browser's own caches never hide what the service
    worker does (it revalidates every file anyway)."""

    def __init__(self):
        self.overlay = {}        # path -> bytes served instead of the file (a feature added for one check)
        self.down = False        # True: every request is dropped unanswered, like a phone with no network
        self.paths = []          # every path asked for while up
        self.dropped = []


class Handler(http.server.SimpleHTTPRequestHandler):
    site = None

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        site = self.site
        path = urllib.parse.urlsplit(self.path).path
        if site.down:
            site.dropped.append(path)
            self.close_connection = True
            return
        site.paths.append(path)
        if path == "/Pantry":
            self.send_response(301)
            self.send_header("Location", BASE)
            self.end_headers()
            return
        if path in site.overlay:
            body = site.overlay[path]
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not path.startswith(BASE):
            self.send_error(404, "outside /Pantry/")
            return
        self.path = "/" + self.path[len(BASE):]
        super().do_GET()


class Server(socketserver.ThreadingTCPServer):
    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionError):     # the browser dropping a request it no longer needs
            super().handle_error(request, client_address)


def start_site():
    site = Site()
    handler = type("SiteHandler", (Handler,), {"site": site})
    srv = Server(("127.0.0.1", 0), functools.partial(handler, directory=str(ROOT)))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, site, f"http://127.0.0.1:{srv.server_address[1]}{BASE}"


# ── browser helpers ───────────────────────────────────────────────
def watch(page, errors, tag):
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
    page.on("console", lambda m: m.type == "error" and errors.append(f"[{tag}] console: {m.text}"))


def set_text(page, scale):
    """The browser's default font size, as the phone's text size sets it; applies from the next load."""
    cdp = getattr(page, "_pantry_cdp", None) or page.context.new_cdp_session(page)
    page._pantry_cdp = cdp
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": round(16 * scale), "fixed": round(13 * scale)}})


def phone(browser, errors, tag, text=BIG_TEXT, init=None):
    ctx = browser.new_context(**PHONE)
    ctx.clock.set_fixed_time(NOW)
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    watch(page, errors, tag)
    set_text(page, text)
    return ctx, page


def open_today(page, url):
    page.goto(url)
    page.wait_for_selector('[data-screen="today"] [data-test="kcal-left"]')


def reload_to(page, screen):
    page.reload()
    page.wait_for_selector(f'[data-screen="{screen}"]')


def kcal_left(page):
    return page.locator('[data-screen="today"] [data-test="kcal-left"]').inner_text().strip()


def stored(page):
    return page.evaluate("() => JSON.parse(localStorage.getItem('pantry.v1'))")


def wait_controlled(page):
    page.evaluate("() => navigator.serviceWorker.ready")
    page.wait_for_function("() => navigator.serviceWorker.controller !== null")


def go_offline(ctx, site):
    ctx.set_offline(True)
    site.down = True


def go_online(ctx, site):
    ctx.set_offline(False)
    site.down = False


FIT_JS = """() => {
  const w = document.documentElement.clientWidth;
  const bad = [...document.querySelectorAll('#app *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (r.right > w + 0.5 || r.left < -0.5);
  }).map(el => el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : '')
    + ' ' + Math.round(el.getBoundingClientRect().left) + '..' + Math.round(el.getBoundingClientRect().right));
  return { width: w, scroll: document.documentElement.scrollWidth - w, bad: bad.slice(0, 6) };
}"""


def fits(page, name):
    r = page.evaluate(FIT_JS)
    check(f"{name}: no horizontal scroll, nothing past the edge ({r['width']} px)", r["scroll"] <= 0 and not r["bad"], r)


TEXT_SIZES_JS = """() => [...document.querySelectorAll('#app *')].filter(el =>
    [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && el.getClientRects().length)
  .map(el => [el.tagName.toLowerCase() + ':' + el.textContent.trim().slice(0, 24), parseFloat(getComputedStyle(el).fontSize)])"""

ROW_NAMES_JS = """() => [...document.querySelectorAll('#app .fr .name, #app .fr .sub')].map(el => {
  const s = getComputedStyle(el);
  return { text: el.textContent, nowrap: s.whiteSpace === 'nowrap', ellipsis: s.textOverflow === 'ellipsis',
           lines: Math.round(el.getBoundingClientRect().height / parseFloat(s.lineHeight)) };
})"""


def rows_single_line(page, name):
    rows = page.evaluate(ROW_NAMES_JS)
    bad = [r for r in rows if not (r["nowrap"] and r["ellipsis"] and r["lines"] <= 1)]
    check(f"{name}: each row's name and subtitle stay on one line and end with an ellipsis", rows and not bad, bad or rows)


# ── checks ────────────────────────────────────────────────────────
def check_files():
    app = ROOT / "app"
    leaks = [str(p.relative_to(ROOT)) for p in sorted(app.rglob("*")) if p.is_file() and p.name != "core.js"
             and "localStorage" in p.read_text(encoding="utf-8", errors="replace")]
    check("only app/core.js touches localStorage", not leaks, leaks)
    core = (app / "core.js").read_text(encoding="utf-8")
    check("app/core.js opens with a header comment", core.startswith("/*") and "*/" in core, core[:60])

    registry = (app / "registry.js").read_text(encoding="utf-8")
    listed = re.findall(r"^PANTRY_FEATURES\.push\('([^']+)'\);$", registry, re.M)
    missing = [f for f in listed if not (ROOT / f).is_file()]
    check("app/registry.js lists one existing feature script per line", listed and not missing, (listed, missing))
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    check("sw.js names a release cache and lists no feature by hand",
          re.search(r"const CACHE = 'pantry-v\d+'", sw) is not None and not any(f in sw for f in listed), listed)

    if TASARIM.is_dir():
        pairs = [(ROOT / "tokens.css", TASARIM / "references" / "tokens.css")] + [
            (ROOT / "fonts" / n, TASARIM / "assets" / "fonts" / n)
            for n in ("archivo.css", "Archivo-latin.woff2", "Archivo-latin-ext.woff2", "Manrope.woff2")]
        differ = [str(a.relative_to(ROOT)) for a, b in pairs
                  if not a.is_file() or hashlib.sha256(a.read_bytes()).digest() != hashlib.sha256(b.read_bytes()).digest()]
        check("tokens.css and the fonts are unchanged copies of the tasarim files", not differ, differ)
    else:
        print(f"SKIP tokens.css and fonts against the tasarim source: {TASARIM} is not on this machine")

    for target in (".tmp/x.json", "references/mynetdiary-history-2026-10-20.json", "references/clip.mp4"):
        r = subprocess.run(["git", "check-ignore", "-q", target], cwd=ROOT)
        check(f"git ignores {target}", r.returncode == 0, f"git check-ignore exit {r.returncode}")


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def check_manifest(url):
    murl = urllib.parse.urljoin(url, "manifest.json")
    m = json.loads(urllib.request.urlopen(murl).read())

    def get(u):
        try:
            with urllib.request.urlopen(u) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""

    for key in ("start_url", "scope"):
        u = urllib.parse.urljoin(murl, m.get(key, ""))
        status, _ = get(u)
        check(f"manifest {key} resolves under {BASE} with 200", urllib.parse.urlsplit(u).path.startswith(BASE) and status == 200, (u, status))
    check("manifest is installable as an app (standalone, name)", m.get("display") == "standalone" and m.get("name") == "Pantry", m)
    for size in (192, 512):
        icons = [i for i in m.get("icons", []) if i.get("sizes") == f"{size}x{size}"]
        purposes = {p for i in icons for p in i.get("purpose", "any").split()}
        ok = bool(icons)
        for icon in icons:
            u = urllib.parse.urljoin(murl, icon["src"])
            status, data = get(u)
            ok = ok and urllib.parse.urlsplit(u).path.startswith(BASE) and status == 200 and png_size(data) == (size, size)
        check(f"manifest {size} px icon resolves under {BASE} with 200 and is {size}x{size} (any and maskable)",
              ok and {"any", "maskable"} <= purposes, icons)


def check_phone(browser, url, site, errors):
    ctx, page = phone(browser, errors, "phone", text=1.0)
    open_today(page, url)

    # first launch: the seeded document
    doc = stored(page)
    foods = doc and doc.get("foods") or []
    want = []
    for fid, name, brand, per100, _ in STARTER:
        f = {"id": fid, "name": name, "per100": per100, "servings": [], "source": "mynetdiary"}
        if brand:
            f["brand"] = brand
        want.append(f)
    check("first launch seeds the five starter foods as tasks/Task-00.md gives them", foods == want,
          [f.get("name") for f in foods])
    check("the document is { version 1, foods, entries [], settings.targets }",
          doc and doc.get("version") == 1 and doc.get("entries") == [] and doc.get("settings") == {"targets": TARGETS}
          and list(doc) == ["version", "foods", "entries", "settings"], {k: doc.get(k) for k in ("version", "settings")} if doc else doc)
    usual = {s[0]: s[4] for s in STARTER}
    got_usual = page.evaluate("() => Object.fromEntries(Pantry.starter.map(s => [s.food.id, s.usual]))")
    check("starter foods carry their usual grams outside the document", got_usual == usual, got_usual)
    eyebrow = page.locator('[data-screen="today"] .top .eyebrow').inner_text().strip()
    check("Today shows today's date in Darwin", eyebrow == "Tuesday, 20 October", eyebrow)
    check("Today starts at 2,200 kcal left", kcal_left(page) == "2,200", kcal_left(page))

    # text at 150 %
    title = '[data-screen="today"] h1'
    h100 = page.locator(title).bounding_box()["height"]
    sizes100 = page.evaluate(TEXT_SIZES_JS)
    set_text(page, BIG_TEXT)
    reload_to(page, "today")
    h150 = page.locator(title).bounding_box()["height"]
    sizes150 = page.evaluate(TEXT_SIZES_JS)
    check("text at 150 % works: the title is at least 1.4x as tall as at 100 %", h150 >= 1.4 * h100, (h100, h150))
    flat = [a[0] for a, b in zip(sizes100, sizes150) if b[1] < 1.45 * a[1]]
    check("every text on Today grows with the text size (no px font sizes)",
          len(sizes100) == len(sizes150) and sizes100 and not flat, flat or (len(sizes100), len(sizes150)))
    fits(page, "Today, empty, 150 % text")

    # log 350 g of chicken the way Tarik does it
    page.get_by_role("button", name="Add food").click()
    page.wait_for_selector('[data-screen="add"] .fr')
    names = [n.strip() for n in page.locator('[data-screen="add"] .fr .name').all_inner_texts()]
    check("the food list shows the starter foods by their short name", names == [s[1] for s in STARTER], names)
    subs = [n.strip() for n in page.locator('[data-screen="add"] .fr .sub').all_inner_texts()]
    check("each food shows its brand on the second line with its usual grams",
          subs == [(f"{b}, " if b else "") + f"{g} g" for _, _, b, _, g in STARTER], subs)
    fits(page, "food list, 150 % text")
    rows_single_line(page, "food list")

    page.get_by_role("button", name=re.compile("^Chicken Breast Raw")).click()
    grams = page.get_by_label("Grams")
    grams.wait_for()
    check("the gram step offers the usual 350 g and its kcal",
          grams.input_value() == "350" and page.locator('[data-test="portion-kcal"]').inner_text().strip() == "378",
          (grams.input_value(), page.locator('[data-test="portion-kcal"]').inner_text()))
    check("at 07:00 the meal is breakfast", page.get_by_role("radio", name="Breakfast").is_checked())
    grams.fill("")
    page.get_by_role("button", name="Add to breakfast").click()
    err = page.locator('[data-screen="add"] .err')
    check("an empty amount is refused with a plain message and nothing is saved",
          err.is_visible() and "Type the grams" in err.inner_text() and stored(page)["entries"] == [], err.inner_text())
    fits(page, "gram step with its error, 150 % text")
    grams.fill("350")
    page.get_by_role("button", name="Add to breakfast").click()
    page.wait_for_selector('[data-screen="today"] [data-test="kcal-left"]')

    kcal350 = round(CHICKEN[3]["kcal"] * 350 / 100)                    # 378
    expect = f"{2200 - kcal350:,}"                                       # 1,822
    check(f"kcal left drops by the chicken's kcal for 350 g ({kcal350}): {expect}", kcal_left(page) == expect, kcal_left(page))
    entries = stored(page)["entries"]
    e = entries[0] if len(entries) == 1 else {}
    utc_day = NOW.astimezone(datetime.timezone.utc).date().isoformat()
    check(f"the entry is stored under the Darwin date 2026-10-20, not the UTC date {utc_day}",
          utc_day != "2026-10-20" and e.get("date") == "2026-10-20", e.get("date"))
    want_totals = {k: v * 350 / 100 for k, v in CHICKEN[3].items()}
    totals = e.get("totals", {})
    close = set(totals) == set(want_totals) and all(abs(totals[k] - v) <= (0.051 if k == "kcal" else 0.0051) for k, v in want_totals.items())
    check("the entry keeps meal, food, amount, grams and every nutrient total of 350 g",
          e.get("meal") == "breakfast" and e.get("foodId") == CHICKEN[0] and e.get("amount") == "350 g"
          and e.get("grams") == 350 and close, e)
    butter = page.evaluate(f"() => Pantry.totals(Pantry.doc().foods.find(f => f.id === {json.dumps(STARTER[3][0])}), 5)")
    check("an unknown nutrient stays absent from totals, never 0 (butter has no fibre)",
          "fibre" not in butter and abs(butter.get("kcal", 0) - 30.83) <= 0.051, butter)
    check("a change marks the document dirty for sync, outside the document",
          page.evaluate("() => Pantry.dirty()") and "dirty" not in stored(page)
          and page.evaluate("() => JSON.parse(localStorage.getItem('pantry.sync')).dirty") is True)
    row = page.locator('[data-screen="today"] .fr').first
    check("Today lists the entry", page.locator('[data-screen="today"] .fr').count() == 1
          and "Chicken Breast Raw" in row.inner_text() and "Breakfast, 350 g" in row.inner_text(), row.inner_text())
    fits(page, "Today with an entry, 150 % text")
    rows_single_line(page, "Today")

    reload_to(page, "today")
    check("the entry survives a reload", kcal_left(page) == expect and page.locator('[data-screen="today"] .fr').count() == 1,
          kcal_left(page))

    page.evaluate(f"() => Pantry.change(d => {{ d.foods.find(f => f.id === {json.dumps(CHICKEN[0])}).per100.kcal = 999; }})")
    live = kcal_left(page)
    reload_to(page, "today")
    check("changing the food's per100.kcal leaves kcal left as logged", live == expect and kcal_left(page) == expect, (live, kcal_left(page)))

    page.evaluate("""() => Pantry.change(d => { d.entries.push({ id: 'gate-live', date: Pantry.today(), meal: 'snacks',
        foodId: d.foods[0].id, amount: '1 g', grams: 1, totals: { kcal: 100 } }); })""")
    live = kcal_left(page)
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'gate-live'); })")
    check("Today follows a change without a reload", live == f"{2200 - kcal350 - 100:,}" and kcal_left(page) == expect, (live, kcal_left(page)))
    frozen = page.evaluate("() => { try { Pantry.doc().entries.push({}); return false; } catch (e) { return true; } }")
    guarded = page.evaluate("""() => { const before = localStorage.getItem('pantry.v1');
        try { Pantry.change(d => { d.entries.push({ id: 'x', date: 'today' }); }); return 'saved'; }
        catch (e) { return localStorage.getItem('pantry.v1') === before ? 'refused' : 'changed'; } }""")
    check("the document can only change through Pantry.change, which refuses a wrong shape", frozen and guarded == "refused", (frozen, guarded))

    keys = page.evaluate("() => Object.keys(Pantry)")
    header = (ROOT / "app" / "core.js").read_text(encoding="utf-8").split("*/", 1)[0]
    undocumented = [k for k in keys if f"Pantry.{k}" not in header]
    check("the core.js header documents every Pantry API member", keys and not undocumented, undocumented)

    # offline after one online load
    wait_controlled(page)
    go_offline(ctx, site)
    reload_to(page, "today")
    fonts = page.evaluate("""async () => { await document.fonts.ready;
        const loaded = fam => [...document.fonts].some(f => f.family.replace(/['"]/g, '') === fam && f.status === 'loaded');
        return { manrope: document.fonts.check('16px Manrope'), archivo: document.fonts.check('700 40px Archivo'),
                 faces: loaded('Manrope') && loaded('Archivo') }; }""")
    check("offline, a reload shows Today with the saved entry", kcal_left(page) == expect
          and page.locator('[data-screen="today"] .fr').count() == 1, kcal_left(page))
    check("offline, Manrope and Archivo are loaded (document.fonts.check)", fonts["manrope"] and fonts["archivo"] and fonts["faces"], fonts)
    page.get_by_role("button", name="Add food").click()
    page.wait_for_selector('[data-screen="add"] .fr')
    page.get_by_role("button", name="Back").click()
    page.get_by_role("button", name="Scan a barcode").click()
    page.wait_for_selector('[data-screen="scan"] [data-test="scan-status"]')
    check("offline, the food list and the scan screen open", page.locator('[data-screen="scan"]').count() == 1)
    page.get_by_role("button", name="Back").click()
    go_online(ctx, site)

    # index.html comes from the network first, so a release reaches the phone on the next launch
    index = (ROOT / "index.html").read_bytes()
    site.overlay[BASE + "index.html"] = index.replace(b"</head>", b'<meta name="pantry-gate" content="new">\n</head>')
    page.goto(url + "index.html")
    page.wait_for_selector('[data-screen="today"]')
    check("online, a new index.html is used at once (network first)", page.locator('meta[name="pantry-gate"]').count() == 1)
    site.overlay.clear()

    # a feature added to an installed app: online it appears, then it works offline
    add_probe(site)
    page.goto(url + "#/probe")
    reload_to(page, "probe")                       # a new hash alone does not reload; a launch does
    probe_online = page.locator('[data-test="probe"]').count() == 1
    page.wait_for_function("() => caches.match('app/zz-probe.js').then(Boolean)")
    go_offline(ctx, site)
    reload_to(page, "probe")
    check("a feature appended to app/registry.js on an installed app shows online and offline",
          probe_online and page.locator('[data-test="probe"]').count() == 1)
    go_online(ctx, site)
    site.overlay.clear()

    # Chrome's zoom slider at 150 % leaves 240 CSS px on a 360 px phone
    set_text(page, 1.0)
    page.set_viewport_size({"width": 240, "height": 520})
    open_today(page, url)
    fits(page, "Today at 240 px (150 % page zoom)")
    page.get_by_role("button", name="Add food").click()
    page.wait_for_selector('[data-screen="add"] .fr')
    fits(page, "food list at 240 px")
    page.locator('[data-screen="add"] .fr').first.click()
    page.get_by_label("Grams").wait_for()
    fits(page, "gram step at 240 px")
    page.goto(url + "#/scan")
    page.wait_for_selector('[data-screen="scan"] [data-test="scan-status"]')
    fits(page, "scan screen at 240 px")
    ctx.close()


def add_probe(site):
    registry = (ROOT / "app" / "registry.js").read_bytes()
    site.overlay[BASE + "app/registry.js"] = registry + b"PANTRY_FEATURES.push('app/zz-probe.js');\n"
    site.overlay[BASE + "app/zz-probe.js"] = (ROOT / "tests" / "fixtures" / "app" / "probe.js").read_bytes()


def check_probe_fresh(browser, url, site, errors):
    """First install with a new feature listed: it must be stored at install, since the first load is not yet
    served by the worker."""
    add_probe(site)
    ctx, page = phone(browser, errors, "probe")
    page.goto(url + "#/probe")
    page.wait_for_selector('[data-screen]')
    online = page.locator('[data-test="probe"]').count() == 1
    wait_controlled(page)
    stored_at_install = page.evaluate("() => caches.match('app/zz-probe.js').then(Boolean)")
    go_offline(ctx, site)
    reload_to(page, "probe")
    offline = page.locator('[data-test="probe"]').count() == 1
    check("a feature listed in app/registry.js shows online and offline after a first install, "
          "with no edit to index.html, app/core.js or sw.js",
          online and offline and stored_at_install, dict(online=online, offline=offline, stored_at_install=stored_at_install))
    go_online(ctx, site)
    site.overlay.clear()
    ctx.close()


def check_unreadable(browser, url):
    """A stored log the app cannot read is never written over, and Today says why nothing saves."""
    quiet = []                    # this scenario logs an error on purpose; it is not part of the error check
    ctx, page = phone(browser, quiet, "unreadable")
    broken = '{"version": 1, "foods": "not a list", "entries": []'
    page.add_init_script(f"if (!sessionStorage.getItem('gate')) {{ sessionStorage.setItem('gate', '1'); localStorage.setItem('pantry.v1', {json.dumps(broken)}); }}")
    open_today(page, url)
    banner = page.locator('[data-screen="today"] .banner')
    said = banner.count() == 1 and "could not be read" in banner.inner_text()
    page.get_by_role("button", name="Add food").click()
    page.get_by_role("button", name=re.compile("^Chicken Breast Raw")).click()
    page.get_by_role("button", name="Add to breakfast").click()
    err = page.locator('[data-screen="add"] .err')
    refused = err.is_visible() and "not saving" in err.inner_text()
    kept = page.evaluate("() => localStorage.getItem('pantry.v1')") == broken
    check("an unreadable stored log is never written over; Today and the gram step say why",
          said and refused and kept, dict(banner=said, refused=refused, kept=kept))
    ctx.close()


FAKES_JS = """(() => {
  const cfg = window.__cfg = %s;
  const fake = window.__fake = { tracks: [], gum: 0, detect: 0, formats: null, source: null };
  delete window.BarcodeDetector;
  if (cfg.formats) {
    window.BarcodeDetector = class {
      static async getSupportedFormats() { return cfg.formats; }
      constructor(opts) { fake.formats = opts && opts.formats; }
      async detect(src) {
        fake.detect++; fake.source = src && src.tagName;
        const step = cfg.reads[Math.min(fake.detect - 1, cfg.reads.length - 1)] || [];
        return step.map(rawValue => ({ rawValue, format: rawValue.length === 13 ? 'ean_13' : 'qr_code' }));
      }
    };
  }
  navigator.mediaDevices.getUserMedia = async constraints => {
    fake.gum++; fake.constraints = constraints;
    if (cfg.delay) await new Promise(r => setTimeout(r, cfg.delay));
    const c = document.createElement('canvas'); c.width = 640; c.height = 480;
    const g = c.getContext('2d');
    const draw = () => { g.fillStyle = '#333'; g.fillRect(0, 0, 640, 480); g.fillStyle = '#eee'; g.fillRect(performance.now() / 4 %% 600, 200, 40, 80); };
    draw(); setInterval(draw, 40);
    const stream = c.captureStream(25);
    fake.tracks.push(...stream.getTracks());
    return stream;
  };
})();"""

TRACKS_JS = "() => window.__fake.tracks.map(t => t.readyState)"


def scan_page(browser, url, errors, tag, cfg):
    ctx, page = phone(browser, errors, tag, init=FAKES_JS % json.dumps(cfg))
    open_today(page, url)
    page.get_by_role("button", name="Scan a barcode").click()
    page.wait_for_selector('[data-screen="scan"] [data-test="scan-status"]')
    return ctx, page


def status(page):
    return page.locator('[data-test="scan-status"]').inner_text().strip()


def check_scan(browser, url, errors):
    ctx, page = scan_page(browser, url, errors, "scan-missing", {"formats": None, "reads": []})
    page.wait_for_function("() => /BarcodeDetector/.test(document.querySelector('[data-test=\"scan-status\"]').textContent)")
    check("scan without BarcodeDetector says so in plain words and opens no camera",
          "no built-in barcode reader" in status(page) and "BarcodeDetector is missing" in status(page)
          and page.evaluate("() => window.__fake.gum") == 0, status(page))
    fits(page, "scan screen, no reader, 150 % text")
    ctx.close()

    ctx, page = scan_page(browser, url, errors, "scan-noean", {"formats": ["qr_code", "code_128"], "reads": []})
    page.wait_for_function("() => /EAN-13/.test(document.querySelector('[data-test=\"scan-status\"]').textContent)")
    check("scan with a reader that lacks ean_13 says so in plain words and opens no camera",
          "cannot read EAN-13" in status(page) and "qr_code" in status(page) and page.evaluate("() => window.__fake.gum") == 0, status(page))
    ctx.close()

    reads = [[], [], [], [EAN_BAD], ["QR-NOT-A-PACK"], [EAN]]
    ctx, page = scan_page(browser, url, errors, "scan", {"formats": ["ean_13", "qr_code"], "reads": reads})
    code = page.locator('[data-test="scan-code"]')
    code.wait_for(state="visible")
    digits = re.sub(r"\D", "", code.inner_text())
    fake = page.evaluate("() => ({ gum: window.__fake.gum, formats: window.__fake.formats, source: window.__fake.source, facing: window.__fake.constraints.video.facingMode, detect: window.__fake.detect })")
    check("scan opens the rear camera, asks the reader for ean_13 and shows the EAN-13 it read",
          digits == EAN and fake["formats"] == ["ean_13"] and fake["source"] == "VIDEO"
          and fake["facing"] == {"ideal": "environment"} and fake["detect"] >= len(reads), (digits, fake))
    check("a read with a wrong check digit is never shown", EAN_BAD not in page.locator('[data-screen="scan"]').inner_text().replace(" ", ""))
    check("the read says how long it took", re.search(r"Read in \d+\.\d s", page.locator('[data-screen="scan"]').inner_text()) is not None)
    check("the camera is live while scanning", page.evaluate(TRACKS_JS) == ["live"], page.evaluate(TRACKS_JS))
    fits(page, "scan screen with a read, 150 % text")

    page.get_by_role("button", name="Back").click()
    page.wait_for_selector('[data-screen="today"]')
    check("leaving the scan screen with Back stops every camera track", page.evaluate(TRACKS_JS) == ["ended"], page.evaluate(TRACKS_JS))

    page.get_by_role("button", name="Scan a barcode").click()
    page.wait_for_function("() => window.__fake.tracks.length === 2 && window.__fake.tracks[1].readyState === 'live'")
    page.go_back()
    page.wait_for_selector('[data-screen="today"]')
    check("leaving with the phone's back gesture stops every camera track", page.evaluate(TRACKS_JS) == ["ended"] * 2, page.evaluate(TRACKS_JS))

    page.get_by_role("button", name="Scan a barcode").click()
    page.wait_for_function("() => window.__fake.tracks.length === 3 && window.__fake.tracks[2].readyState === 'live'")
    page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }")
    hidden = page.evaluate(TRACKS_JS)
    page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }")
    page.wait_for_function("() => window.__fake.tracks.length === 4 && window.__fake.tracks[3].readyState === 'live'")
    check("the app going to the background stops the camera; coming back starts it again",
          hidden == ["ended"] * 3 and page.evaluate(TRACKS_JS)[3] == "live", hidden)

    page.get_by_role("button", name="Back").click()
    page.evaluate("() => { window.__cfg.delay = 600; }")
    page.get_by_role("button", name="Scan a barcode").click()
    page.get_by_role("button", name="Back").click()
    page.wait_for_function("() => window.__fake.tracks.length === 5", timeout=5000)
    page.wait_for_timeout(200)
    check("leaving while the camera is still starting stops it when it arrives", page.evaluate(TRACKS_JS) == ["ended"] * 5, page.evaluate(TRACKS_JS))
    ctx.close()


def run_file(path):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900, env=env)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return "timeout", ""


def check_suite():
    code, _ = run_file(ROOT / "tests" / "fixtures" / "app" / "exits_1.py")
    check("the runner turns a test file that exits 1 red (tests/fixtures/app/exits_1.py, not in the suite)", code == 1, code)
    files = sorted((ROOT / "tests").glob("test_*.py"))
    if not files:
        print("SKIP tests/test_*.py: none in tests/ yet")
    for f in files:
        code, out = run_file(f)
        if not check(f"tests/{f.name} exits 0", code == 0, f"exit {code}"):
            print("\n".join("    " + line for line in out.strip().splitlines()[-25:]))


def guarded(name, fn, *args):
    """A scenario that crashes is one FAIL with its error, and the other scenarios still run."""
    try:
        fn(*args)
    except Exception as e:      # noqa: BLE001 - the gate reports every crash as a failure
        check(f"{name} ran to the end", False, f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")


def main():
    srv, site, url = start_site()
    errors = []
    try:
        guarded("file checks", check_files)
        guarded("manifest checks", check_manifest, url)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            guarded("phone scenario", check_phone, browser, url, site, errors)
            site.overlay.clear()
            site.down = False
            guarded("first-install feature scenario", check_probe_fresh, browser, url, site, errors)
            site.overlay.clear()
            site.down = False
            guarded("scan scenario", check_scan, browser, url, errors)
            guarded("unreadable log scenario", check_unreadable, browser, url)
            browser.close()
        outside = sorted({p for p in site.paths if not p.startswith(BASE) and p != "/Pantry"})
        check(f"every request stays under {BASE} (relative paths only)", not outside, outside)
        check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    guarded("tests/test_*.py suite", check_suite)
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()

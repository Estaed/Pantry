"""Checks for Task-13: the theme picked in Settings (Dynamic, Light, Dark or System) and applied by app/core.js.

Run from the repo root: python tests/test_theme.py   (exit 0 = no FAIL; prints PASS or FAIL per check)

Reuses the gate's server, phone and checks from tests/acceptance.py. Every clock is injected (Playwright's clock):
no check waits on real time. Darwin's sunrise and sunset are checked against a published table:
  sunrisesunsettime.org, "Darwin First Light, Sunrise & Sunset Times", calendar for 2026,
  https://www.sunrisesunsettime.org/australia-pacific/australia/darwin.htm (read 2026-10-21; Darwin at -12.461130,
  130.841850, Australia/Darwin, times to the minute as printed). time.now/darwin/sun printed the same October days
  within a minute (20 Oct 2026: 06:19 and 18:44).
Chromium's own forced dark mode (--blink-settings=forceDarkModeEnabled=true) stands in for Samsung Internet's dark
mode, which the phone runs. The GitHub Contents API is mocked in Python for the synced theme. Documents are built in
code (no fixture). Screenshots go to .tmp/test_theme/.
"""
import base64
import datetime
import hashlib
import json
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
WORK = ROOT / ".tmp" / "test_theme"
DAY = "2026-10-20"
# Darwin local times as the table prints them: date -> (sunrise, sunset). Four seasons, today and New Year's Day.
TABLE = {
    "2026-01-01": ("06:25", "19:16"),
    "2026-03-21": ("06:51", "18:58"),
    "2026-06-21": ("07:07", "18:31"),
    "2026-09-22": ("06:37", "18:43"),
    "2026-10-20": ("06:20", "18:45"),
    "2026-12-21": ("06:19", "19:11"),
}
TOKEN = "github_pat_11TESTONLY0000_themeTestTokenNotARealOne00000000000000000000000000000000"
NAMES = ["Dynamic", "Light", "Dark", "System"]


def at(date, hhmm, minutes=0):
    y, m, d = map(int, date.split("-"))
    h, mi = map(int, hhmm.split(":"))
    return datetime.datetime(y, m, d, h, mi, tzinfo=A.DARWIN) + datetime.timedelta(minutes=minutes)


def canvases():
    """The two canvas colours as tokens.css gives them: the colour each theme's browser bar must carry."""
    css = (ROOT / "tokens.css").read_text(encoding="utf-8")
    dark = re.search(r':root, \[data-theme="dark"\] \{[^}]*?--canvas: (#[0-9A-Fa-f]{6})', css).group(1).upper()
    light = re.search(r'\[data-theme="light"\] \{[^}]*?--canvas: (#[0-9A-Fa-f]{6})', css).group(1).upper()
    return {"dark": dark, "light": light}


def doc_with(theme=None, entries=False):
    """A document built in code: the starter-less shape core.js seeds, or an older one with a food and an entry."""
    settings = {"targets": dict(A.TARGETS)}
    if theme is not None:
        settings["theme"] = theme
    doc = {"version": 1, "foods": [], "entries": [], "settings": settings}
    if entries:
        fid, name, _, per100, _ = A.STARTER[0]
        doc["foods"] = [{"id": fid, "name": name, "per100": per100, "servings": [], "source": "mynetdiary"}]
        doc["entries"] = [{"id": "theme-old-1", "date": DAY, "meal": "lunch", "foodId": fid, "amount": "350 g", "grams": 350,
                           "totals": {k: v * 3.5 for k, v in per100.items()}}]
    return doc


def phone(browser, errors, tag, scheme="dark", clock=None, doc=None, text=1.0, tz="Australia/Darwin"):
    """The gate's phone at Tarik's text size, with an injected clock (installed at `clock`, else fixed at the gate's
    07:00) and, when given, a stored document put in place before the first load."""
    ctx = browser.new_context(**{**A.PHONE, "timezone_id": tz}, color_scheme=scheme, service_workers="block")
    if clock is not None:
        ctx.clock.install(time=clock)
    else:
        ctx.clock.set_fixed_time(A.NOW)
    if doc is not None:
        ctx.add_init_script(f"if (!localStorage.getItem('pantry.v1')) localStorage.setItem('pantry.v1', {json.dumps(json.dumps(doc))});")
    page = ctx.new_page()
    A.watch(page, errors, tag)
    A.set_text(page, text)
    return ctx, page


def open_settings(page, url):
    page.goto(url + "#/settings")
    page.wait_for_selector('[data-screen="settings"] [data-part="theme"] input')


def shown(page):
    return page.evaluate("() => document.documentElement.dataset.theme")


def picked(page):
    return page.evaluate("() => [...document.querySelectorAll('[data-part=\"theme\"] input')].filter(r => r.checked).map(r => r.value)")


def stored_theme(page):
    return page.evaluate("() => { const s = JSON.parse(localStorage.getItem('pantry.v1')).settings; return 'theme' in s ? s.theme : '(absent)'; }")


def help_line(page):
    return page.locator('[data-test="theme-help"]').inner_text().strip()


# the theme-color metas the browser can use now: no media, or a media that matches
BARS_JS = """() => [...document.querySelectorAll('meta[name="theme-color"]')]
  .filter(m => !m.media || matchMedia(m.media).matches).map(m => m.content.toUpperCase())"""


def bars(page):
    return page.evaluate(BARS_JS)


def follow(page, theme, timeout=3000):
    """Give a media change (an event, delivered after emulate_media returns) the moment it needs; the check decides."""
    try:
        page.wait_for_function("t => document.documentElement.dataset.theme === t", arg=theme, timeout=timeout)
    except Exception:       # noqa: BLE001 - a theme that never follows is reported by the check that reads it
        pass


def visibility(page, state):
    page.evaluate("""s => { Object.defineProperty(document, 'visibilityState', { value: s, configurable: true });
        document.dispatchEvent(new Event('visibilitychange')); }""", state)


# ── Settings: the four choices, at once, stored, kept ─────────────
def check_choice(browser, url, errors):
    ctx, page = phone(browser, errors, "choice")
    A.open_today(page, url)
    open_settings(page, url)
    radios = page.locator('[data-part="theme"] input[type="radio"]')
    names = [page.locator('[data-part="theme"] label').nth(i).inner_text().strip() for i in range(radios.count())]
    A.check("Settings shows the four theme choices in order: Dynamic, Light, Dark, System", names == NAMES, names)
    A.check("a new document is on System, marked in Settings, and opening Settings writes no settings.theme",
            picked(page) == ["system"] and stored_theme(page) == "(absent)" and shown(page) == "dark",
            (picked(page), stored_theme(page), shown(page)))
    page.evaluate("() => { window.__sameLoad = true; }")
    for name, value, want in (("Light", "light", "light"), ("Dark", "dark", "dark"), ("System", "system", "dark"),
                              ("Dynamic", "dynamic", "light")):
        page.get_by_role("radio", name=name).check()
        now = page.evaluate("() => ({ theme: document.documentElement.dataset.theme, same: window.__sameLoad === true })")
        A.check(f"picking {name} changes <html data-theme> to {want} at once and stores settings.theme '{value}'",
                now == {"theme": want, "same": True} and stored_theme(page) == value and picked(page) == [value],
                (now, stored_theme(page), picked(page)))
    A.check("Dynamic at 07:00 in Darwin is light, and its line says what it does",
            shown(page) == "light" and help_line(page) == "Light by day, dark from sunset to sunrise in Darwin.", help_line(page))
    page.get_by_role("radio", name="Light").check()
    A.check("Light says it stays light whatever the phone is set to", help_line(page) == "Always light, whatever the phone is set to.",
            help_line(page))
    A.reload_to(page, "settings")
    A.check("the choice survives a restart: Light is marked and shown after a reload",
            picked(page) == ["light"] and shown(page) == "light", (picked(page), shown(page)))
    ctx.close()


def check_older(browser, url, errors):
    old = doc_with(entries=True)
    ctx, page = phone(browser, errors, "older", scheme="light", doc=old)
    A.open_today(page, url)
    before = page.evaluate("() => localStorage.getItem('pantry.v1')")
    open_settings(page, url)
    first = (picked(page), shown(page))
    page.emulate_media(color_scheme="dark")
    follow(page, "dark")
    after = page.evaluate("() => localStorage.getItem('pantry.v1')")
    A.check("an older document without settings.theme opens as System (marked, following the phone) and stays unchanged",
            json.loads(before) == old and after == before and first == (["system"], "light") and shown(page) == "dark",
            (first, shown(page), after == before))
    ctx.close()


# ── the browser's own colours ─────────────────────────────────────
def check_bars(browser, url, errors, colours):
    for phone_scheme, name in (("dark", "Light"), ("light", "Dark")):
        want = name.lower()
        ctx, page = phone(browser, errors, f"bars-{want}", scheme=phone_scheme)
        open_settings(page, url)
        page.get_by_role("radio", name=name).check()
        got = bars(page)
        scheme = page.evaluate("() => ({ css: getComputedStyle(document.documentElement).colorScheme, "
                               "meta: document.querySelector('meta[name=\"color-scheme\"]').content })")
        A.check(f"{name} picked on a phone set to {phone_scheme}: every theme-color the browser can use says {colours[want]}",
                got and all(c == colours[want] for c in got), got)
        A.check(f"{name} picked on a phone set to {phone_scheme}: color-scheme is only {want}, so the browser's own dark mode keeps out",
                scheme["css"].split() in (["only", want], [want, "only"]) and scheme["meta"] == f"only {want}", scheme)
        A.reload_to(page, "settings")
        reloaded = bars(page)
        A.check(f"{name} on a phone set to {phone_scheme}: the theme-color is right again after a restart",
                reloaded and all(c == colours[want] for c in reloaded), reloaded)

        # System follows the phone live, the theme-color with it
        page.get_by_role("radio", name="System").check()
        seen = {}
        for scheme_now in ("light", "dark", "light"):
            page.emulate_media(color_scheme=scheme_now)
            follow(page, scheme_now)
            seen[scheme_now] = (shown(page), bars(page))
        A.check(f"System follows prefers-color-scheme live, the theme-color with it (from a phone set to {phone_scheme})",
                all(t == s and b and all(c == colours[s] for c in b) for s, (t, b) in seen.items()), seen)
        ctx.close()


def pixel(page, x, y):
    png = page.screenshot(clip={"x": x, "y": y, "width": 1, "height": 1}, scale="css")
    return page.evaluate("""async b64 => { const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
        const c = document.createElement('canvas'); c.width = 1; c.height = 1; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
        return [...g.getImageData(0, 0, 1, 1).data].slice(0, 3); }""", base64.b64encode(png).decode())


def check_forced_dark(p, url, errors):
    """Light under the browser's own forced dark mode: Chromium's, the engine Samsung Internet runs."""
    browser = p.chromium.launch(args=["--blink-settings=forceDarkModeEnabled=true"])
    try:
        ctx = browser.new_context(**A.PHONE, color_scheme="dark", service_workers="block")
        ctx.clock.set_fixed_time(A.NOW)
        probe = ctx.new_page()
        probe.set_content('<body style="margin:0;background:#FFFFFF"></body>')
        control = pixel(probe, 10, 10)
        page = ctx.new_page()
        A.watch(page, errors, "forced-dark")
        A.set_text(page, 1.0)
        open_settings(page, url)
        page.get_by_role("radio", name="Light").check()
        page.wait_for_timeout(100)
        light = pixel(page, 352, 6)               # the top bar's canvas, right of the title
        page.screenshot(path=str(WORK / "forced-dark-light.png"))
        A.check("under the browser's forced dark mode (a plain white page turns dark), Light stays light",
                max(control) < 128 and min(light) >= 240, {"plain white page": control, "Pantry, Light": light})
        ctx.close()
    finally:
        browser.close()


# ── Dynamic: Darwin's sunset and sunrise, with an injected clock ──
def check_dynamic(browser, url, errors, colours):
    rise, sset = TABLE[DAY]
    for label, when, want in (("a moment before sunset", at(DAY, sset, -5), "light"), ("a moment after sunset", at(DAY, sset, 5), "dark"),
                              ("a moment before sunrise", at(DAY, rise, -5), "dark"), ("a moment after sunrise", at(DAY, rise, 5), "light")):
        ctx, page = phone(browser, errors, f"open-{want}", scheme="light" if want == "dark" else "dark", clock=when,
                          doc=doc_with("dynamic"))
        open_settings(page, url)
        got = (shown(page), bars(page))
        A.check(f"Dynamic, the app opening {label} ({when:%H:%M} Darwin) shows {want}, the theme-color with it",
                got[0] == want and got[1] and all(c == colours[want] for c in got[1]), got)
        ctx.close()

    for event, hhmm, before, after in (("sunset", sset, "light", "dark"), ("sunrise", rise, "dark", "light")):
        # the clock crosses it with the app open
        ctx, page = phone(browser, errors, f"cross-{event}", clock=at(DAY, hhmm, -5), doc=doc_with("dynamic"))
        open_settings(page, url)
        page.clock.pause_at(at(DAY, hhmm, -3))
        then = shown(page)
        page.clock.run_for(6 * 60 * 1000)
        now = (shown(page), bars(page))
        A.check(f"Dynamic switches by itself at {event} while the app is open: {before} at {hhmm} - 3 min, {after} at + 3 min",
                then == before and now[0] == after and now[1] and all(c == colours[after] for c in now[1]), (then, now))
        ctx.close()

        # the phone froze the page in the background while the clock crossed it
        ctx, page = phone(browser, errors, f"wake-{event}", clock=at(DAY, hhmm, -5), doc=doc_with("dynamic"))
        open_settings(page, url)
        page.clock.pause_at(at(DAY, hhmm, -3))
        then = shown(page)
        visibility(page, "hidden")
        page.clock.set_system_time(at(DAY, hhmm, 3))      # no timer fires: the page was frozen
        frozen = shown(page)
        visibility(page, "visible")
        A.check(f"Dynamic is right when the page becomes visible again after the clock crossed {event} ({before} -> {after})",
                then == before and frozen == before and shown(page) == after, (then, frozen, shown(page)))
        ctx.close()


def switch_at(page, lo, hi, before, after):
    """The moment Dynamic turns from `before` to `after` between lo and hi, found to the second: the injected clock is
    set to each probe (no timer fires) and the page brought back to the foreground, which applies the theme again.
    None when lo or hi does not show what it should."""
    def show(t):
        page.clock.set_system_time(t)
        visibility(page, "visible")
        return shown(page)
    if show(lo) != before or show(hi) != after:
        return None
    while (hi - lo).total_seconds() > 1:
        mid = lo + (hi - lo) / 2
        if show(mid) == before:
            lo = mid
        else:
            hi = mid
    return hi


def check_table(browser, url, errors):
    """The sunrise and sunset Dynamic switches at against the published table, compared as absolute times, on a phone
    in Darwin's zone and on one in UTC (the instants must not move with the phone's zone)."""
    got = {}
    for tz in ("Australia/Darwin", "UTC"):
        first = min(TABLE)
        ctx, page = phone(browser, errors, f"table-{tz}", clock=at(first, "00:00", -60), doc=doc_with("dynamic"), tz=tz)
        open_settings(page, url)
        page.clock.pause_at(at(first, "00:00", -30))
        got[tz] = {date: (switch_at(page, at(date, rise, -10), at(date, rise, 10), "dark", "light"),
                          switch_at(page, at(date, sset, -10), at(date, sset, 10), "light", "dark"))
                   for date, (rise, sset) in sorted(TABLE.items())}
        ctx.close()
    off = {}
    for date, (rise, sset) in TABLE.items():
        found = got["Australia/Darwin"][date]
        off[date] = tuple(None if f is None else round((f - at(date, t)).total_seconds()) for f, t in zip(found, (rise, sset)))
    secs = [s for pair in off.values() for s in pair]
    worst = None if None in secs else max(abs(s) for s in secs)
    A.check(f"Darwin's sunrise and sunset (where Dynamic switches) match sunrisesunsettime.org's 2026 table within 3 minutes "
            f"on {len(TABLE)} dates across the year (worst {worst} s; seconds off, sunrise and sunset: {off})",
            worst is not None and worst <= 180, off)
    apart = [abs((a - b).total_seconds()) for date in TABLE for a, b in zip(got["UTC"][date], got["Australia/Darwin"][date])
             if a is not None and b is not None]
    A.check("the switch times are absolute: a phone in UTC switches at the same instants (within the 1 s search step)",
            len(apart) == 2 * len(TABLE) and max(apart) <= 1, {"UTC": got["UTC"], "Darwin": got["Australia/Darwin"]})


# ── sync: another device's theme arrives without a reload ─────────
class Repo:
    """A GitHub Contents API stand-in: the repo, the file's object view (sha and base64 content) and PUT with a sha."""
    CORS = {"access-control-allow-origin": "*",
            "access-control-allow-headers": "authorization, accept, content-type, x-github-api-version",
            "access-control-allow-methods": "GET, PUT, OPTIONS"}

    def __init__(self, doc):
        self.store(doc)

    def store(self, doc):
        self.text = json.dumps(doc, separators=(",", ":")) + "\n"
        data = self.text.encode("utf-8")
        self.sha = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

    def doc(self):
        return json.loads(self.text)

    def handle(self, route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers=self.CORS)

        def answer(status, payload):
            return route.fulfill(status=status, headers=self.CORS, content_type="application/json", body=json.dumps(payload))

        path = urllib.parse.urlsplit(req.url).path
        if path == "/repos/Estaed/Pantry-Data":
            return answer(200, {"full_name": "Estaed/Pantry-Data", "private": True})
        if path != "/repos/Estaed/Pantry-Data/contents/pantry-data.json":
            return answer(404, {"message": "Not Found"})
        if req.method == "GET":
            data = self.text.encode("utf-8")
            return answer(200, {"type": "file", "sha": self.sha, "size": len(data), "encoding": "base64",
                                "content": base64.b64encode(data).decode()})
        sent = json.loads(req.post_data or "{}")
        if sent.get("sha") != self.sha:
            return answer(409, {"message": "does not match"})
        self.store(json.loads(base64.b64decode(sent["content"]).decode("utf-8")))
        return answer(200, {"content": {"sha": self.sha}})


def check_sync(browser, url, errors):
    repo = Repo(doc_with("light"))                   # another device picked Light
    ctx, page = phone(browser, errors, "sync", scheme="dark")
    ctx.route("https://api.github.com/**", repo.handle)
    open_settings(page, url)
    page.evaluate("() => { window.__sameLoad = true; }")
    first = shown(page)
    page.get_by_label("GitHub token").fill(TOKEN)
    page.get_by_role("button", name="Save and sync").click()
    page.wait_for_function("() => document.documentElement.dataset.theme === 'light'", timeout=15000)
    page.wait_for_function("() => window.PantrySync && !PantrySync.status().running", timeout=15000)
    same = page.evaluate("() => window.__sameLoad === true")
    A.check("a synced document with settings.theme 'light' is applied without a reload (dark phone on System before)",
            first == "dark" and same and shown(page) == "light" and picked(page) == ["light"] and bars(page) == [canvases()["light"]],
            (first, same, shown(page), picked(page), bars(page)))
    other = repo.doc()
    other["settings"]["theme"] = "dark"
    repo.store(other)                                # then Dark on that device
    visibility(page, "visible")                      # the app comes back to the foreground: sync pulls
    page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'", timeout=15000)
    A.check("the other device's next pick (Dark) arrives the same way, still without a reload",
            page.evaluate("() => window.__sameLoad === true") and picked(page) == ["dark"] and stored_theme(page) == "dark",
            (picked(page), stored_theme(page)))
    ctx.close()


# ── the screen at 360 px, text 1.0, and where test_sync.py checks Settings ──
SEG_JS = """async () => { await document.fonts.ready;
  const seg = document.querySelector('.settings-seg');
  const labels = [...seg.querySelectorAll('span')].map(s => { const r = document.createRange(); r.selectNodeContents(s);
    const b = r.getBoundingClientRect(), box = s.getBoundingClientRect();
    return { text: s.textContent, lines: new Set([...r.getClientRects()].map(x => Math.round(x.top))).size,
             inside: b.left >= box.left - 0.5 && b.right <= box.right + 0.5 }; });
  return { columns: getComputedStyle(seg).gridTemplateColumns.split(' ').length, labels }; }"""


def check_screen(browser, url, errors):
    ctx, page = phone(browser, errors, "screen")
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        open_settings(page, url)
        A.reload_to(page, "settings")
        A.fits(page, f"Settings with the theme choices, {scheme}, 360 x 780, text 1.0")
        seg = page.evaluate(SEG_JS)
        A.check(f"the four choices sit in one row at 360 px, text 1.0 ({scheme}), each name on one line inside its segment",
                seg["columns"] == 4 and all(lab["lines"] == 1 and lab["inside"] for lab in seg["labels"]), seg)
        top = page.locator('[data-part="theme"]').bounding_box()
        A.check(f"the theme choices show without scrolling at 360 x 780 ({scheme})", top["y"] + top["height"] <= 780, top)
        page.screenshot(path=str(WORK / f"settings-{scheme}.png"), full_page=True)
    for label, text, size in (("150 % text", A.BIG_TEXT, (360, 780)), ("240 px", 1.0, (240, 520))):
        A.set_text(page, text)
        page.set_viewport_size({"width": size[0], "height": size[1]})
        A.reload_to(page, "settings")
        A.fits(page, f"Settings with the theme choices at {label}")
        seg = page.evaluate(SEG_JS)
        A.check(f"at {label} the choices go two by two, each name on one line inside its segment",
                seg["columns"] == 2 and all(lab["lines"] == 1 and lab["inside"] for lab in seg["labels"]), seg)
        # a full-page capture puts the browser's text size back to 100 %, so the 150 % one is of the viewport
        page.screenshot(path=str(WORK / f"settings-{label.split()[0]}.png"), full_page=text == 1.0)
    ctx.close()


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    colours = canvases()
    srv, site, url = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn, args in (("choice", check_choice, ()), ("older document", check_older, ()),
                                   ("theme-color", check_bars, (colours,)), ("dynamic", check_dynamic, (colours,)),
                                   ("table", check_table, ()), ("sync", check_sync, ()), ("screen", check_screen, ())):
                A.guarded(name, fn, browser, url, errors, *args)
            browser.close()
            A.guarded("forced dark", check_forced_dark, p, url, errors)
        A.check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

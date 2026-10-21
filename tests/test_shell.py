"""Checks for Task-07: screens that move, a router that forgives (app/core.js, app/base.css, index.html).

Run from the repo root: python tests/test_shell.py   (exit 0 = no FAIL). Reuses the gate's server, phone and checks
from tests/acceptance.py, at Tarik's text size (1.0) and 360 x 780. The document is the committed fixture
(tests/fixtures/mynetdiary-slice.json through tools/import_mynetdiary.py, the days design/screens.html shows); the
long day for the scroll checks adds synthetic entries in code. Screens are reached by route; Today's own DOM is
never driven (a tap that lands where Today's Add would be is judged by the screen it ends on).

The tap guard is judged by each event's own time: finger taps go through the DevTools protocol
(Input.dispatchTouchEvent) with the timestamp each tap claims, in a context without Playwright's fake clock (which
replaces event.timeStamp), so "200 ms later" is what the events say, never a sleep.
The motion is read from document.getAnimations(): the stage's two layers (the screen left, the screen shown) carry
the keyframes, durations and easings; the real screen under them must never move. What the layers paint is read
through a handle the page keeps on each shadow root it opens (the copies' roots are closed): the copy of the screen
left must match it at the first frame, the copy of the screen shown must match the real one at the last.
"""
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402
import test_entry as E  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
DAY = E.DAY
DINNER = E.DINNER
POTATO = E.POTATO
ENTER = "cubic-bezier(0.22, 1, 0.36, 1)"   # tokens.css --ease-enter
EXIT = "cubic-bezier(0.4, 0, 1, 1)"        # tokens.css --ease-exit
FAST, BASE, SLOW = 120, 200, 320            # tokens.css --dur-fast, --dur-base, --dur-slow

# Every member of window.Pantry with its type and Function.length, as the header of app/core.js lists them.
API = [("doc", "function", 0), ("change", "function", 1), ("subscribe", "function", 1), ("dirty", "function", 0),
       ("changes", "function", 0), ("markClean", "function", 1), ("syncState", "function", 0), ("setSyncState", "function", 1),
       ("problem", "function", 0), ("starter", "object", None), ("today", "function", 0), ("dayLabel", "function", 1),
       ("mealNow", "function", 0), ("usualAmounts", "function", 2), ("totals", "function", 2), ("sum", "function", 1),
       ("fmt", "function", 1), ("esc", "function", 1), ("icon", "function", 1), ("MACROS", "object", None),
       ("view", "function", 2), ("go", "function", 1), ("back", "function", 0), ("home", "function", 0),
       ("css", "function", 1), ("toast", "function", 1), ("haptic", "function", 0), ("removeEntry", "function", 1)]
SIGNATURES = ["Pantry.doc()", "Pantry.change(fn, opts)", "Pantry.subscribe(fn)", "Pantry.dirty()", "Pantry.changes()",
              "Pantry.markClean(upTo)", "Pantry.syncState()", "Pantry.setSyncState(patch)", "Pantry.problem()", "Pantry.starter",
              "Pantry.today()", "Pantry.mealNow()", "Pantry.usualAmounts(foodId, meal)", "Pantry.dayLabel(date)",
              "Pantry.totals(food, grams)", "Pantry.sum(entries)", "Pantry.fmt(n, digits)", "Pantry.esc(text)", "Pantry.icon(name)",
              "Pantry.view(name, def)", "Pantry.go(name, ...args)", "Pantry.back()", "Pantry.home()", "Pantry.css(text)",
              "Pantry.toast(text, opts)", "Pantry.haptic(kind)", "Pantry.removeEntry(id)", "Pantry.MACROS"]

STAGE_JS = """() => {
  const host = document.getElementById('stage');
  const real = document.querySelector('#app > .screen');
  const layers = document.getAnimations().filter(a => a.effect && a.effect.target && a.effect.target.classList
    && a.effect.target.classList.contains('stage-layer'));
  const box = real.getBoundingClientRect(), x = innerWidth / 2, y = innerHeight / 2, hit = document.elementFromPoint(x, y);
  return {
    nav: host ? host.dataset.nav : null,
    top: host && host.lastElementChild ? host.lastElementChild.dataset.layer : null,
    layers: Object.fromEntries(layers.map(a => [a.effect.target.dataset.layer, {
      ms: a.effect.getTiming().duration, easing: a.effect.getTiming().easing,
      frames: a.effect.getKeyframes().map(k => [Number(k.opacity), k.translate ? parseFloat(k.translate) : null]) }])),
    screen: real.dataset.screen, hash: location.hash,
    real: { animations: real.getAnimations({ subtree: true }).filter(a => !(a.effect && a.effect.getTiming().iterations === Infinity)).length,
            left: Math.round(box.left), hitInside: Boolean(hit && real.contains(hit)) },
  };
}"""

FRAMES_JS = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"


def frames(page):
    page.evaluate(FRAMES_JS)


def stage_gone(page):
    """True once the motion's stage has left (it plays at most 320 ms); False after 3 s, so a check says it."""
    try:
        page.wait_for_function("() => !document.getElementById('stage')", timeout=3000)
        return True
    except Exception:  # noqa: BLE001 - Playwright's TimeoutError; the check that asked reports it
        return False


def shows(page, name, ms=3000):
    """True when the named screen is the real one within ms; False instead of a 30 s timeout."""
    try:
        page.wait_for_selector(f'#app > [data-screen="{name}"]', timeout=ms)
        return True
    except Exception:  # noqa: BLE001 - Playwright's TimeoutError; the check that asked reports it
        return False


def load(page, doc):
    page.evaluate("d => { Pantry.change(() => d, { dirty: false }); }", doc)


def go(page, *args):
    page.evaluate("a => Pantry.go(...a)", list(args))
    page.wait_for_selector(f'#app > [data-screen="{args[0]}"]')


# ── API ───────────────────────────────────────────────────────────
def check_api(browser, url, errors, doc):
    ctx, page = A.phone(browser, errors, "shell-api", text=1.0)
    A.open_today(page, url)
    got = page.evaluate("""() => Object.keys(Pantry).map(k => [k, typeof Pantry[k],
        typeof Pantry[k] === 'function' ? Pantry[k].length : null])""")
    A.check("Pantry keeps every name, type and signature (Function.length) the header of app/core.js lists, and no other",
            sorted(map(tuple, got)) == sorted(API), sorted(set(map(tuple, got)) ^ set(API)))
    header = (ROOT / "app" / "core.js").read_text(encoding="utf-8").split("*/", 1)[0]
    missing = [s for s in SIGNATURES if s not in header]
    A.check("the header of app/core.js still writes each signature", not missing, missing)
    A.check("window.Pantry is frozen", page.evaluate("Object.isFrozen(Pantry)"))
    meta = page.evaluate("document.querySelector('meta[name=viewport]').content")
    A.check("the viewport resizes with the keyboard, so a field's button stays above it (interactive-widget=resizes-content)",
            "interactive-widget=resizes-content" in meta, meta)
    ctx.close()


# ── motion ────────────────────────────────────────────────────────
def motion_ok(st, kind):
    """The stage's layers as Tarik Base v6 → Motion writes each kind."""
    old, new = st["layers"].get("old"), st["layers"].get("new")
    if not old or not new:
        return False
    if kind == "push":
        return (old == {"ms": FAST, "easing": EXIT, "frames": [[1, None], [0, None]]}
                and new == {"ms": SLOW, "easing": ENTER, "frames": [[0, 24], [1, 0]]} and st["top"] == "new")
    if kind == "back":
        return (old == {"ms": BASE, "easing": EXIT, "frames": [[1, 0], [0, 24]]}
                and new == {"ms": BASE, "easing": ENTER, "frames": [[0, None], [1, None]]} and st["top"] == "old")
    return (old == {"ms": BASE, "easing": EXIT, "frames": [[1, None], [0, None]]}
            and new == {"ms": BASE, "easing": ENTER, "frames": [[0, None], [1, None]]} and st["top"] == "new")


def opacity_only(st):
    return bool(st["layers"]) and all(t is None for layer in st["layers"].values() for _, t in layer["frames"])


def run_three(page):
    """A push, a back and a return to Today, each read while it plays: (push, back, home)."""
    push = page.evaluate(f"() => {{ Pantry.go('settings'); return ({STAGE_JS})(); }}")
    stage_gone(page)
    back = page.evaluate(f"""() => new Promise(done => {{
        addEventListener('popstate', () => done(({STAGE_JS})()), {{ once: true }}); history.back(); }})""")
    stage_gone(page)
    go(page, "entry", DINNER)
    stage_gone(page)
    home = page.evaluate(f"() => {{ Pantry.go('today', '{DAY}'); return ({STAGE_JS})(); }}")
    stage_gone(page)
    return push, back, home


def check_motion(browser, url, errors, doc):
    ctx, page = A.phone(browser, errors, "shell-motion", text=1.0)
    A.open_today(page, url)
    load(page, doc)
    go(page, "today", DAY)
    stage_gone(page)
    push, back, home = run_three(page)
    A.check("a push (Pantry.go('settings')) slides the new screen 24 px in from the right while it fades in (320 ms, "
            "ease-enter) over the old one fading out (120 ms, ease-exit); Settings is the screen",
            push["nav"] == "push" and motion_ok(push, "push") and push["screen"] == "settings" and push["hash"] == "#/settings", push)
    A.check("a back (popstate) reverses it: the screen left slides 24 px to the right as it fades (200 ms, ease-exit) over "
            "the one returned to fading in; Today for 8 Aug is the screen",
            back["nav"] == "back" and motion_ok(back, "back") and back["screen"] == "today" and back["hash"] == f"#/today/{DAY}", back)
    A.check("a return to Today (Pantry.go('today', date) from Edit entry) crossfades, nothing slides (200 ms)",
            home["nav"] == "home" and motion_ok(home, "home") and home["screen"] == "today" and home["hash"] == f"#/today/{DAY}", home)
    A.check("while the motion plays the real screen is in place and takes the taps: it has no animation of its own, sits "
            "at x 0, and the middle of the screen hits it, not the stage",
            all(s["real"] == {"animations": 0, "left": 0, "hitInside": True} for s in (push, back, home)),
            [s["real"] for s in (push, back, home)])
    go(page, "settings")
    A.fits(page, "Settings while the push plays, 360 px, text 1.0")
    A.check("the stage leaves once the motion is over", stage_gone(page))

    # The browser already animated the back swipe: the app adds nothing.
    def fake_back(ua):
        return page.evaluate(f"""ua => {{ history.pushState({{ depth: 0 }}, '', '#/today/{DAY}');
            dispatchEvent(new PopStateEvent('popstate', {{ state: history.state, hasUAVisualTransition: ua }}));
            return ({STAGE_JS})(); }}""", ua)
    stage_gone(page)
    plain = fake_back(False)
    stage_gone(page)
    go(page, "settings")
    stage_gone(page)
    done = fake_back(True)
    A.check("a popstate that says the browser already animated it (hasUAVisualTransition) runs no motion of its own and "
            "still shows Today; the same popstate without it runs the back",
            plain["nav"] == "back" and done["nav"] is None and not done["layers"] and done["screen"] == "today", (plain["nav"], done))

    # Reduced motion: every slide becomes a fade of the same length.
    page.emulate_media(reduced_motion="reduce")
    go(page, "today", DAY)
    stage_gone(page)
    calm = run_three(page)
    A.check("with reduced motion nothing moves: push, back and return to Today animate opacity only, with the same "
            "durations (320 / 200 / 200 ms in)",
            all(opacity_only(s) for s in calm) and [s["layers"]["new"]["ms"] for s in calm] == [SLOW, BASE, BASE]
            and [s["nav"] for s in calm] == ["push", "back", "home"], calm)
    page.emulate_media(reduced_motion="no-preference")

    # A back, or another screen, while the motion still plays: the right screen, no console error.
    before = len(errors)
    page.evaluate("() => { Pantry.go('settings'); history.back(); }")
    page.wait_for_function(f"() => location.hash === '#/today/{DAY}' && document.querySelector('#app > .screen').dataset.screen === 'today'")
    stage_gone(page)
    page.evaluate(f"() => {{ Pantry.go('settings'); Pantry.go('entry', '{DINNER}'); }}")
    page.wait_for_selector('#app > [data-screen="entry"]')
    stage_gone(page)
    frames(page)
    A.check("a back during a running push ends on Today, a push during a push on Edit entry, with no console error "
            "(the cut-short motion's promises are handled)",
            page.evaluate("document.querySelector('#app > .screen').dataset.screen") == "entry" and len(errors) == before,
            errors[before:])
    ctx.close()


# ── what the motion shows ─────────────────────────────────────────
SHADOWS = """(() => { const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (o) {
    const root = attach.call(this, o); (window.__shadows = window.__shadows || []).push(root); return root; }; })()"""

# Measures the real screen, makes the move, freezes the copy of the screen left at its first frame and the copy of
# the screen shown at its last, and compares each with the real one element for element: box (0.5 px), font, colours
# and the CSS animations running on it (their time within 50 ms). A touch then ends the motion.
COPIES_JS = r"""async move => {
  const PROPS = ['font-family', 'font-size', 'font-weight', 'font-stretch', 'font-style', 'line-height', 'letter-spacing',
                 'color', 'background-color'];
  const measure = root => [root, ...root.querySelectorAll('*')].map(el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return { el: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : ''),
             box: [r.x, r.y, r.width, r.height], style: PROPS.map(p => s.getPropertyValue(p)),
             anims: el.getAnimations().filter(a => a.animationName).map(a => [a.animationName, a.currentTime]).sort() };
  });
  const diff = (real, copy) => {
    if (real.length !== copy.length) return { count: [real.length, copy.length] };
    const off = [];
    real.forEach((a, i) => {
      const b = copy[i], d = Math.max(...a.box.map((v, k) => Math.abs(v - b.box[k])));
      const props = PROPS.flatMap((p, k) => (a.style[k] === b.style[k] ? [] : [`${p}: ${a.style[k]} | ${b.style[k]}`]));
      if (a.anims.length !== b.anims.length || a.anims.some(([n, t], k) => n !== b.anims[k][0] || Math.abs(t - b.anims[k][1]) > 50)) {
        props.push(`animations: ${JSON.stringify(a.anims)} | ${JSON.stringify(b.anims)}`);
      }
      if (d > 0.5 || props.length) off.push({ el: a.el, d: Math.round(d * 10) / 10, props });
    });
    return { total: off.length, of: real.length, off: off.slice(0, 4) };
  };
  const was = measure(document.querySelector('#app > .screen'));
  await new Promise(done => {
    if (move.back) { addEventListener('popstate', () => done(), { once: true }); history.back(); } else { Pantry.go(...move.go); done(); }
  });
  const host = document.getElementById('stage');
  if (!host) return { nav: null };
  const layer = name => host.querySelector(`[data-layer="${name}"]`);
  const motion = el => document.getAnimations().find(a => a.effect && a.effect.target === el);
  const copy = el => window.__shadows.find(r => r.host === el).querySelector('.screen');
  const old = motion(layer('old')), shown = motion(layer('new'));
  old.pause(); old.currentTime = 0;
  shown.pause(); shown.currentTime = shown.effect.getTiming().duration;
  const out = { nav: host.dataset.nav, first: diff(was, measure(copy(layer('old')))),
                last: diff(measure(document.querySelector('#app > .screen')), measure(copy(layer('new')))) };
  dispatchEvent(new PointerEvent('pointerdown'));
  return out;
}"""


def check_copies(browser, url, errors, doc):
    for scheme in ("dark", "light"):
        ctx, page = A.phone(browser, errors, f"shell-copies-{scheme}", text=1.0, init=SHADOWS)
        page.emulate_media(color_scheme=scheme)
        A.open_today(page, url)
        load(page, doc)
        go(page, "today", DAY)
        stage_gone(page)
        seen = {}
        for route in (("add", "dinner", DAY), ("entry", DINNER), ("settings",), ("scan", "dinner", DAY)):
            seen[f"push to {route[0]}"] = page.evaluate(COPIES_JS, {"go": list(route)})
            stage_gone(page)
            seen[f"back from {route[0]}"] = page.evaluate(COPIES_JS, {"back": True})
            stage_gone(page)
        go(page, "entry", DINNER)
        stage_gone(page)
        seen["return to Today"] = page.evaluate(COPIES_JS, {"go": ["today", DAY]})
        stage_gone(page)
        # the gram sheet's Add returns to Today with the sheet open; its rise ended long before (Codex review, 2026-10-21)
        go(page, "add", "dinner", DAY)
        stage_gone(page)
        page.locator('[data-screen="add"] .log-open').first.click()
        page.wait_for_timeout(1000)
        seen["return to Today from the gram sheet"] = page.evaluate(COPIES_JS, {"go": ["today", DAY]})
        stage_gone(page)
        bad = {k: v for k, v in seen.items()
               if not v["nav"] or v["first"].get("total") != 0 or v["last"].get("total") != 0}
        A.check(f"{scheme}: every push, back and return to Today starts on a copy that matches the screen left and ends on "
                "one that matches the screen shown, element for element (box within 0.5 px, font, colours, running CSS "
                "animations at the same time), so nothing jumps when the motion ends", not bad, bad)
        ctx.close()


# ── scroll ────────────────────────────────────────────────────────
def long_day(doc):
    """The fixture plus 16 synthetic snacks on 8 Aug, so Today for that day scrolls at 360 x 780."""
    d = json.loads(json.dumps(doc))
    for i in range(16):
        d["entries"].append({"id": f"synthetic-scroll-{i}", "date": DAY, "meal": "snacks", "foodId": POTATO,
                             "amount": "100 g", "grams": 100, "totals": {"kcal": 59}})
    return d


def check_scroll(browser, url, errors, doc):
    ctx, page = A.phone(browser, errors, "shell-scroll", text=1.0)
    A.open_today(page, url)
    load(page, long_day(doc))
    go(page, "today", DAY)
    room = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    A.check("Today for the long 8 Aug scrolls at 360 x 780 (room for the scroll checks)", room >= 400, room)

    page.evaluate("scrollTo(0, 400)")
    go(page, "add", "dinner", DAY)
    at_list = page.evaluate("scrollY")
    page.go_back()
    page.wait_for_selector('#app > [data-screen="today"]')
    gesture = page.evaluate("scrollY")
    page.evaluate("scrollTo(0, 250)")
    go(page, "add", "dinner", DAY)
    page.locator('#app > [data-screen="add"]').get_by_role("button", name="Back").click()
    page.wait_for_selector('#app > [data-screen="today"]')
    button = page.evaluate("scrollY")
    A.check("the list opens at the top; back to Today (gesture, then the Back button) puts Today where he left it (400, 250)",
            at_list == 0 and gesture == 400 and button == 250, (at_list, gesture, button))

    go(page, "entry", DINNER)
    page.get_by_label("Grams").fill("500")
    page.locator('#app > [data-screen="entry"]').get_by_role("button", name="Save").click()
    page.wait_for_selector('#app > [data-screen="today"]')
    saved = page.evaluate("scrollY")
    page.evaluate("scrollTo(0, 300)")
    go(page, "today", DAY)
    again = page.evaluate("scrollY")
    A.check("a save that returns with Pantry.go('today', date) opens Today at the top, and so does any Pantry.go('today')",
            saved == 0 and again == 0, (saved, again))

    # A popstate that leaves the address as it is (the gram sheet's own entry): no motion, no new screen, no scroll.
    stage_gone(page)
    page.evaluate("scrollTo(0, 300)")
    same = page.evaluate(f"""() => new Promise(done => {{
        const screen = document.querySelector('#app > .screen');
        history.pushState({{ ...(history.state || {{}}), depth: (history.state.depth || 0) + 1, probe: 1 }}, '', location.href);
        addEventListener('popstate', () => requestAnimationFrame(() => done({{ stage: Boolean(document.getElementById('stage')),
            kept: document.querySelector('#app > .screen') === screen, y: scrollY, hash: location.hash }})), {{ once: true }});
        history.back(); }})""")
    A.check("a popstate that leaves the address unchanged changes nothing: no motion, the same screen, the same scroll",
            same == {"stage": False, "kept": True, "y": 300, "hash": f"#/today/{DAY}"}, same)
    ctx.close()


# ── the tap guard ─────────────────────────────────────────────────
class Finger:
    """Taps through the DevTools protocol, each with the time it claims (seconds since the epoch)."""

    def __init__(self, page):
        self.page = page
        self.cdp = page.context.new_cdp_session(page)
        self.t0 = time.time() + 5
        self.presses = 0
        page.evaluate("() => { window.__ups = 0; addEventListener('pointerup', () => { window.__ups += 1; }, true); }")

    def settled(self):
        """Every press sent so far has reached the page (pointerup is never held), and two frames have passed."""
        self.page.wait_for_function("n => window.__ups >= n", arg=self.presses)
        frames(self.page)

    @staticmethod
    def spot(locator_or_xy):
        if isinstance(locator_or_xy, tuple):
            return locator_or_xy
        box = locator_or_xy.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def tap(self, locator_or_xy, at):
        """A finger tap: touch down at t0 + at, up 30 ms later (the click carries the up time)."""
        x, y = self.spot(locator_or_xy)
        t = self.t0 + at
        self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}], "timestamp": t})
        self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": [], "timestamp": t + 0.03})
        self.presses += 1
        return x, y

    def click(self, locator_or_xy, at):
        """A mouse click at the same claimed time scale, so 'right after' is measured the same way."""
        x, y = self.spot(locator_or_xy)
        t = self.t0 + at
        for kind, dt in (("mousePressed", 0), ("mouseReleased", 0.03)):
            self.cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1, "timestamp": t + dt})
        self.presses += 1


PROBE_JS = """() => {
  window.__count = 0;
  Pantry.view('tapprobe', { render(root, target) {
    root.innerHTML = '<button type="button" data-t="go" style="display:block;width:320px;height:120px;margin:40px 20px">Go</button>'
      + '<button type="button" data-t="count" style="display:block;width:320px;height:120px;margin:20px">Count</button>'
      + '<button type="button" data-t="same" style="display:block;width:320px;height:120px;margin:20px">Same address</button>';
    root.querySelector('[data-t="go"]').addEventListener('click', () => Pantry.go(...JSON.parse(decodeURIComponent(target))));
    root.querySelector('[data-t="count"]').addEventListener('click', () => { window.__count += 1; });
    root.querySelector('[data-t="same"]').addEventListener('click', () => {
      addEventListener('popstate', () => { window.__popped = (window.__popped || 0) + 1; }, { once: true });
      history.pushState({ ...(history.state || {}), depth: (history.state.depth || 0) + 1, probe: 1 }, '', location.href);
      history.back(); });
  } });
}"""


def probe(page, *target):
    page.evaluate("t => Pantry.go('tapprobe', encodeURIComponent(JSON.stringify(t)))", list(target))
    shows(page, "tapprobe")
    return page.locator('#app > [data-screen="tapprobe"]')


def until(page, js, arg=None, ms=5000):
    """True once js(arg) is truthy within ms; False instead of a timeout, so the check reports it."""
    try:
        page.wait_for_function(js, arg=arg, timeout=ms)
        return True
    except Exception:  # noqa: BLE001 - Playwright's TimeoutError; the check that asked reports it
        return False


def check_guard(browser, url, errors, doc):
    ctx = browser.new_context(**A.PHONE)            # no fake clock: event.timeStamp is what the taps claim
    page = ctx.new_page()
    A.watch(page, errors, "shell-guard")
    A.set_text(page, 1.0)
    A.open_today(page, url)
    load(page, doc)
    page.evaluate(PROBE_JS)
    finger = Finger(page)
    before = A.stored(page)
    entry = '#app > [data-screen="entry"]'

    # Never held: Pantry.go and popstate right after a tap that changed the screen.
    screen = probe(page, "settings")
    finger.tap(screen.locator('[data-t="go"]'), 0)
    steps = [shows(page, "settings")]
    page.evaluate(f"() => {{ Pantry.go('entry', '{DINNER}'); Pantry.go('today', '{DAY}'); }}")
    steps.append(shows(page, "today"))
    page.go_back()
    steps.append(shows(page, "entry"))
    page.go_back()
    steps.append(shows(page, "settings"))
    A.check("Pantry.go calls and popstates right after a tap that changed the screen are never dropped "
            "(the tap opens Settings, two Pantry.go open Edit entry then Today, two backs end on Settings)",
            all(steps) and page.evaluate("location.hash") == "#/settings", steps)

    # Delete tapped twice: the second tap lands where Today's Add is.
    go(page, "entry", DINNER)
    spot = finger.tap(page.locator(entry).get_by_role("button", name="Delete"), 10)
    shows(page, "today")
    finger.tap(spot, 10.2)
    finger.settled()
    where = page.evaluate("[location.hash, document.querySelector('#app > .screen').dataset.screen]")
    left = len(before["entries"]) - len(A.stored(page)["entries"])
    A.check("Delete tapped twice (200 ms apart) ends on Today, not on Add under the same finger; one entry is deleted",
            where == [f"#/today/{DAY}", "today"] and left == 1, (where, left))

    # The toast's Undo right after Delete: 300 ms after does nothing, 400 ms after works.
    load(page, before)
    go(page, "entry", DINNER)
    finger.tap(page.locator(entry).get_by_role("button", name="Delete"), 20)
    shows(page, "today")
    undo = page.locator("#toast").get_by_role("button", name="Undo")
    undo.wait_for(timeout=3000)
    finger.tap(undo, 20.3)
    finger.settled()
    held = E.find(A.stored(page), DINNER) is None
    A.check("a tap on the toast's Undo 300 ms after the Delete tap does nothing", held and undo.count() == 1, held)
    if held:
        finger.tap(undo, 20.4)
        back = until(page, "id => Pantry.doc().entries.some(e => e.id === id)", DINNER)
        A.check("a tap 400 ms after it works: Undo puts the entry back as it was",
                back and A.stored(page)["entries"] == before["entries"], E.find(A.stored(page), DINNER))

    # A list row's +, 200 ms after the tap that opened the list, logs nothing; 400 ms after, it acts.
    screen = probe(page, "add", "dinner", DAY)
    finger.tap(screen.locator('[data-t="go"]'), 30)
    page.wait_for_selector('#app > [data-screen="add"] [data-act="plus"]')
    plus = page.locator('#app > [data-screen="add"] [data-act="plus"]').first
    count = len(A.stored(page)["entries"])
    plus.evaluate("p => { window.__plus = p; window.__snap = JSON.stringify(Pantry.doc().entries) + p.outerHTML; }")
    changed = "() => JSON.stringify(Pantry.doc().entries) + window.__plus.outerHTML !== window.__snap"
    finger.tap(plus, 30.2)
    finger.settled()
    frames(page)
    quick = page.evaluate(changed)
    A.check("a list row's + tapped 200 ms after the tap that opened the list logs nothing and changes nothing",
            not quick, len(A.stored(page)["entries"]) - count)
    if not quick:
        finger.tap(plus, 30.4)
        A.check("the same + tapped 400 ms after acts (the log or the row changed)", until(page, changed),
                len(A.stored(page)["entries"]) - count)

    # A mouse click is never held, and a popstate that leaves the address as it is arms nothing.
    screen = probe(page, "tapprobe", "%5B%5D")     # Go opens another probe screen with no target
    hash_ = page.evaluate("location.hash")
    finger.tap(screen.locator('[data-t="go"]'), 40)
    until(page, "h => location.hash !== h", hash_)
    count = page.locator('#app > [data-screen="tapprobe"] [data-t="count"]')
    finger.click(count, 40.1)
    finger.settled()
    A.check("a mouse click 100 ms after a tap that changed the screen acts (only finger taps are held)",
            page.evaluate("window.__count") == 1, page.evaluate("window.__count"))
    finger.tap(page.locator('#app > [data-screen="tapprobe"] [data-t="same"]'), 50)
    until(page, "() => window.__popped === 1 && !history.state.probe")
    finger.tap(count, 50.1)
    finger.settled()
    A.check("a popstate that leaves the address unchanged arms no guard: a tap 100 ms after it acts",
            page.evaluate("window.__count") == 2, page.evaluate("window.__count"))
    ctx.close()


# ── 360 x 780, text 1.0, dark and light ───────────────────────────
def check_layout(browser, url, errors, doc):
    ctx, page = A.phone(browser, errors, "shell-layout", text=1.0)
    A.open_today(page, url)
    load(page, doc)
    for scheme, canvas, ink in (("dark", "rgb(14, 14, 14)", "rgb(238, 238, 238)"), ("light", "rgb(247, 247, 247)", "rgb(18, 18, 18)")):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"() => document.documentElement.dataset.theme === '{scheme}'")
        for route in (("today", DAY), ("add", "dinner", DAY), ("entry", DINNER), ("settings",), ("scan", "dinner", DAY)):
            go(page, *route)
            page.wait_for_function("() => document.getElementById('stage')")
            stage = page.evaluate("getComputedStyle(document.getElementById('stage')).backgroundColor")
            stage_gone(page)
            A.fits(page, f"{route[0]} at 360 x 780, text 1.0, {scheme}")
            got = page.evaluate("""() => ({ canvas: getComputedStyle(document.body).backgroundColor,
                ink: getComputedStyle(document.querySelector('#app > .screen .title, #app > .screen h1')).color })""")
            A.check(f"{route[0]} renders in {scheme} (the theme's canvas and ink; the stage paints the same canvas)",
                    got == {"canvas": canvas, "ink": ink} and stage == canvas, (got, stage))
        page.goto(url + "#/")
        page.wait_for_selector('#app > [data-screen="today"]')
    ctx.close()


SCENARIOS = [("API scenario", check_api), ("motion scenario", check_motion), ("copies scenario", check_copies),
             ("scroll scenario", check_scroll),
             ("tap guard scenario", check_guard), ("layout scenario", check_layout)]


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    doc = E.imported_doc()
    srv, site, url = A.start_site()
    E.serve_entry(site)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn in SCENARIOS:
                A.guarded(name, fn, browser, url, errors, json.loads(json.dumps(doc)))
            browser.close()
        A.check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    print(f"\n{'ALL PASS' if not A.FAILS else str(len(A.FAILS)) + ' FAIL'}")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

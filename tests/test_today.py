"""Checks for Task-02, Today: day strip, meals in the corners, the ring, the macro strip, the eaten list; for Task-09:
the budget status tones, days switched in place, the ring swipe, and the motion that shows what changed; and for
Task-12: one whole ring with the meals end to end in alternating tones, over in the base danger red, one grey for the
macro bars with a deviation mark and its points under each, one page per meal with two-tap delete (a double tap's second
tap held) that keeps its page across the meal clock, the floating + and Scan clear of the last row, and no page
scrollbar.

Run from the repo root: python tests/test_today.py [scenario ...]   (exit 0 = no FAIL; names as in SCENARIOS run only
those). Reuses the gate's server and phone from
tests/acceptance.py (360 x 780, text at 150 %, Darwin, 07:00 on 20 Oct 2026). The data is the committed fixture
(tests/fixtures/mynetdiary-slice.json: 8 Aug, 19 Oct, 20 Oct 2026, the days design/screens.html shows), converted by
tools/import_mynetdiary.py into .tmp/test_today/ as Tarik converts his history. Expected numbers are worked out here
from the fixture, never read from the app. Synthetic entries are built in the page only to exercise a rule.
Screenshots of Today in dark and light go to .tmp/today-dark.png and .tmp/today-light.png; at text 1.0, over and within
budget, to .tmp/today-over-<scheme>.png and .tmp/today-within-<scheme>.png. The motion checks install the page clock and
step it; they never wait in real time.
"""
import datetime
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import TimeoutError as PlaywrightTimeout  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
TMP = ROOT / ".tmp" / "test_today"
check = A.check
MEALS = ["breakfast", "lunch", "dinner", "snacks"]
BUDGET = 2200

SCREEN = '[data-screen="today"]'
TEXT = "(s) => { const el = document.querySelector(s); return el ? el.textContent.trim() : null; }"
TEXTS = "(s) => [...document.querySelectorAll(s)].map(el => el.textContent.trim())"

# Start and end of a ring path in degrees clockwise from 12 o'clock, read from the drawn path: the M point, then the
# end point of every arc in it, unwrapped so the end follows the start.
ANGLES_JS = """const angles = p => {
  const n = p.getAttribute('d').match(/-?\\d+(?:\\.\\d+)?/g).map(Number);
  const box = p.ownerSVGElement.viewBox.baseVal, cx = box.width / 2, cy = box.height / 2;
  const pts = [[n[0], n[1]]];
  for (let i = 2; i + 6 < n.length; i += 7) pts.push([n[i + 5], n[i + 6]]);
  const ang = ([x, y]) => Math.atan2(x - cx, cy - y) * 180 / Math.PI;
  let start = ang(pts[0]);
  if (start < -0.5) start += 360;
  let end = start;
  for (let k = 1; k < pts.length; k++) { let d = ang(pts[k]) - ang(pts[k - 1]); while (d <= 0) d += 360; end += d; }
  return [start, end];
};"""
ARCS_JS = "() => {" + ANGLES_JS + """
  return Object.fromEntries([...document.querySelectorAll('[data-screen="today"] .today-seg')].map(p => [p.dataset.meal, angles(p)])); }"""
# The track pieces: [over tint or not, start, end] each.
TRACKS_JS = "() => {" + ANGLES_JS + """
  return [...document.querySelectorAll('[data-screen="today"] .today-track')].map(p => [p.classList.contains('today-full'), ...angles(p)]); }"""

# The second lap over budget: its [start, end], its tone and the tokens it is measured against, as sRGB.
LAP_JS = "() => {" + ANGLES_JS + """
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const g = cv.getContext('2d', { willReadFrequently: true });
  const rgb = c => { g.clearRect(0, 0, 1, 1); g.fillStyle = c; g.fillRect(0, 0, 1, 1); return [...g.getImageData(0, 0, 1, 1).data].slice(0, 3); };
  const s = document.querySelector('[data-screen="today"]'), laps = [...s.querySelectorAll('.today-lap')];
  const probe = v => { const i = document.createElement('i'); i.style.color = v; s.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return rgb(c); };
  return { laps: laps.map(angles), tone: laps.length ? rgb(getComputedStyle(laps[0]).stroke) : null,
           danger: probe('var(--danger)'), canvas: probe('var(--canvas)') }; }"""

# Corner names and kcal against the ring's box; corner drawings and + marks against the drawn ring itself.
CLEAR_JS = """() => {
  const ringEl = document.querySelector('[data-screen="today"] .today-ring');
  const ring = ringEl.getBoundingClientRect(), svg = ringEl.querySelector('svg'), track = svg.querySelector('path');
  const unit = ring.width / svg.viewBox.baseVal.width;
  const radius = Number(track.getAttribute('d').match(/A(-?\\d+(?:\\.\\d+)?)/)[1]);
  const outer = (radius + parseFloat(getComputedStyle(track).strokeWidth) / 2) * unit;
  const cx = ring.left + ring.width / 2, cy = ring.top + ring.height / 2;
  const hit = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  const q = s => [...document.querySelectorAll('[data-screen="today"] ' + s)];
  const words = q('.today-corner .today-cn, .today-corner .today-ck').filter(el => hit(el.getBoundingClientRect(), ring))
    .map(el => el.closest('.today-corner').dataset.meal + ': ' + el.textContent.trim());
  const art = q('.today-corner .today-fs, .today-corner .today-addm').filter(el => {
    const r = el.getBoundingClientRect();
    return Math.hypot(Math.min(Math.max(cx, r.left), r.right) - cx, Math.min(Math.max(cy, r.top), r.bottom) - cy) < outer;
  }).map(el => el.closest('.today-corner').dataset.meal);
  const corners = q('.today-corner').map(el => el.getBoundingClientRect());
  const meet = [[0, 1], [0, 3], [1, 2], [2, 3], [0, 2], [1, 3]].filter(([a, b]) => hit(corners[a], corners[b]));
  return { words, art, meet, corners: q('.today-corner').length };
}"""

# The ring's centre lines (kcal left, its words, eaten / budget): each box's farthest corner from the ring's centre
# against the ring's inner edge, and each line's font size against 1rem.
CENTER_JS = """() => {
  const ringEl = document.querySelector('[data-screen="today"] .today-ring');
  const ring = ringEl.getBoundingClientRect(), svg = ringEl.querySelector('svg'), track = svg.querySelector('path');
  const unit = ring.width / svg.viewBox.baseVal.width;
  const radius = Number(track.getAttribute('d').match(/A(-?\\d+(?:\\.\\d+)?)/)[1]);
  const inner = (radius - parseFloat(getComputedStyle(track).strokeWidth) / 2) * unit;
  const cx = ring.left + ring.width / 2, cy = ring.top + ring.height / 2;
  return { inner, rem: parseFloat(getComputedStyle(document.documentElement).fontSize),
    lines: [...ringEl.querySelectorAll('.today-center > span')].map(el => { const b = el.getBoundingClientRect();
      return [el.textContent.trim(), Math.hypot(Math.max(cx - b.left, b.right - cx), Math.max(cy - b.top, b.bottom - cy)),
              parseFloat(getComputedStyle(el).fontSize)]; }) };
}"""

# The days the strip shows: the ones inside its view (it scrolls through about three months).
STRIP_JS = """() => { const nav = document.querySelector('[data-screen="today"] .today-days'), v = nav.getBoundingClientRect();
  return [...nav.querySelectorAll('.today-day')].filter(d => { const r = d.getBoundingClientRect();
    return r.left >= v.left - 1 && r.right <= v.right + 1; }).map(d => {
  const liq = d.querySelector('.today-liq');
  return { day: d.dataset.day, name: d.querySelector('span').textContent, num: d.querySelector('b').textContent,
           label: d.querySelector('em').textContent, over: d.classList.contains('today-ov'), on: d.classList.contains('today-on'),
           fill: liq ? liq.getBoundingClientRect().height / d.clientHeight : 0,
           wordsFit: [...d.querySelectorAll('span, b, em')].every(w => w.getBoundingClientRect().width <= d.clientWidth) };
}); }"""

# Each macro percentage is readable: inside its bar when it fits, else on the label line under the bar.
MACRO_JS = """() => {
  const labs = [...document.querySelectorAll('[data-screen="today"] .today-labs > div')];
  return [...document.querySelectorAll('[data-screen="today"] .today-bar')].map((bar, i) => {
    const pct = bar.querySelector('.today-pct'), lab = labs[i].querySelector('.today-lpct');
    const inside = getComputedStyle(pct).visibility === 'visible' && pct.getBoundingClientRect().width <= bar.clientWidth;
    const under = getComputedStyle(lab).visibility === 'visible' && getComputedStyle(lab).position === 'static';
    return { pct: pct.textContent, under: lab.textContent.trim(), inside, shownUnder: under };
  });
}"""

# The visible words of an element as line boxes: one rect per line per text node, surrounding spaces left out; words
# inside `skip` (a selector) left out too.
INK_JS = """const ink = (el, skip) => {
  const rects = [], walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let size = null;
  for (let n; (n = walk.nextNode());) {
    const t = n.textContent;
    if (!t.trim() || (skip && n.parentElement.closest(skip)) || getComputedStyle(n.parentElement).visibility !== 'visible') continue;
    const r = document.createRange(); r.setStart(n, t.search(/\\S/)); r.setEnd(n, t.trimEnd().length);
    rects.push(...[...r.getClientRects()].filter(x => x.width > 0));
    if (size === null) size = parseFloat(getComputedStyle(n.parentElement).fontSize);
  }
  return { left: Math.min(...rects.map(x => x.left)), right: Math.max(...rects.map(x => x.right)),
           lines: new Set(rects.map(x => Math.round(x.top))).size, size };
};"""

# Each macro label (its name and grams; the deviation mark over them and its points are check_marks') against its bar
# and its neighbours; the gap the labels keep is one em of their text (0.75rem).
LABELS_JS = "() => {" + INK_JS + """
  const q = s => [...document.querySelectorAll('[data-screen="today"] ' + s)];
  const row = document.querySelector('[data-screen="today"] .today-labs').getBoundingClientRect();
  return { sep: 0.75 * parseFloat(getComputedStyle(document.documentElement).fontSize), row: [row.left, row.right],
           bars: q('.today-bar').map(b => [b.getBoundingClientRect().left, b.getBoundingClientRect().right]),
           labels: q('.today-labs > div').map(el => ink(el, '.today-dev')) };
}"""

# The floating + and Scan (as in MyNetDiary, design/deviations.md): [+ size, + to the screen's right edge, gap to Scan,
# Scan's left edge], and whether the + shows its icon.
FAB_JS = """() => { const b = document.querySelector('[data-screen="today"] .bottom');
  const add = b.querySelector('[data-act="add"]').getBoundingClientRect(), scan = b.querySelector('[data-act="scan"]').getBoundingClientRect();
  return { box: [add.width, add.height], right: document.documentElement.clientWidth - add.right, gap: add.left - scan.right,
           scanLeft: scan.left, icon: !!b.querySelector('[data-act="add"] svg'), text: b.querySelector('[data-act="add"]').textContent.trim() }; }"""
FAB_OK = lambda f: (f["box"] == [56, 56] and abs(f["right"] - 20) <= 0.5 and abs(f["gap"] - 10) <= 0.5  # noqa: E731
                    and f["scanLeft"] > 20 and f["icon"] and f["text"] == "")

# Corner names cut short (an ellipsis): the laid-out words wider than the box that shows them.
CUT_JS = """() => [...document.querySelectorAll('[data-screen="today"] .today-cn > span')].filter(s => {
  const r = document.createRange(); r.selectNodeContents(s);
  return r.getBoundingClientRect().width > s.getBoundingClientRect().width + 0.5;
}).map(s => s.textContent)"""

WAVES_JS = """() => [...document.querySelectorAll('[data-screen="today"] .today-wave')].map(w => {
  const s = getComputedStyle(w); return [s.animationName, s.animationPlayState];
})"""


def imported():
    """The fixture as the import tool turns it into a Pantry document."""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / "pantry-data.json"
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "import_mynetdiary.py"),
                           str(ROOT / "tests" / "fixtures" / "mynetdiary-slice.json"), "-o", str(out)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    if done.returncode != 0:
        raise SystemExit(f"tools/import_mynetdiary.py failed ({done.returncode}): {done.stdout}{done.stderr}")
    return json.loads(out.read_text(encoding="utf-8"))


def fixture_days():
    """kcal per meal and macro grams per day, straight from the MyNetDiary fixture."""
    src = json.loads((ROOT / "tests" / "fixtures" / "mynetdiary-slice.json").read_text(encoding="utf-8"))
    days = {}
    for day in src["days"]:
        d = days.setdefault(day["date"], {"meals": dict.fromkeys(MEALS, 0.0), "p": 0.0, "c": 0.0, "f": 0.0})
        for e in day["entries"]:
            d["meals"][e["meal"].lower()] += e["kcal"]
            d["p"] += e["nutrients"]["protein"]
            d["c"] += e["nutrients"]["totalCarbs"]
            d["f"] += e["nutrients"]["totalFat"]
    return days


def end_to_end(kcals):
    """The ring rule worked by hand (Blueprint, 2026-10-21): each logged meal's arc is kcal / budget x 360 degrees, end
    to end in meal order from 12 o'clock; the ring stops at a full turn."""
    end, out = 0.0, {}
    for meal, k in zip(MEALS, kcals):
        if k and end < 360:
            s, end = end, min(360.0, end + k / BUDGET * 360)
            out[meal] = (s, end)
    return out


def near(got, want, tol=0.5):
    """Two {meal: (start, end)} maps alike within tol degrees."""
    return set(got) == set(want) and all(abs(got[m][0] - want[m][0]) <= tol and abs(got[m][1] - want[m][1]) <= tol for m in want)


def show(page, date=None):
    page.evaluate("d => Pantry.go('today', d)", date)
    page.wait_for_selector(f"{SCREEN} .today-frame")


def goto_hash(page, hash_):
    """Set the address by hand, as a typed or bookmarked link would, and wait until the screen has been redrawn."""
    page.evaluate("""h => new Promise(done => {
        addEventListener('hashchange', () => setTimeout(done, 0), { once: true }); location.hash = h; })""", hash_)


def text(page, selector):
    return page.evaluate(TEXT, f"{SCREEN} {selector}")


def texts(page, selector):
    return page.evaluate(TEXTS, f"{SCREEN} {selector}")


def tap_goes(page, selector, back_to):
    """Tap one control, read where Pantry.go sent the address, then come back to Today for back_to."""
    before = page.evaluate("location.hash")
    page.locator(f"{SCREEN} {selector}").first.click()
    page.wait_for_function("h => location.hash !== h", arg=before)
    went = page.evaluate("location.hash")
    show(page, back_to)
    return went


def strip_still(page, ms=4000):
    """Waits until the strip's scroll has stopped: a flick or a smooth scroll runs on the browser's own clock."""
    last, same = None, 0
    for _ in range(ms // 50):
        x = page.evaluate("() => document.querySelector('[data-screen=\"today\"] .today-days').scrollLeft")
        same = same + 1 if x == last else 0
        if same >= 4:
            return True
        last = x
        page.wait_for_timeout(50)
    return False


def short_day(day):
    return f"{int(day[8:])} {datetime.date.fromisoformat(day).strftime('%b')}"


def swipe(page, x0, x1, y):
    """A finger dragged across the screen (real touch events through the DevTools protocol)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y}]})
    for i in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 10, "y": y}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    page.wait_for_timeout(50)


def clear(page, name):
    r = page.evaluate(CLEAR_JS)
    check(f"{name}: the corner names and kcal stay off the ring's box, the drawings off the ring, corners apart",
          r["corners"] == 4 and not r["words"] and not r["art"] and not r["meet"], r)


def centre(page, name, roomy):
    r = page.evaluate(CENTER_JS)
    lines = r["lines"]
    check(f"{name}: '{lines[0][0] if lines else None}', its words and eaten / budget sit inside the ring's inner edge",
          len(lines) == 3 and all(far <= r["inner"] + 0.5 for _, far, _ in lines),
          {"inner": round(r["inner"], 1), "lines": [[t, round(far, 1), size] for t, far, size in lines]})
    check(f"{name}: the kcal-left number stays at least twice the size of the words under it",
          len(lines) == 3 and lines[0][2] >= 2 * lines[1][2] - 0.01, lines)
    if roomy:
        check(f"{name}: with room for it, the centre keeps the design's sizes (2.75rem number, 0.75rem words)",
              len(lines) == 3 and abs(lines[0][2] - 2.75 * r["rem"]) < 0.01
              and all(abs(size - 0.75 * r["rem"]) < 0.01 for _, _, size in lines[1:]), (r["rem"], lines))


def strip_days(page):
    return [d["day"] for d in page.evaluate(STRIP_JS)]


def check_day(page, days):
    aug8 = days["2026-08-08"]
    show(page, "2026-08-08")
    check("Today for 8 Aug: 224 kcal left, 1,976 / 2,200",
          text(page, '[data-test="kcal-left"]') == "224" and text(page, ".today-lbl") == "kcal left"
          and text(page, ".today-tot") == "1,976 / 2,200", (text(page, '[data-test="kcal-left"]'), text(page, ".today-tot")))
    corners = page.evaluate("""() => [...document.querySelectorAll('[data-screen="today"] .today-corner')]
        .map(c => [c.dataset.meal, (c.querySelector('.today-ck') || {}).textContent])""")
    want = [[m, f"{round(aug8['meals'][m]):,}"] for m in MEALS]
    check("the corners show 888, 350, 590, 148 for breakfast, lunch, dinner, snacks", corners == want, corners)
    boxes = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('[data-screen="today"] .today-corner')]
        .map(c => { const r = c.getBoundingClientRect(); return [c.dataset.meal, [r.left, r.top]]; }))""")
    check("Breakfast sits top left, Lunch top right, Dinner bottom right, Snacks bottom left",
          boxes["breakfast"][0] < boxes["lunch"][0] and boxes["snacks"][0] < boxes["dinner"][0]
          and boxes["breakfast"][1] < boxes["snacks"][1] and boxes["lunch"][1] < boxes["dinner"][1], boxes)
    kc = [aug8["c"] * 4, aug8["p"] * 4, aug8["f"] * 9]
    shares = [k / sum(kc) * 100 for k in kc]
    pcts = texts(page, ".today-pct")
    check("the macro strip reads 36 / 50 / 15 % for carbs, protein, fat", pcts == ["36%", "50%", "15%"]
          and [f"{round(s)}%" for s in shares] == pcts, pcts)
    widths = page.evaluate("() => [...document.querySelectorAll('[data-screen=\"today\"] .today-bar')].map(b => b.getBoundingClientRect().width)")
    got = [w / sum(widths) * 100 for w in widths]
    check("each macro bar's width is its share of carbs x 4 + protein x 4 + fat x 9 (within 1 point)",
          len(got) == 3 and all(abs(g - s) <= 1.0 for g, s in zip(got, shares)), (got, shares))
    grams = texts(page, ".today-g")
    check("under each bar: grams eaten against the target from 45 / 20 / 35 % of 2,200",
          grams == ["186 / 248 g", "258 / 110 g", "34 / 86 g"] and text(page, ".today-fig") == "target 45 / 20 / 35%", grams)
    names = [n.split(" ")[0] for n in texts(page, ".today-lab")]
    label = page.evaluate("() => document.querySelector('[data-screen=\"today\"] .today-mac').getAttribute('aria-label')")
    check("the macros read carbs, protein, fat: the labels, the targets and the strip's spoken name (Pantry.MACROS)",
          names == ["Carbs", "Protein", "Fat"] and label == "Calories from carbs, protein and fat"
          and page.evaluate("Pantry.MACROS.join()") == "carbs,protein,fat", (names, label))
    add_name = lambda: page.locator(f'{SCREEN} [data-act="add"]').get_attribute("aria-label")  # noqa: E731
    eaten = page.evaluate("() => document.querySelector('[data-screen=\"today\"] .today-eaten').getAttribute('aria-label')")
    check("a past day: eyebrow 'Saturday, 8 August', title '8 Aug', 'Eaten that day'; it opens on its first meal with "
          "entries, so the + is 'Add food to breakfast'",
          text(page, ".top .eyebrow") == "Saturday, 8 August" and text(page, "h1") == "8 Aug"
          and eaten == "Eaten that day" and add_name() == "Add food to breakfast",
          (text(page, ".top .eyebrow"), text(page, "h1"), eaten, add_name()))
    pages = page.evaluate("""() => [...document.querySelectorAll('[data-screen="today"] .today-pg')]
        .map(p => [p.dataset.pg, [...p.querySelectorAll('.fr .sub')].map(s => s.textContent)])""")
    check("a past day has one page per meal, in meal order, each with its own rows",
          pages == [["breakfast", ["Breakfast, 3 pieces"]], ["lunch", ["Lunch, 1 servings"]], ["dinner", ["Dinner, 1000 g"]],
                    ["snacks", ["Snacks, 1.5 slices"]]], pages)
    A.rows_single_line(page, "Today, 8 Aug")


def ring_state(page):
    """The drawn ring: {meal: (start, end)}, the track pieces, whether the frame is over, the letters on the ring."""
    return {"arcs": page.evaluate(ARCS_JS), "tracks": page.evaluate(TRACKS_JS), "laps": page.evaluate(LAP_JS)["laps"],
            "over": page.evaluate("() => document.querySelector('[data-screen=\"today\"] .today-frame').classList.contains('today-over')"),
            "letters": page.evaluate("() => [...document.querySelectorAll('[data-screen=\"today\"] .today-ring span')].filter(s => /^[BLDS]$/.test(s.textContent.trim())).length")}


# The tone of each drawn arc in drawn order (meal order is drawn order) and of each corner badge, as sRGB.
TONE_JS = """() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const g = cv.getContext('2d', { willReadFrequently: true });
  const rgb = c => { g.clearRect(0, 0, 1, 1); g.fillStyle = c; g.fillRect(0, 0, 1, 1); return [...g.getImageData(0, 0, 1, 1).data].slice(0, 3); };
  const s = document.querySelector('[data-screen="today"]');
  return { arcs: [...s.querySelectorAll('.today-seg')].map(p => [p.dataset.meal, rgb(getComputedStyle(p).stroke)]),
           badges: Object.fromEntries([...s.querySelectorAll('.today-corner')].map(c =>
             [c.dataset.meal, rgb(getComputedStyle(c.querySelector('.today-sw')).backgroundColor)])) }; }"""


def tones_ok(t):
    """Arcs side by side differ in tone and every other one shares it (dark, light, dark: OKLab distance), each corner
    badge has its own arc's tone, and a badge with no arc the light one (the second arc's)."""
    arcs, badges = t["arcs"], t["badges"]
    drawn = dict(arcs)
    alternate = (all(delta(a[1], b[1]) > 0.1 for a, b in zip(arcs, arcs[1:]))
                 and all(delta(a[1], c[1]) < 0.01 for a, c in zip(arcs, arcs[2:])))
    own = all(delta(badges[m], c) < 0.01 for m, c in arcs)
    rest = len(arcs) < 2 or all(delta(c, arcs[1][1]) < 0.01 for m, c in badges.items() if m not in drawn)
    return alternate and own and rest


def whole_ring(r, want):
    """The arcs are `want`, end to end with no overlap, and the rest is one unbroken track from the last end to the top."""
    arcs, last = r["arcs"], max(e for _, e in want.values())
    order = sorted(arcs.values())
    return (near(arcs, want) and all(a[1] <= c[0] + 0.01 for a, c in zip(order, order[1:]))
            and len(r["tracks"]) == 1 and not r["tracks"][0][0] and abs(r["tracks"][0][1] - last) <= 0.5
            and abs(r["tracks"][0][2] - 360) <= 0.5 and not r["over"])


def check_ring(page, days):
    show(page, "2026-08-08")
    want = end_to_end([days["2026-08-08"]["meals"][m] for m in MEALS])
    r = ring_state(page)
    check("8 Aug ring, measured from the drawn arcs: breakfast 0..145, lunch ..203, dinner ..299, snacks ..323 end to end "
          "from 12 o'clock, then one track back to the top (0.5 deg)",
          abs(want["snacks"][1] - 323.3) < 0.5 and whole_ring(r, want), (want, r))
    check("the ring carries no meal letters (the corner badges do)", r["letters"] == 0
          and texts(page, ".today-sw") == ["B", "L", "D", "S"], (r["letters"], texts(page, ".today-sw")))

    show(page, "2026-10-19")
    r = ring_state(page)
    want = end_to_end([days["2026-10-19"]["meals"][m] for m in MEALS])
    closed = lambda r: len(r["tracks"]) == 1 and r["tracks"][0][0] and abs(r["tracks"][0][2] - r["tracks"][0][1] - 360) <= 0.5  # noqa: E731
    check("19 Oct is 92 over: breakfast 0..161.7 and dinner on from it, stopped at the top; a closed track in the over tint "
          "under them; the centre says '92 kcal over'",
          near(r["arcs"], want) and abs(want["breakfast"][1] - 161.7) < 0.1 and abs(want["dinner"][1] - 360) < 0.01 and r["over"]
          and closed(r) and text(page, '[data-test="kcal-left"]') == "92" and text(page, ".today-lbl") == "kcal over", r)
    check("19 Oct's 92 over runs on as a second lap from the top: 0..15.1 deg (92 / 2,200 of a turn)",
          len(r["laps"]) == 1 and abs(r["laps"][0][0]) <= 0.5 and abs(r["laps"][0][1] - 92 / BUDGET * 360) <= 0.5, r["laps"])
    tones = page.evaluate(TONE_JS)
    check("19 Oct (breakfast and dinner, lunch skipped): the two arcs side by side are the full over tone and its light "
          "tint, never one tone cut by a gap; each corner badge has its arc's tone, the meals with no arc the light one",
          [m for m, _ in tones["arcs"]] == ["breakfast", "dinner"] and tones_ok(tones), tones)

    # breakfast alone, then dinner, then lunch logged after dinner (it moves dinner on), then over budget
    def log(entry_id, meal, kcal):
        page.evaluate("""([id, meal, kcal]) => Pantry.change(d => { d.entries.push(
            { id, date: '2026-07-01', meal, foodId: 'x', amount: '1', grams: null, totals: { kcal } }); })""", [entry_id, meal, kcal])
        until(page, "() => !document.querySelector('[data-screen=\"today\"]').dataset.motion")   # the change has landed
        return ring_state(page)
    show(page, "2026-07-01")
    empty = ring_state(page)
    check("nothing logged: no arc, the whole ring one track", empty["arcs"] == {} and len(empty["tracks"]) == 1
          and abs(empty["tracks"][0][1]) <= 0.5 and abs(empty["tracks"][0][2] - 360) <= 0.5, empty)
    only = log("tt-b", "breakfast", 300)
    check("only breakfast logged (300): one breakfast arc 0..49.1 and one unbroken track 49.1..360, no slot for lunch, dinner or snacks",
          whole_ring(only, end_to_end([300, 0, 0, 0])), only)
    two = log("tt-d", "dinner", 900)
    check("breakfast and dinner logged: two arcs end to end (dinner from 49.1 to 196.4) and one track",
          whole_ring(two, end_to_end([300, 0, 900, 0])), two)
    two_tones = page.evaluate(TONE_JS)
    check("breakfast and dinner within budget: dark then light grey side by side; each badge has its arc's tone, lunch's "
          "and snacks' the light one", [m for m, _ in two_tones["arcs"]] == ["breakfast", "dinner"] and tones_ok(two_tones), two_tones)
    three = log("tt-l", "lunch", 200)
    check("lunch logged after dinner takes its place in meal order and moves dinner's arc on (81.8..229.1); no overlap",
          whole_ring(three, end_to_end([300, 200, 900, 0])) and abs(three["arcs"]["dinner"][0] - 81.8) < 0.5, three)
    three_tones = page.evaluate(TONE_JS)
    check("lunch between them: breakfast dark, lunch light, dinner dark again (its arc and its badge change tone)",
          [m for m, _ in three_tones["arcs"]] == MEALS[:3] and tones_ok(three_tones)
          and delta(three_tones["badges"]["dinner"], two_tones["badges"]["dinner"]) > 0.1, three_tones)
    over = log("tt-s", "snacks", 1000)
    check("over budget (2,400): the arcs fill the ring and stop at the top, the track is the closed over-tint ring, the frame is over",
          near(over["arcs"], end_to_end([300, 200, 900, 1000])) and abs(over["arcs"]["snacks"][1] - 360) < 0.5 and over["over"]
          and closed(over), over)
    check_lap(page, log, two)
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => !e.id.startsWith('tt-')); })")


def check_lap(page, log, within):
    """Past the budget the ring runs on as a second lap from 12 o'clock (Tarik, 2026-10-21, MyNetDiary's 19 Oct):
    excess / budget x 360 degrees, a whole lap at most; within budget no lap, and the gap from the last arc's end to
    the top is what is left. The lap's red deepens with the excess, full `danger` from 25 % over (app/today.js HOT).
    The page holds 2,400 kcal on 1 Jul (300 + 200 + 900 + 1,000) when this runs."""
    left = (BUDGET - 1200) / BUDGET * 360
    check("within budget (1,200 of 2,200): no second lap, and the track from dinner's end to the top is the 1,000 left "
          "(196.4..360)", not within["laps"] and abs(within["tracks"][0][2] - within["tracks"][0][1] - left) <= 0.5, within)
    seen = {}
    for extra, total in ((0, 2400), (20, 2420), (330, 2750), (550, 3300), (1540, 4840)):
        if extra:
            log(f"tt-x{total}", "snacks", extra)
        seen[total] = page.evaluate(LAP_JS)
    want = lambda total: min(360.0, (total - BUDGET) / BUDGET * 360)  # noqa: E731
    ok = {t: len(r["laps"]) == 1 and abs(r["laps"][0][0]) <= 0.5 and abs(r["laps"][0][1] - want(t)) <= 0.5 for t, r in seen.items()}
    check("over budget a second lap runs from 12 o'clock over the full ring: 200 over is 32.7 deg, 220 over (10 %) 36, "
          "1,100 over (50 %) 180, 2,640 over (more than a lap) a whole lap and no more", all(ok.values()),
          {t: r["laps"] for t, r in seen.items()})
    far = {t: delta(r["tone"], r["canvas"]) for t, r in seen.items() if r["tone"]}
    check("the lap's red deepens with the excess: lighter at 10 % over than at 50 %, the full danger red from 25 % over "
          "(OKLab distance from the canvas, and from danger)",
          len(far) == len(seen) and far[2420] + 0.03 < far[3300] and delta(seen[2750]["tone"], seen[2750]["danger"]) < 0.01
          and delta(seen[3300]["tone"], seen[3300]["danger"]) < 0.01 and delta(seen[2420]["tone"], seen[2420]["danger"]) > 0.03,
          {t: (r["tone"], round(far.get(t, -1), 3)) for t, r in seen.items()})
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => !e.id.startsWith('tt-x')); })")
    until(page, "() => !document.querySelector('[data-screen=\"today\"]').dataset.motion")


def check_strip(page, url):
    show(page, "2026-08-08")
    strip = page.evaluate(STRIP_JS)
    days = [f"2026-08-0{i}" for i in range(2, 9)]
    check("the strip shows the seven days ending at the shown day (2 to 8 Aug, local dates)",
          [d["day"] for d in strip] == days and [d["num"] for d in strip] == [str(i) for i in range(2, 9)]
          and [d["name"] for d in strip] == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], strip)
    empty = strip[:6]
    check("a day with no entries has an empty tank labelled '−2,200'",
          all(d["fill"] == 0 and d["label"] == "−2,200" and not d["over"] for d in empty), empty)
    check("8 Aug is filled to 1,976 / 2,750 of its tank, labelled '−224', marked as the shown day",
          abs(strip[6]["fill"] - 1976 / 2750) <= 0.02 and strip[6]["label"] == "−224" and strip[6]["on"], strip[6])

    show(page)
    strip = page.evaluate(STRIP_JS)
    by = {d["day"]: d for d in strip}
    check("on Today the strip ends at 20 Oct (the Darwin date, not the UTC one) labelled 'today'",
          [d["day"] for d in strip][-1] == "2026-10-20" and by["2026-10-20"]["label"] == "today" and by["2026-10-20"]["on"], strip)
    check("19 Oct, over budget, is labelled '+92' and marked; its fill is 2,292 / 2,750",
          by["2026-10-19"]["label"] == "+92" and by["2026-10-19"]["over"] and abs(by["2026-10-19"]["fill"] - 2292 / 2750) <= 0.02
          and not by["2026-10-20"]["over"] and abs(by["2026-10-20"]["fill"] - 1304 / 2750) <= 0.02, by["2026-10-19"])
    check("no other day in the strip is marked over", [d["day"] for d in strip if d["over"]] == ["2026-10-19"], strip)

    page.evaluate("() => Pantry.change(d => { d.settings.targets.kcal = 2400; })")
    by = {d["day"]: d for d in page.evaluate(STRIP_JS)}
    check("with a 2,400 budget the strip's scale is 1.25 x 2,400 = 3,000 and 19 Oct reads '−108', not over",
          abs(by["2026-10-19"]["fill"] - 2292 / 3000) <= 0.02 and by["2026-10-19"]["label"] == "−108" and not by["2026-10-19"]["over"],
          by["2026-10-19"])
    page.evaluate("() => Pantry.change(d => { d.settings.targets.kcal = 2200; })")

    # tap a day; swipe a week either way without changing the shown day
    show(page, "2026-08-08")
    page.locator(f'{SCREEN} .today-day[data-day="2026-08-05"]').click()
    check("tapping 5 Aug in the strip shows that day in place (the address stays #/today/2026-08-08)",
          text(page, "h1") == "5 Aug" and page.evaluate("location.hash") == "#/today/2026-08-08", (text(page, "h1"), page.evaluate("location.hash")))
    page.evaluate("Pantry.go('today', '2026-08-05')")
    page.wait_for_selector(f"{SCREEN} .today-frame")
    strip_still(page)
    check("the opened day's strip shows it", "2026-08-05" in strip_days(page) and text(page, "h1") == "5 Aug", strip_days(page))

    show(page, "2026-08-08")
    strip_still(page)
    box = page.locator(f"{SCREEN} .today-days").bounding_box()
    y = box["y"] + box["height"] / 2
    hash_before = page.evaluate("location.hash")
    before = strip_days(page)
    swipe(page, box["x"] + 60, box["x"] + box["width"] - 30, y)
    strip_still(page)
    earlier = strip_days(page)
    swipe(page, box["x"] + box["width"] - 30, box["x"] + 60, y)
    strip_still(page)
    later = strip_days(page)
    check("the strip scrolls under the finger, day by day: a swipe right shows earlier days, a swipe left later ones, "
          "seven whole days in view when it stops, the shown day stays 8 Aug",
          "2026-08-08" in before and earlier[-1] < before[-1] and later[-1] > earlier[-1] and len(earlier) == len(later) == 7
          and text(page, "h1") == "8 Aug" and page.evaluate("location.hash") == hash_before, (before, earlier, later))
    show(page, "2026-10-19")
    strip_still(page)
    swipe(page, box["x"] + box["width"] - 30, box["x"] + 60, y)
    strip_still(page)
    check("the strip never runs past today: a swipe left from 19 Oct stops at 20 Oct", strip_days(page)[-1] == "2026-10-20", strip_days(page))
    first_js = "() => document.querySelector('[data-screen=\"today\"] .today-days .today-day').dataset.day"
    first = page.evaluate(first_js)
    page.evaluate("() => { document.querySelector('[data-screen=\"today\"] .today-days').scrollLeft = 0; }")
    strip_still(page)
    seen = strip_days(page)
    page.wait_for_timeout(300)
    check("scrolled to its start the strip takes about three months more days, and the days in view stay in view",
          page.evaluate(first_js) < first and strip_days(page) == seen and seen[0] < "2026-07-25", (first, page.evaluate(first_js), seen))
    page.wait_for_timeout(450)                 # a tap right after a swipe is the swipe's own touch ending, so it is ignored
    page.locator(f'{SCREEN} .today-day[data-day="2026-10-20"]').click()
    check("tapping today in the strip shows Today in place, which follows the clock (state.day null, no date)",
          text(page, "h1") == "Today" and page.evaluate("'day' in history.state && history.state.day === null")
          and page.evaluate("location.hash") == "#/today/2026-10-19", (text(page, "h1"), page.evaluate("history.state")))


def check_waves(page):
    show(page)
    waves = page.evaluate(WAVES_JS)
    filled = page.locator(f"{SCREEN} .today-liq").count()   # every filled day in the strip, in view or scrolled
    check("with reduced motion off, every filled day's wave runs a CSS animation",
          waves and len(waves) == filled and all(n != "none" and s == "running" for n, s in waves), waves)
    page.emulate_media(reduced_motion="reduce")
    waves = page.evaluate(WAVES_JS)
    check("with prefers-reduced-motion: reduce, no wave animates", waves and all(n == "none" for n, _ in waves), waves)
    page.emulate_media(reduced_motion="no-preference")


def check_routes(page):
    show(page, "2026-08-08")
    got = {m: tap_goes(page, f'.today-corner[data-meal="{m}"]', "2026-08-08") for m in MEALS}
    check("tapping each corner opens that meal's list for the shown day (add <meal> 2026-08-08)",
          got == {m: f"#/add/{m}/2026-08-08" for m in MEALS}, got)
    went = {
        "add": tap_goes(page, '[data-act="add"]', "2026-08-08"),
        "scan": tap_goes(page, '[data-act="scan"]', "2026-08-08"),
        "row": tap_goes(page, ".fr", "2026-08-08"),
        "gear": tap_goes(page, '[data-act="settings"]', "2026-08-08"),
    }
    want = {"add": "#/add/breakfast/2026-08-08", "scan": "#/scan/breakfast/2026-08-08", "row": "#/entry/2026-08-08-102", "gear": "#/settings"}
    check("on a past day shown on its breakfast page, the + opens add breakfast <date>, Scan scan breakfast <date>, a row entry <id>, the gear settings",
          went == want, went)
    page.locator(f'{SCREEN} .today-tab[data-page="dinner"]').click()
    until(page, "() => document.querySelector('[data-act=\"add\"]').dataset.for === 'dinner'")
    named = page.locator(f'{SCREEN} [data-act="add"]').get_attribute("aria-label")
    went = [tap_goes(page, '[data-act="add"]', "2026-08-08"), tap_goes(page, '[data-act="scan"]', "2026-08-08")]
    check("on the dinner page the + is 'Add food to dinner' and the + and Scan open add dinner and scan dinner for the day "
          "(the page shown, kept on the way back)",
          named == "Add food to dinner" and went == ["#/add/dinner/2026-08-08", "#/scan/dinner/2026-08-08"], (named, went))
    show(page)
    named = page.locator(f'{SCREEN} [data-act="add"]').get_attribute("aria-label")
    check("on Today at 07:00 the + is 'Add food to breakfast' and is found as 'Add food'",
          named == "Add food to breakfast" and page.get_by_role("button", name="Add food").count() == 1
          and page.get_by_role("button", name="Scan a barcode").count() == 1, named)
    went = [tap_goes(page, '[data-act="add"]', None), tap_goes(page, '.today-corner[data-meal="lunch"]', None)]
    check("on Today the bottom button opens add breakfast 2026-10-20 and the Lunch corner add lunch 2026-10-20",
          went == ["#/add/breakfast/2026-10-20", "#/add/lunch/2026-10-20"], went)


def check_live(page):
    show(page)
    food = page.evaluate("Pantry.doc().foods[0].id")
    seen = page.evaluate("""f => {
        const sub = () => { const s = document.querySelector('[data-screen="today"] .today-pg[data-pg="lunch"] .fr .sub'); return s ? s.textContent : null; };
        const read = () => [document.querySelector('[data-test="kcal-left"]').textContent,
                            (document.querySelector('.today-corner[data-meal="lunch"] .today-ck') || {}).textContent || null,
                            sub(), document.querySelector('.today-tab[data-page="lunch"] b').textContent];
        const before = read();
        Pantry.change(d => { d.entries.push({ id: 'tt-live', date: Pantry.today(), meal: 'lunch', foodId: f, amount: '1 g', grams: 1, totals: { kcal: 500 } }); });
        const added = read();
        Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'tt-live'); });
        return [before, added, read()];
    }""", food)
    check("an entry added or removed shows in the same frame: kcal left, the corner, the lunch page's row and its tab's kcal",
          seen[0] == ["896", None, None, ""] and seen[1] == ["396", "500", "Lunch, 1 g", "500"] and seen[2] == ["896", None, None, ""], seen)


def check_midnight(page):
    goto_hash(page, "#/today/2026-10-20")
    title = text(page, "h1")
    page.clock.set_fixed_time(datetime.datetime(2026, 10, 21, 0, 0, 30, tzinfo=A.DARWIN))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    strip = page.evaluate(STRIP_JS)
    check("at midnight Darwin time Today turns to Wednesday, 21 October: 2,200 left, the strip ends at the new today",
          title == "Today" and text(page, ".top .eyebrow") == "Wednesday, 21 October" and text(page, "h1") == "Today"
          and text(page, '[data-test="kcal-left"]') == "2,200" and strip[-1]["day"] == "2026-10-21" and strip[-1]["label"] == "today"
          and strip[-2]["label"] == "−896", (title, text(page, ".top .eyebrow"), strip[-2:]))
    page.clock.set_fixed_time(A.NOW)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")


def check_meal_clock(page):
    show(page)
    page.clock.set_fixed_time(datetime.datetime(2026, 10, 20, 12, 0, 0, tzinfo=A.DARWIN))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    label = page.locator(f'{SCREEN} [data-act="add"]').get_attribute("aria-label")
    went = [tap_goes(page, '[data-act="add"]', None), tap_goes(page, '[data-act="scan"]', None)]
    page.clock.set_fixed_time(A.NOW)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    check("Today left open from 07:00 to 12:00: the + becomes 'Add food to lunch' and Add and Scan open lunch",
          label == "Add food to lunch" and went == ["#/add/lunch/2026-10-20", "#/scan/lunch/2026-10-20"], (label, went))


def check_banner(page):
    show(page)
    sentence = "Sync failed. Saved on this phone; it will try again. The GitHub token may have expired: Settings, Sync."
    shown = page.evaluate("""s => { Pantry.setSyncState({ lastError: s });
        return [...document.querySelectorAll('[data-screen="today"] .banner')].map(b => [b.textContent.trim(), (b.querySelector('b') || {}).textContent]); }""", sentence)
    gone = page.evaluate("""() => { Pantry.setSyncState({ lastError: null });
        return document.querySelectorAll('[data-screen="today"] .banner').length; }""")
    check("with lastError set Today shows one banner with its sentence (redrawn on 'sync'); cleared, it goes",
          len(shown) == 1 and shown[0][0] == sentence and shown[0][1] == "Sync failed." and gone == 0, (shown, gone))


def check_dates(page):
    for bad in ("2026-02-30", "yesterday", "2026-8-8"):
        goto_hash(page, f"#/today/{bad}")
        ok = text(page, "h1") == "Today" and text(page, ".top .eyebrow") == "Tuesday, 20 October"
        if not check(f"a date argument that is not a real YYYY-MM-DD ({bad}) shows today", ok, text(page, "h1")):
            break
    show(page, "2025-08-08")
    check("a day in another year names its year: 'Friday, 8 August 2025'", text(page, ".top .eyebrow") == "Friday, 8 August 2025",
          text(page, ".top .eyebrow"))


def check_fit(browser, url, doc, errors):
    # 200 % is the largest font the terra_nt eye check uses; 240 px with 150 % text is page zoom and big text together
    for name, size, scale in (("360 px, 150 % text", (360, 780), 1.5), ("360 px, 100 % text", (360, 780), 1.0), ("240 px", (240, 520), 1.0),
                              ("360 px, 200 % text", (360, 780), 2.0), ("240 px, 150 % text", (240, 520), 1.5)):
        ctx, page = A.phone(browser, errors, f"today-fit-{size[0]}-{scale}", text=scale)
        page.set_viewport_size({"width": size[0], "height": size[1]})
        A.open_today(page, url)
        page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
        for date in ("2026-08-08", "2026-10-19", None):
            page.goto(url + (f"#/today/{date}" if date else "#/"))
            page.reload()
            page.wait_for_selector(f"{SCREEN} .today-frame")
            page.evaluate("document.fonts.ready")
            label = f"Today {date or '20 Oct'}, {name}"
            A.fits(page, label)
            clear(page, label)
            centre(page, label, size[0] == 360 and scale <= 1.5)
            strip = page.evaluate(STRIP_JS)
            check(f"{label}: every day name, date and label in the day strip fits its day", all(d["wordsFit"] for d in strip), strip)
            macro = page.evaluate(MACRO_JS)
            check(f"{label}: each macro percentage shows once, inside its bar or under it when the bar is too narrow",
                  len(macro) == 3 and all(m["inside"] != m["shownUnder"] and m["under"] == m["pct"] for m in macro), macro)
            labs = page.evaluate(LABELS_JS)
            ink, bars, sep = labs["labels"], labs["bars"], labs["sep"]
            gaps = [round(b["left"] - a["right"], 1) for a, b in zip(ink, ink[1:])]
            over = [[max(0, min(lab["right"], bar[1]) - max(lab["left"], bar[0])) for bar in bars] for lab in ink]
            check(f"{label}: the macro labels stay one em (0.75rem) apart, each sits mostly under its own bar, none leaves the row",
                  len(ink) == 3 and all(g >= sep - 0.5 for g in gaps)
                  and all(o.index(max(o)) == i for i, o in enumerate(over))
                  and all(lab["left"] >= labs["row"][0] - 0.5 and lab["right"] <= labs["row"][1] + 0.5 for lab in ink),
                  {"gaps": gaps, "sep": sep, "labels": [[round(lab["left"], 1), round(lab["right"], 1)] for lab in ink], "bars": bars})
            if scale == 1.0 and size[0] == 360:
                check(f"{label}: as drawn, each macro label is one line of name and one of grams, starting where its bar starts",
                      all(lab["lines"] == 2 and abs(lab["left"] - bar[0]) <= 4.5 for lab, bar in zip(ink, bars)), ink)
            fab = page.evaluate(FAB_JS)
            check(f"{label}: the + (56 px) floats 20 px from the right edge with Scan 10 px to its left", FAB_OK(fab), fab)
            cut = page.evaluate(CUT_JS)
            check(f"{label}: every corner name shows whole, none cut short", not cut, cut)
        # nothing logged yet (every morning): the widest centre, 2,200 left
        page.goto(url + "#/today/2026-10-18")
        page.reload()
        page.wait_for_selector(f"{SCREEN} .today-frame")
        page.evaluate("document.fonts.ready")
        label = f"Today 2026-10-18 (nothing logged), {name}"
        A.fits(page, label)
        clear(page, label)
        centre(page, label, size[0] == 360 and scale <= 1.5)
        ctx.close()


def check_text_and_theme(page, url):
    show(page, "2026-08-08")
    A.set_text(page, 1.0)
    A.reload_to(page, "today")
    page.evaluate("document.fonts.ready")
    small = page.evaluate(A.TEXT_SIZES_JS)
    A.set_text(page, A.BIG_TEXT)
    A.reload_to(page, "today")
    page.evaluate("document.fonts.ready")
    big = page.evaluate(A.TEXT_SIZES_JS)
    flat = [a[0] for a, b in zip(small, big) if b[1] < 1.45 * a[1]]
    names = [a[0] for a in small]
    check("every text on Today for 8 Aug grows with the text size, the corner badges' letters and the meal tabs included (rem only)",
          len(small) == len(big) and small and not flat and sum(1 for n in names if n in ("i:B", "i:L", "i:D", "i:S")) == 4
          and sum(1 for n in names if n in ("span:Breakfast", "span:Lunch", "span:Dinner", "span:Snacks")) >= 8,
          flat or (len(small), len(big), names[:12]))

    colours = {}
    for scheme in ("dark", "light"):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{scheme}'")
        page.wait_for_timeout(300)             # let the buttons' colour transition finish before the screenshot
        colours[scheme] = page.evaluate("() => { const s = getComputedStyle(document.body); return [s.backgroundColor, s.color]; }")
        page.screenshot(path=str(ROOT / ".tmp" / f"today-{scheme}.png"))
    check("in dark and in light the canvas and ink differ (screenshots: .tmp/today-dark.png, .tmp/today-light.png)",
          colours["dark"][0] != colours["light"][0] and colours["dark"][1] != colours["light"][1]
          and all(c[0] != c[1] for c in colours.values()), colours)
    page.emulate_media(color_scheme="light")


def check_first_launch(browser, url, errors):
    ctx, page = A.phone(browser, errors, "today-first")
    A.open_today(page, url)
    check("first launch: the empty plate, 2,200 kcal left, Import, and the 'Add food' and 'Scan a barcode' buttons",
          page.locator(f"{SCREEN} .today-empty").count() == 1 and text(page, ".today-empty h2") == "An empty plate."
          and text(page, '[data-test="kcal-left"]') == "2,200"
          and page.get_by_role("button", name="Import MyNetDiary history").count() == 1
          and page.get_by_role("button", name="Add food").count() == 1 and page.get_by_role("button", name="Scan a barcode").count() == 1
          and page.locator(f"{SCREEN} .today-frame").count() == 0, text(page, ".today-empty h2"))
    A.fits(page, "first launch, 150 % text")
    fab = page.evaluate(FAB_JS)
    check("first launch: the + floats 20 px from the right edge with Scan 10 px to its left", FAB_OK(fab), fab)
    page.locator(f'{SCREEN} [data-act="import"]').click()
    page.wait_for_function("location.hash === '#/settings'")
    check("Import MyNetDiary history opens settings", page.evaluate("location.hash") == "#/settings", page.evaluate("location.hash"))
    ctx.close()

    # an unreadable stored log and a sync error at once: one banner, the unreadable log's
    quiet = []                    # the unreadable log is reported on the console on purpose
    ctx, page = A.phone(browser, quiet, "today-unreadable")
    page.add_init_script("""if (!sessionStorage.getItem('t')) { sessionStorage.setItem('t', '1');
        localStorage.setItem('pantry.v1', '{"version": 1, "foods": "no"');
        localStorage.setItem('pantry.sync', JSON.stringify({ lastError: 'Sync failed. Saved on this phone; it will try again.' })); }""")
    A.open_today(page, url)
    banners = texts(page, ".banner")
    check("with an unreadable log and a sync error, Today shows one banner: the unreadable log's",
          len(banners) == 1 and "could not be read" in banners[0], banners)
    ctx.close()


# ── Task-09: budget status in colour, days switched in place, the ring swipe, what a change moves ──

def oklab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb[:3])
    l_, m_, s_ = ((0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3),
                  (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3),
                  (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def chroma(rgb):
    return math.hypot(*oklab(rgb)[1:])


def hue_gap(x, y):
    h = [math.degrees(math.atan2(c[2], c[1])) % 360 for c in (oklab(x), oklab(y))]
    return min(abs(h[0] - h[1]), 360 - abs(h[0] - h[1]))


def delta(x, y):
    return math.dist(oklab(x), oklab(y))


# Computed colours as sRGB, a translucent fill laid over what is under it (a day's tank over its cell), via a canvas.
TONES_JS = """() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const g = cv.getContext('2d', { willReadFrequently: true });
  const rgb = (c, under) => {
    g.clearRect(0, 0, 1, 1);
    if (under) { g.fillStyle = under; g.fillRect(0, 0, 1, 1); }
    g.fillStyle = '#010203'; g.fillStyle = c;
    if (g.fillStyle === '#010203') return null;
    g.fillRect(0, 0, 1, 1);
    return [...g.getImageData(0, 0, 1, 1).data].slice(0, 3);
  };
  const s = document.querySelector('[data-screen="today"]'), cs = el => getComputedStyle(el);
  const probe = v => { const p = document.createElement('i'); p.style.color = v; s.appendChild(p); const c = cs(p).color; p.remove(); return rgb(c); };
  const cells = Object.fromEntries([...s.querySelectorAll('.today-day')].map(d => {
    const liq = d.querySelector('.today-liq'), bg = cs(d).backgroundColor;
    return [d.dataset.day, { fill: liq ? rgb(cs(liq).backgroundColor, bg) : null, bg: rgb(bg), label: rgb(cs(d.querySelector('em')).color),
                             over: d.classList.contains('today-ov') }];
  }));
  const num = s.querySelector('.today-frame [data-test="kcal-left"]');
  const track = s.querySelector('.today-track');
  return { ring: [...s.querySelectorAll('.today-seg')].map(p => rgb(cs(p).stroke)), num: rgb(cs(num).color),
           sw: [...s.querySelectorAll('.today-sw')].map(e => rgb(cs(e).backgroundColor)),
           bars: [...s.querySelectorAll('.today-bar')].map(e => rgb(cs(e).backgroundColor)),
           track: track ? rgb(cs(track).stroke) : null,
           cells, accent: probe('var(--primary-display)'), danger: probe('var(--danger)'), violet: probe('var(--chart-5)'),
           canvas: probe('var(--canvas)'), grey: probe('var(--chart-neutral)'),
           words: [num.textContent, s.querySelector('.today-lbl').textContent] };
}"""

NEUTRAL, TONED = 0.02, 0.05      # OKLCH chroma: below is grey, above carries a hue


def check_status(browser, url, doc, errors):
    """Within budget the greys and the orange answer; over it the base danger red (Task-12, Tarik's pick over chart-5
    violet) on the ring, its badges, the number and the day's tank; a macro bar over its own target grams takes it too
    and the others share one grey; an empty day stays neutral.
    Synthetic days: 2,200.4 kcal (shown as 2,200: within), 2,200.6 (shown as 2,201: over by 1), 1,500, and nothing."""
    source = (ROOT / "app" / "today.js").read_text(encoding="utf-8")
    check("app/today.js names no chart-5: the over tone is var(--danger)", "chart-5" not in source
          and "--today-over: var(--danger)" in source, [ln for ln in source.splitlines() if "chart-5" in ln][:3])
    ctx, page = A.phone(browser, errors, "today-status", text=1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
    page.evaluate("""() => Pantry.change(d => { const f = d.foods[0].id; d.entries.push(
        { id: 'tt-s1', date: '2026-09-10', meal: 'breakfast', foodId: f, amount: '1', grams: null, totals: { kcal: 2200.4 } },
        { id: 'tt-s2', date: '2026-09-11', meal: 'breakfast', foodId: f, amount: '1', grams: null, totals: { kcal: 2200.6 } },
        { id: 'tt-s3', date: '2026-09-13', meal: 'lunch', foodId: f, amount: '1', grams: null, totals: { kcal: 1500 } }); })""")
    for scheme in ("dark", "light"):
        page.emulate_media(color_scheme=scheme)
        page.wait_for_function(f"document.documentElement.dataset.theme === '{scheme}'")
        show(page, "2026-09-10")
        within = page.evaluate(TONES_JS)
        show(page, "2026-09-11")
        over = page.evaluate(TONES_JS)
        page.screenshot(path=str(ROOT / ".tmp" / f"today-over-{scheme}.png"))
        A.fits(page, f"Today over budget, {scheme}, 360 px, text 1.0")
        tone, red, violet = over["num"], over["danger"], over["violet"]
        # over, the first lap's arcs and badges are light tints of the token (so the second lap, check_lap, reads on
        # top): the same hue, so they are measured by hue against danger and by distance from violet
        reddish = lambda c: chroma(c) >= TONED and hue_gap(c, red) <= 20 and delta(c, violet) > 0.1  # noqa: E731
        check(f"{scheme}: 2,200.4 kcal reads '0 kcal left' and stays within: the ring grey, the number the orange answer",
              within["words"] == ["0", "kcal left"] and within["ring"] and all(chroma(c) < NEUTRAL for c in within["ring"])
              and delta(within["num"], within["accent"]) < 0.01 and all(chroma(c) < NEUTRAL for c in within["sw"]),
              {"words": within["words"], "ring": within["ring"], "num": within["num"], "accent": within["accent"]})
        check(f"{scheme}: 2,200.6 kcal reads '1 kcal over': the number is var(--danger), the ring and its badges are light "
              "tints of it under the second lap, nothing is chart-5 violet",
              over["words"] == ["1", "kcal over"] and delta(tone, red) < 0.01 and over["ring"]
              and delta(over["ring"][0], red) > 0.05 and all(reddish(c) for c in over["ring"] + over["sw"])
              and over["track"] and chroma(over["track"]) >= 0.03 and hue_gap(over["track"], red) <= 20,
              {"words": over["words"], "num": tone, "ring": over["ring"], "sw": over["sw"], "track": over["track"], "danger": red})
        check(f"{scheme}: within and over differ on the ring and the badges",
              delta(within["ring"][0], over["ring"][0]) > 0.1 and delta(within["sw"][0], over["sw"][0]) > 0.1,
              (within["ring"][0], over["ring"][0], within["sw"][0], over["sw"][0]))
        shown_over = over["cells"]["2026-09-11"]
        check(f"{scheme}: the shown day over budget fills its tank in the danger tint, not the orange of the shown day",
              shown_over["over"] and shown_over["fill"] and reddish(shown_over["fill"]), shown_over)
        show(page, "2026-09-13")
        cells = page.evaluate(TONES_JS)["cells"]
        w, o, e = cells["2026-09-10"], cells["2026-09-11"], cells["2026-09-12"]
        check(f"{scheme}: in the strip a day within has a grey tank, a day over a tank in the over tone; they differ",
              not w["over"] and w["fill"] and chroma(w["fill"]) < NEUTRAL and o["over"] and o["fill"]
              and chroma(o["fill"]) >= TONED and hue_gap(o["fill"], tone) <= 20 and delta(w["fill"], o["fill"]) > 0.05, (w, o))
        check(f"{scheme}: a day with nothing logged stays neutral: no tank, a grey label, the cell as plain as the days around it",
              e["fill"] is None and not e["over"] and chroma(e["label"]) < NEUTRAL and e["bg"] == cells["2026-09-09"]["bg"]
              and chroma(e["bg"]) < NEUTRAL, e)
        show(page, "2026-08-08")
        aug = page.evaluate(TONES_JS)
        bars = aug["bars"]
        check(f"{scheme}: 8 Aug's protein (258 / 110 g) is over its target and is var(--danger); carbs (186 / 248) and fat "
              "(34 / 86) share one grey (chart-neutral)",
              len(bars) == 3 and delta(bars[1], red) < 0.01 and delta(bars[0], aug["grey"]) < 0.005 and delta(bars[2], aug["grey"]) < 0.005
              and chroma(bars[0]) < NEUTRAL, bars)
        show(page)
        bars = page.evaluate(TONES_JS)["bars"]
        check(f"{scheme}: 20 Oct (143 / 248, 67 / 110, 48 / 86 g: none past its target) draws its three bars in one grey",
              len(bars) == 3 and all(delta(b, aug["grey"]) < 0.005 for b in bars) and chroma(bars[0]) < NEUTRAL, bars)
        show(page, "2026-10-19")
        bars = page.evaluate(TONES_JS)["bars"]
        check(f"{scheme}: 19 Oct: protein (139 / 110 g) and fat (105 / 86 g) past their targets are danger, carbs (212 / 248) grey",
              len(bars) == 3 and delta(bars[0], aug["grey"]) < 0.005 and delta(bars[1], red) < 0.01 and delta(bars[2], red) < 0.01, bars)
        show(page, "2026-08-08")
        A.fits(page, f"Today 8 Aug, {scheme}, 360 px, text 1.0")
        page.screenshot(path=str(ROOT / ".tmp" / f"today-within-{scheme}.png"))
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => !e.id.startsWith('tt-s')); })")
    ctx.close()


def drag(page, points):
    """A finger along the points (real touch events through the DevTools protocol); returns once they are handled."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": points[0][0], "y": points[0][1]}]})
    for x, y in points[1:]:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


def centre_of(page, selector):
    box = page.locator(f"{SCREEN} {selector}").first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def ring_swipe(page, dx, start=".today-ring"):
    """dx < 0 is a swipe to the left. The finger moves across the middle of the start element."""
    x, y = centre_of(page, start)
    drag(page, [(x - dx / 2 + dx * i / 10, y) for i in range(11)])


def corner_flick(page):
    """A quick mouse flick to the left that starts and ends on the Lunch corner."""
    box = page.locator(f'{SCREEN} .today-corner[data-meal="lunch"]').bounding_box()
    x, y = box["x"] + box["width"] - 4, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 4):
        page.mouse.move(x - 10 * i, y)
    page.mouse.up()


def check_swipe(page):
    show(page, "2026-08-08")
    hash_ = page.evaluate("location.hash")
    ring_swipe(page, -120)
    left = (text(page, "h1"), text(page, ".top .eyebrow"), text(page, '[data-test="kcal-left"]'))
    ring_swipe(page, 120)
    ring_swipe(page, 120)
    right = (text(page, "h1"), text(page, ".top .eyebrow"))
    check("a left swipe on the ring opens the next day (9 Aug, its numbers), two right swipes the days before (7 Aug); the address stays",
          left == ("9 Aug", "Sunday, 9 August", "2,200") and right == ("7 Aug", "Friday, 7 August")
          and page.evaluate("location.hash") == hash_, (left, right, page.evaluate("location.hash")))

    corner_flick(page)
    check("a sideways flick that starts on a corner switches the day too (the corners are part of the ring's swipe)",
          text(page, "h1") == "8 Aug" and page.evaluate("location.hash") == hash_, (text(page, "h1"), page.evaluate("location.hash")))

    show(page)
    state, hash_ = page.evaluate("JSON.stringify(history.state)"), page.evaluate("location.hash")
    ring_swipe(page, -120)
    check("on Today a left swipe does nothing: there is no day after today",
          text(page, "h1") == "Today" and text(page, ".top .eyebrow") == "Tuesday, 20 October"
          and page.evaluate("JSON.stringify(history.state)") == state, (text(page, "h1"), page.evaluate("history.state"), state))
    corner_flick(page)
    check("the same flick on Today's corner, which has no next day to go to, does not open the meal: its click is part of the swipe",
          text(page, "h1") == "Today" and page.evaluate("location.hash") == hash_, (text(page, "h1"), page.evaluate("location.hash")))

    show(page, "2026-08-08")
    page.evaluate("window.scrollTo(0, 0)")
    room = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    x, y = centre_of(page, ".today-ring")
    drag(page, [(x, y - 240 * i / 10) for i in range(11)])
    until(page, "scrollY > 0")
    check("a vertical drag that starts on the ring scrolls the page and keeps the day",
          room > 0 and page.evaluate("scrollY") > 0 and text(page, "h1") == "8 Aug", (room, page.evaluate("scrollY"), text(page, "h1")))
    page.evaluate("window.scrollTo(0, 0)")
    # a thumb's arc: the first 7 px lean 65 degrees from vertical, then straight up. They end inside Chrome's touch slop
    # (8 dp on Android), where pan-y alone takes the scroll by the way the touch leans when it leaves the slop: up.
    lean = [(x + 1.75 * i * math.sin(math.radians(65)), y - 1.75 * i * math.cos(math.radians(65))) for i in range(5)]
    drag(page, lean + [(lean[-1][0], lean[-1][1] - 20 * i) for i in range(1, 11)])
    until(page, "scrollY > 0")
    check("a vertical drag on the ring whose first 7 px lean 65 degrees sideways, then go straight up, scrolls the page too",
          page.evaluate("scrollY") > 0 and text(page, "h1") == "8 Aug", (page.evaluate("scrollY"), text(page, "h1")))
    page.evaluate("window.scrollTo(0, 0)")


STRIP_BOX_JS = """() => [...document.querySelectorAll('[data-screen="today"] .today-day')]
  .map(d => [d.dataset.day, Math.round(d.getBoundingClientRect().left * 10) / 10])"""
BACK_TO_JS = "t => { const h = document.querySelector('[data-screen=\"today\"] h1'); return !!h && h.textContent === t; }"


def until(page, script, arg=None):
    """Wait (polling, at most 5 s) for a condition; False instead of an error, so the check that needs it says FAIL."""
    try:
        page.wait_for_function(script, arg=arg, timeout=5000)
        return True
    except PlaywrightTimeout:
        return False


def back_to(page, title):
    """The phone's back gesture: one step back in history, then wait for Today to show `title`; returns the title shown."""
    page.evaluate("history.back()")
    until(page, BACK_TO_JS, title)
    return text(page, "h1")


def check_in_place(page):
    show(page)
    depth, hash_, boxes = page.evaluate("history.state.depth"), page.evaluate("location.hash"), page.evaluate(STRIP_BOX_JS)
    seen = []
    for day in ("2026-10-19", "2026-10-17", "2026-10-15"):
        page.locator(f'{SCREEN} .today-day[data-day="{day}"]').click()
        seen.append([text(page, "h1"), page.evaluate(STRIP_BOX_JS) == boxes, page.evaluate("location.hash") == hash_])
    check("tapping 19, 17 and 15 Oct switches the day in place: the title follows, the strip and every day in it stay put, the address stays",
          [s[0] for s in seen] == ["19 Oct", "17 Oct", "15 Oct"] and all(s[1] and s[2] for s in seen), seen)
    check("three taps add one history entry, not three (history depth +1)", page.evaluate("history.state.depth") == depth + 1,
          (depth, page.evaluate("history.state")))
    check("pressing back once returns to the day shown before the first tap (Today)", back_to(page, "Today") == "Today"
          and not page.evaluate("'day' in (history.state || {})"), page.evaluate("history.state"))

    ring_swipe(page, 120)
    ring_swipe(page, 120)
    swiped = text(page, "h1")
    check("two right swipes on the ring (19, then 18 Oct) and back once: Today again",
          swiped == "18 Oct" and back_to(page, "Today") == "Today", swiped)

    show(page, "2026-08-08")
    page.locator(f'{SCREEN} .today-day[data-day="2026-08-05"]').click()
    action = page.locator(f'{SCREEN} [data-act="today"]')
    offered = action.count() == 1 and action.inner_text().strip() == "Today"
    action.click()
    strip_still(page)
    strip = strip_days(page)
    check("a past day offers Today, which switches to today in place: Today's numbers, the strip ends at 20 Oct, the address stays",
          offered and text(page, "h1") == "Today" and text(page, '[data-test="kcal-left"]') == "896" and strip[-1] == "2026-10-20"
          and page.evaluate("location.hash") == "#/today/2026-08-08" and page.locator(f'{SCREEN} [data-act="today"]').count() == 0,
          (offered, text(page, "h1"), strip, page.evaluate("location.hash")))
    check("... and back once returns to 8 Aug, the day the address opened", back_to(page, "8 Aug") == "8 Aug")

    show(page)
    page.locator(f'{SCREEN} .today-day[data-day="2026-10-19"]').click()
    page.locator(f'{SCREEN} [data-act="today"]').click()
    check("Today reached from Today's own day leaves no extra history: the entry of the switch is gone",
          text(page, "h1") == "Today" and not page.evaluate("'day' in (history.state || {})"), page.evaluate("history.state"))

    page.locator(f'{SCREEN} .today-day[data-day="2026-10-19"]').click()
    page.locator(f'{SCREEN} .today-corner[data-meal="dinner"]').click()
    until(page, "location.hash === '#/add/dinner/2026-10-19'")
    check("a day switched to in place comes back with Back from its meal list (19 Oct, not Today)", back_to(page, "19 Oct") == "19 Oct")
    page.reload()
    page.wait_for_selector(f"{SCREEN} .today-frame")
    check("a reload keeps the day switched to in place (its history entry holds it)",
          text(page, "h1") == "19 Oct" and page.evaluate("location.hash") == "#/today", (text(page, "h1"), page.evaluate("location.hash")))


def touch_tap(page, selector):
    """A finger tap (touch start and end through the DevTools protocol), as a phone taps: its click is Chrome's to make."""
    drag(page, [centre_of(page, selector)])


def strip_swipe(page, dx):
    """dx > 0: the finger moves right across the strip (the week before)."""
    box = page.locator(f"{SCREEN} .today-days").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    drag(page, [(x - dx / 2 + dx * i / 10, y) for i in range(11)])


def check_tap_after_swipe(browser, url, doc, errors):
    """A quick sideways swipe on the ring or the strip, then at once a tap: the tap gets its click. Chrome made a fling
    of such a swipe on a pan-y area, never showed it, and took the next tap as the one that stops it (no click)."""
    ctx, page = A.phone(browser, errors, "today-tap-after-swipe", text=1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
    show(page)
    ring_swipe(page, 120)
    swiped = until(page, BACK_TO_JS, "19 Oct")
    touch_tap(page, '[data-act="today"]')
    check("a right swipe on the ring to 19 Oct, then at once a finger tap on Today: Today again",
          swiped and until(page, BACK_TO_JS, "Today"), text(page, "h1"))
    ring_swipe(page, -120)
    still_today = text(page, "h1") == "Today"
    touch_tap(page, '.today-day[data-day="2026-10-16"]')
    check("a left swipe on Today's ring (no day after it, nothing redrawn), then at once a finger tap on 16 Oct: 16 Oct",
          still_today and until(page, BACK_TO_JS, "16 Oct"), text(page, "h1"))
    show(page)
    strip_still(page)
    # a drag held still before the finger lifts: headless Chromium never ends the fling a quick lift starts and takes
    # the next tap to stop it (the browser's own, checked on the phone, not here)
    box = page.locator(f"{SCREEN} .today-days").bounding_box()
    sx, sy = box["x"] + box["width"] / 2 - 80, box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": sx, "y": sy}]})
    for i in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": sx + 16 * i, "y": sy}]})
        page.wait_for_timeout(16)
    page.wait_for_timeout(200)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    moved = strip_still(page)
    day = strip_days(page)[0]
    touch_tap(page, f'.today-day[data-day="{day}"]')
    check("a swipe on the strip to earlier days, then a finger tap on the first day in view: that day",
          moved and day < "2026-10-14" and until(page, BACK_TO_JS, short_day(day)), (day, text(page, "h1")))
    ctx.close()


# The ring's frame offset
OFFSET_JS = """() => { const f = document.querySelector('[data-screen="today"] .today-frame');
  const m = f.style.transform.match(/translateX\\((-?[\\d.]+)px\\)/); return m ? Number(m[1]) : 0; }"""

def check_moving_edges(browser, url, doc, errors):
    """At 360 px and text 1.0, whatever Today moves sideways stays inside the screen: the ring held mid-drag either way,
    the ring coming in after a swipe, the strip held mid-drag (it scrolls inside itself). Page clock paused: the frames
    are read where they start, farthest out."""
    ctx = browser.new_context(**A.PHONE)
    ctx.clock.install(time=A.NOW)
    page = ctx.new_page()
    A.watch(page, errors, "today-edges")
    A.set_text(page, 1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
    page.clock.pause_at(A.NOW + datetime.timedelta(seconds=30))
    show(page, "2026-10-19")
    x, y = centre_of(page, ".today-ring")
    for sign, side in ((1, "right"), (-1, "left")):
        cdp = page.context.new_cdp_session(page)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        for i in range(1, 21):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x + sign * 10 * i, "y": y}]})
        held, fit = page.evaluate(OFFSET_JS), page.evaluate(A.FIT_JS)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchCancel", "touchPoints": []})
        cdp.detach()
        page.clock.run_for(1000)
        check(f"the ring held 200 px into a drag to the {side} follows the finger and stays inside the screen: no horizontal scroll",
              sign * held > 15 and fit["scroll"] <= 0 and not fit["bad"], (held, fit))
    for dx, day in ((-120, "Today"), (120, "19 Oct")):
        ring_swipe(page, dx)
        start, fit = page.evaluate(OFFSET_JS), page.evaluate(A.FIT_JS)
        page.clock.run_for(1000)
        check(f"the ring coming in after a swipe to {day} starts off to the side, inside the screen: no horizontal scroll",
              text(page, "h1") == day and abs(start) > 15 and fit["scroll"] <= 0 and not fit["bad"], (text(page, "h1"), start, fit))
    sx, sy = centre_of(page, ".today-days")
    at = "() => document.querySelector('[data-screen=\"today\"] .today-days').scrollLeft"
    start = page.evaluate(at)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": sx, "y": sy}]})
    for i in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": sx + 10 * i, "y": sy}]})
        page.wait_for_timeout(20)
    page.wait_for_timeout(100)
    held, fit = start - page.evaluate(at), page.evaluate(A.FIT_JS)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    strip_still(page)
    check("the strip held 100 px into a drag to the right follows the finger (earlier days come in) and the page does not "
          "scroll sideways: nothing past the edge", 60 <= held <= 110 and fit["scroll"] <= 0 and not fit["bad"], (held, fit))
    ctx.close()


# What the motion has on screen: the swapped numbers and their ghosts, the bars, the day's tank, the tone.
STATE_JS = """() => {
  const s = document.querySelector('[data-screen="today"]');
  const st = el => el ? { text: el.textContent, opacity: el.style.opacity === '' ? 1 : parseFloat(el.style.opacity), transform: el.style.transform } : null;
  const ghost = k => st(s.querySelector(`.today-ghost[data-k="${k}"]`));
  const liq = s.querySelector('.today-day[data-day="2026-10-20"] .today-liq');
  const macs = [0, 1, 2].map(i => ({ g: st(s.querySelectorAll('.today-g > span:first-child')[i]), gGhost: ghost('g' + i),
                                     pct: st(s.querySelectorAll('.today-pct')[i]), pctGhost: ghost('pct' + i),
                                     dn: st(s.querySelectorAll('.today-labs > div')[i].querySelector('.today-devn')), dnGhost: ghost('dn' + i) }));
  return { motion: s.dataset.motion || null, macs, num: st(s.querySelector('.today-frame [data-test="kcal-left"]')), numGhost: ghost('num'),
           ck: st(s.querySelector('.today-corner[data-meal="dinner"] .today-ck')), tot: st(s.querySelector('.today-tot')), totGhost: ghost('tot'),
           bars: [...s.querySelectorAll('.today-bar')].map(b => parseFloat(b.style.flexGrow)), ghosts: s.querySelectorAll('.today-ghost').length,
           devs: [...s.querySelectorAll('.today-devbar')].map(b => b.getAttribute('style')),
           fill: liq ? parseFloat(liq.style.height) : null, over: s.querySelector('.today-frame').classList.contains('today-over') };
}"""
STEP = 16


def sample(page, ms=1100, at=None):
    """Read the screen every 16 ms of page clock (never a real wait); `at` runs a script at the given time."""
    out = []
    for t in range(0, ms + 1, STEP):
        if at and t in at:
            page.evaluate(at[t])
        s = page.evaluate(STATE_JS)
        s["t"], s["arcs"] = t, page.evaluate(ARCS_JS)
        out.append(s)
        page.clock.run_for(STEP)
    return out


def settled_at(samples, done):
    """The time from which `done(sample)` holds to the end."""
    t = None
    for s in samples:
        if done(s):
            if t is None:
                t = s["t"]
        else:
            t = None
    return t


def still(el):
    return el is not None and el["opacity"] == 1 and el["transform"] in ("", "none")


RETURN_JS = """kcal => { Pantry.go('add', 'dinner', Pantry.today());
  Pantry.change(d => { d.entries.push({ id: 'tt-dinner', date: Pantry.today(), meal: 'dinner', foodId: d.foods[0].id, amount: '1 serving',
    grams: null, totals: { kcal, protein: 50, carbs: 100, fat: 40 } }); });
  Pantry.go('today'); }"""
UNDO_JS = "() => Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'tt-dinner'); })"
DINNER = {"protein": 50, "carbs": 100, "fat": 40}      # the macros RETURN_JS logs


def macro_shown(entries):
    """What the macro strip shows for these entries, worked out here: grams eaten ("143 /") and shares ("45%"), carbs,
    protein, fat, rounded half up as the app's numbers are."""
    grams = [sum(e["totals"].get(k, 0) for e in entries) for k in ("carbs", "protein", "fat")]
    kcal = [g * per for g, per in zip(grams, (4, 4, 9))]
    half = lambda v: math.floor(v + 0.5)  # noqa: E731
    return [f"{half(g):,} /" for g in grams], [f"{half(k / sum(kcal) * 100)}%" for k in kcal]


def dev_points(entries):
    """The points each deviation mark writes for these entries, worked out here against the 45 / 20 / 35 % targets."""
    grams = [sum(e["totals"].get(k, 0) for e in entries) for k in ("carbs", "protein", "fat")]
    kcal = [g * per for g, per in zip(grams, (4, 4, 9))]
    return [points(k / sum(kcal) * 100 - t) for k, t in zip(kcal, (45, 20, 35))]


def macros_still(s):
    return all(still(m["g"]) and still(m["pct"]) and m["gGhost"] is None and m["pctGhost"] is None for m in s["macs"])


def check_motion(browser, url, doc, errors):
    """Today after a log, an Undo, a sync announcement, a return with nothing new, and under reduced motion. The page
    clock is installed and paused: every frame is stepped with clock.run_for. Today has 1,304 kcal of breakfast; the
    return adds 1,000 kcal of dinner (2,304: 104 over), as the gram sheet's Add does: log, then Pantry.go('today')."""
    ctx = browser.new_context(**A.PHONE)
    ctx.clock.install(time=A.NOW)
    page = ctx.new_page()
    A.watch(page, errors, "today-motion")
    A.set_text(page, 1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
    page.clock.pause_at(A.NOW + datetime.timedelta(seconds=30))
    show(page)
    before = (page.evaluate(ARCS_JS), page.evaluate(STATE_JS))

    page.evaluate(RETURN_JS, 1000)
    first = page.evaluate(STATE_JS)
    first_arcs = page.evaluate(ARCS_JS)
    fits = page.evaluate(A.FIT_JS)
    run = sample(page)
    end = run[-1]
    final_arcs = end["arcs"]
    dinner = [s["arcs"].get("dinner") for s in run]
    grown = [d for d in dinner if d]
    check("back after logging dinner: the dinner arc grows from its old end (its own start, where breakfast ends at 213.4 deg) "
          "to the top (360), never back",
          "dinner" not in first_arcs and grown and all(abs(d[0] - final_arcs["dinner"][0]) < 0.01 for d in grown)
          and abs(final_arcs["dinner"][0] - 1304 / BUDGET * 360) < 0.5
          and all(b[1] >= a[1] - 0.01 for a, b in zip(grown, grown[1:])) and abs(final_arcs["dinner"][1] - 360) < 0.5
          and len({round(d[1], 1) for d in grown}) > 3, [None if d is None else [round(x, 1) for x in d] for d in dinner[:12]])
    check("only what changed moves: breakfast's arc stays at 0..213.4 in every frame, no other meal gets an arc",
          all(s["arcs"].get("breakfast") == before[0]["breakfast"] and set(s["arcs"]) <= {"breakfast", "dinner"} for s in run),
          before[0])
    check("numbers never count up: kcal-left holds its new value (104) in every frame while the old one (896) leaves as a ghost",
          first["num"]["text"] == "104" and first["numGhost"] and first["numGhost"]["text"] == "896"
          and all(s["num"]["text"] == "104" for s in run) and first["num"]["opacity"] == 0, first)
    today = [e for e in doc["entries"] if e["date"] == "2026-10-20"]
    old_g, old_p = macro_shown(today)
    new_g, new_p = macro_shown(today + [{"totals": DINNER}])
    macs = first["macs"]
    swapped = lambda old, new, real, ghost: (real["opacity"] == 0 and (ghost or {}).get("text") == old  # noqa: E731
                                             if old != new else still(real) and ghost is None)
    check(f"the macro grams ({' / '.join(g[:-2] for g in old_g)} to {' / '.join(g[:-2] for g in new_g)} g) and percentages "
          f"({' / '.join(old_p)} to {' / '.join(new_p)}) "
          "swap too, never jump: in the first frame each changed one holds its new value hidden while its old value shows as "
          "a ghost; an unchanged one gets no ghost",
          old_g != new_g and old_p != new_p and any(a == b for a, b in zip(old_p, new_p))
          and [m["g"]["text"] for m in macs] == new_g and [m["pct"]["text"] for m in macs] == new_p
          and all(swapped(old_g[i], new_g[i], m["g"], m["gGhost"]) and swapped(old_p[i], new_p[i], m["pct"], m["pctGhost"])
                  for i, m in enumerate(macs)), macs)
    old_d, new_d = dev_points(today), dev_points(today + [{"totals": DINNER}])
    dn_swapped = lambda old, new, m: (m["dn"] is not None and m["dn"]["text"] == new and (  # noqa: E731
        m["dn"]["opacity"] == 0 and (m["dnGhost"] or {}).get("text") == (old or None) if old != new else still(m["dn"]) and m["dnGhost"] is None))
    check(f"the deviation points ({' / '.join(map(repr, old_d))} to {' / '.join(map(repr, new_d))}) swap with them, never "
          "jump: a changed one holds its new value hidden in the first frame while its old value leaves as a ghost (none "
          "when it had none); an unchanged one stays still; at the end all are still",
          old_d != new_d and any(a == b for a, b in zip(old_d, new_d))
          and all(dn_swapped(old_d[i], new_d[i], m) for i, m in enumerate(macs))
          and all(still(m["dn"]) and m["dnGhost"] is None for m in end["macs"]), (old_d, new_d, [(m["dn"], m["dnGhost"]) for m in macs]))
    bars_end = settled_at(run, lambda s: s["bars"] == end["bars"])
    times = {
        "arc": settled_at(run, lambda s: s["arcs"] == final_arcs),
        "bars": bars_end,
        "tank": settled_at(run, lambda s: s["fill"] == end["fill"]),
        "corner": settled_at(run, lambda s: still(s["ck"])),
        "total": settled_at(run, lambda s: still(s["tot"]) and s["totGhost"] is None),
        "macro numbers": settled_at(run, macros_still),
        "kcal left": settled_at(run, lambda s: still(s["num"]) and s["numGhost"] is None),
    }
    greys = [v for k, v in times.items() if k != "kcal left"]
    check("the bars and the day's tank move to their new values, the macro numbers land after their bars; the kcal-left "
          "number finishes last, after every grey",
          first["bars"] != end["bars"] and first["fill"] < end["fill"] and None not in times.values()
          and times["macro numbers"] > times["bars"] and all(times["kcal left"] > v for v in greys) and 0 < times["arc"], times)
    devs_end = settled_at(run, lambda s: s["devs"] == end["devs"])
    check("the deviation marks move from their old values to their new ones with the bars and land when the bars do",
          first["devs"] != end["devs"] and devs_end is not None and times["bars"] is not None and devs_end <= times["bars"] + STEP
          and len({s["devs"][1] for s in run}) > 3, (first["devs"], end["devs"], devs_end, times["bars"]))
    flip = settled_at(run, lambda s: s["over"])
    check("the over tone lands with the kcal-left number: grey until its old value has left, then over",
          not first["over"] and end["over"] and flip is not None and times["kcal left"] - 300 <= flip < times["kcal left"]
          and all(s["numGhost"] is None or s["numGhost"]["opacity"] <= 0.01 for s in run if s["over"]), (flip, times))
    check("when it ends nothing of the motion is left: no data-motion, no ghost, no inline offsets",
          end["motion"] is None and end["ghosts"] == 0 and still(end["num"]) and still(end["ck"]) and still(end["tot"])
          and macros_still(end), end)
    check("at 360 px and text 1.0 the moving screen has no horizontal scroll and nothing past the edge",
          fits["scroll"] <= 0 and not fits["bad"], fits)

    # Undo plays the same change back: the arc shrinks from its end to its start, the old number returns
    page.evaluate(UNDO_JS)
    undo = sample(page)
    shrink = [s["arcs"].get("dinner") for s in undo]
    left = [d for d in shrink if d]
    check("Undo plays the change back: the dinner arc shrinks toward its start, 104 over turns back into 896 left, "
          f"{new_g[0][:-2]} g of carbs back into {old_g[0][:-2]}",
          undo[0]["motion"] == "change" and left and all(b[1] <= a[1] + 0.01 for a, b in zip(left, left[1:]))
          and "dinner" not in undo[-1]["arcs"] and (undo[0]["numGhost"] or {}).get("text") == "104" and undo[-1]["num"]["text"] == "896"
          and (undo[0]["macs"][0]["gGhost"] or {}).get("text") == new_g[0] and undo[-1]["macs"][0]["g"]["text"] == old_g[0]
          and undo[-1]["motion"] is None and not undo[-1]["over"],
          ([None if d is None else round(d[1], 1) for d in shrink[:10]], undo[0], undo[-1]))

    # a sync announcement right after the return, and another one in the middle, change nothing in the motion
    page.evaluate("k => { (" + RETURN_JS + ")(k); Pantry.setSyncState({ lastError: 'Sync failed. Saved on this phone; it will try again.' }); }", 1000)
    again = sample(page, at={208: "Pantry.setSyncState({ lastSync: '2026-10-20T00:00:00.000Z' })"})
    ends = [s["arcs"].get("dinner", [0, 0])[1] for s in again]
    replay = {
        "kcal left": settled_at(again, lambda s: still(s["num"]) and s["numGhost"] is None),
        "arc": settled_at(again, lambda s: s["arcs"] == final_arcs),
    }
    check("a Pantry.setSyncState right after the return (a banner: a full redraw) and one at 208 ms do not replay it: "
          "the arc never goes back, everything lands when it did without them",
          page.locator(f"{SCREEN} .banner").count() == 1 and all(b >= a - 0.01 for a, b in zip(ends, ends[1:]))
          and replay == {"kcal left": times["kcal left"], "arc": times["arc"]}, (replay, times))
    page.evaluate("Pantry.setSyncState({ lastError: null })")
    calm = page.evaluate(STATE_JS)
    check("after the motion a sync announcement redraws without moving anything", calm["motion"] is None and calm["ghosts"] == 0, calm)

    # a return that changed nothing
    page.evaluate("() => { Pantry.go('add', 'dinner', Pantry.today()); Pantry.go('today'); }")
    idle = sample(page, ms=64)
    check("a return with no change starts no motion: nothing named, no ghost, the numbers still",
          all(s["motion"] is None and s["ghosts"] == 0 and still(s["num"]) and still(s["tot"]) for s in idle), idle[0])

    # another day picked while the change still plays (Codex review, 2026-10-21): that day shows its own chart
    page.evaluate(UNDO_JS)
    show(page, "2026-10-19")
    page.clock.run_for(2000)
    pick = lambda s, a: {"arcs": a, "bars": s["bars"], "over": s["over"], "num": s["num"]["text"]}  # noqa: E731
    want = pick(page.evaluate(STATE_JS), page.evaluate(ARCS_JS))
    show(page)
    page.clock.run_for(2000)
    page.evaluate(RETURN_JS, 1000)
    page.clock.run_for(208)
    page.click(f'{SCREEN} [data-day="2026-10-19"]')   # in place, as his tap on the strip
    page.clock.run_for(2000)
    got = pick(page.evaluate(STATE_JS), page.evaluate(ARCS_JS))
    check("a day picked 208 ms into the change shows that day's own arcs, bars, tone and number once it settles",
          got == want, (got, want))

    # reduced motion: the chart is drawn at once, the numbers only fade
    page.evaluate(UNDO_JS)
    page.clock.run_for(2000)
    page.emulate_media(reduced_motion="reduce")
    page.evaluate(RETURN_JS, 1000)
    calm_run = sample(page, ms=500)
    moved = [s["t"] for s in calm_run if any(e and "translate" in e["transform"] and not e["transform"].endswith("(0%)")
                                             for e in (s["num"], s["numGhost"], s["tot"], s["totGhost"], s["ck"],
                                                       *[x for m in s["macs"] for x in m.values()]))]
    check("with reduced motion nothing moves: the arcs, bars and tank are at their new values from the first frame, "
          "the numbers only fade, and it is over within fast + base (320 ms)",
          calm_run[0]["arcs"] == final_arcs and calm_run[0]["bars"] == end["bars"] and calm_run[0]["fill"] == end["fill"]
          and not moved and settled_at(calm_run, lambda s: s["motion"] is None) <= 320 + STEP, (moved, calm_run[0]["arcs"]))
    page.emulate_media(reduced_motion="no-preference")
    ctx.close()


# ── Task-12: the deviation marks, the meal pages, the floating + and Scan, the page scrollbar ──

# Each macro's deviation mark: whether it shows, its centre and half width, the target tick's centre, the bar from it,
# its label column, what it says, and the points written over it (their ink, as text).
MARKS_JS = "() => {" + INK_JS + """
 return [...document.querySelectorAll('[data-screen="today"] .today-labs > div')].map(col => {
  const dev = col.querySelector('.today-dev'), r = el => (el ? el.getBoundingClientRect() : null);
  const d = r(dev), t = r(dev && dev.querySelector('.today-devtick')), b = r(dev && dev.querySelector('.today-devbar')), c = r(col);
  const n = dev && dev.querySelector('.today-devn'), nb = n && n.textContent ? ink(n) : null;
  return { visible: !!dev && getComputedStyle(dev).visibility === 'visible' && d.width > 0 && d.height > 0,
           mid: d && d.left + d.width / 2, half: d && d.width / 2, edges: d && [d.left, d.right], top: d && d.top, tick: t && t.left + t.width / 2,
           bar: b && [b.left, b.right], col: c && [c.left, c.right], said: dev && dev.getAttribute('aria-label'),
           points: n ? n.textContent : null, pbox: nb && [nb.left, nb.right, r(n).bottom], size: nb && nb.size };
 }); }"""
SPAN = 20          # points of share for half the mark's scale (app/today.js DEV_SPAN)


def points(d):
    """The points a mark writes for a deviation: rounded half up as the app's numbers are, signed, none on target."""
    if d is None:
        return None
    off = math.floor(d + 0.5)
    return "" if off == 0 else f"{'+' if off > 0 else '−'}{abs(off)}"


def marks_ok(marks, devs):
    """Every mark shows inside its label column, its tick at its centre, and its bar runs from the tick toward the side
    the share leans, min(|deviation|, 20) / 20 of the half long (1 px). Over the scale (never on it, where the bar runs)
    its points are written centred on the tick, inside the column, at 11 px at least; none on target or unlogged."""
    bad = []
    for m, d in zip(marks, devs):
        reach = 0 if d is None else math.copysign(min(abs(d), SPAN) / SPAN * m["half"], d)
        want = sorted([m["mid"], m["mid"] + reach])
        said = points(d)
        written = m["points"] == said if said is None else (m["points"] or "") == said
        placed = not said or (m["pbox"] is not None and abs((m["pbox"][0] + m["pbox"][1]) / 2 - m["tick"]) <= 1
                              and m["pbox"][2] <= m["top"] + 0.5 and m["pbox"][0] >= m["col"][0] - 0.5
                              and m["pbox"][1] <= m["col"][1] + 0.5 and m["size"] >= 11)
        if not (m["visible"] and abs(m["tick"] - m["mid"]) <= 1 and m["edges"][0] >= m["col"][0] - 0.5 and m["edges"][1] <= m["col"][1] + 0.5
                and abs(m["bar"][0] - want[0]) <= 1 and abs(m["bar"][1] - want[1]) <= 1 and written and placed):
            bad.append({"mark": m, "deviation": d, "want": want, "points": said})
    return len(marks) == len(devs) and not bad, bad


def check_marks(page, days):
    for day, words in (("2026-08-08", ["Carbs: 9 points under its 45% target", "Protein: 30 points over its 20% target",
                                       "Fat: 20 points under its 35% target"]), ("2026-10-20", None)):
        d = days[day]
        kc = [d["c"] * 4, d["p"] * 4, d["f"] * 9]
        devs = [k / sum(kc) * 100 - t for k, t in zip(kc, (45, 20, 35))]
        show(page, day)
        marks = page.evaluate(MARKS_JS)
        ok, bad = marks_ok(marks, devs)
        said = [m["said"] for m in marks]
        check(f"{day}: under each macro bar its deviation mark shows how far its share is from its target share "
              f"({', '.join(f'{x:+.1f}' for x in devs)} points: a bar from the target tick, right when above, left when below, "
              f"and over the tick the points, {' / '.join(repr(points(x)) for x in devs)})",
              ok and (words is None or said == words), bad or said)
    show(page, "2026-10-18")
    marks = page.evaluate(MARKS_JS)
    ok, bad = marks_ok(marks, [None] * 3)
    check("a day with nothing logged draws each mark's target tick alone (no bar, no points, nothing said)",
          ok and all(m["said"] is None for m in marks), bad or marks)


PAGES_JS = """() => { const s = document.querySelector('[data-screen="today"]'), pg = s.querySelector('.today-pages');
  const add = s.querySelector('[data-act="add"]');
  return { left: pg.scrollLeft, width: pg.clientWidth,
           selected: [...s.querySelectorAll('.today-tab')].filter(t => t.getAttribute('aria-selected') === 'true').map(t => t.dataset.page),
           live: [...s.querySelectorAll('.today-pg')].filter(p => !p.inert).map(p => p.dataset.pg),
           add: add.getAttribute('aria-label'), addFor: add.dataset.for, scanFor: s.querySelector('[data-act="scan"]').dataset.for,
           armed: s.querySelectorAll('.today-arm').length, h1: s.querySelector('h1').textContent,
           strip: s.querySelector('.today-days').scrollLeft, hash: location.hash, state: JSON.stringify(history.state) }; }"""


def pages_at(page, meal):
    """Waits (at most 5 s) for the pages to rest on `meal`'s snap; returns what the screen shows then."""
    until(page, """i => { const pg = document.querySelector('[data-screen="today"] .today-pages');
        return !!pg && Math.abs(pg.scrollLeft - i * pg.clientWidth) < 1; }""", MEALS.index(meal))
    page.wait_for_timeout(150)
    return page.evaluate(PAGES_JS)


def resting(st, meal):
    """The pages rest on `meal`: scrolled to its snap, its tab alone lit, its page alone live, the + and Scan for it."""
    return (abs(st["left"] - MEALS.index(meal) * st["width"]) < 1 and st["selected"] == [meal] and st["live"] == [meal]
            and st["add"] == f"Add food to {meal}" and st["addFor"] == meal and st["scanFor"] == meal)


def held_drag(page, x0, x1, y):
    """A finger drawn sideways and held still before it lifts (headless Chromium never ends the fling a quick lift
    starts, so the pages would never settle; the phone ends it)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y}]})
    for i in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 10, "y": y}]})
        page.wait_for_timeout(16)
    page.wait_for_timeout(200)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


def tab(page, meal):
    page.locator(f'{SCREEN} .today-tab[data-page="{meal}"]').click()
    return pages_at(page, meal)


def check_pages(browser, url, doc, errors):
    """The eaten section as one page per meal at 360 x 780, text 1.0: 19 Oct has breakfast (3) and dinner (1)."""
    ctx, page = A.phone(browser, errors, "today-pages", text=1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
    day = "2026-10-19"
    names = {f["id"]: f["name"] for f in doc["foods"]}
    logged = lambda meal: [e for e in doc["entries"] if e["date"] == day and e["meal"] == meal]  # noqa: E731
    show(page, day)
    st = pages_at(page, "breakfast")
    check("19 Oct opens on breakfast, its first meal with entries: a tab per meal with its kcal, a page per meal, only "
          "breakfast's page live, its rows in the order logged",
          resting(st, "breakfast") and texts(page, ".today-tab span") == ["Breakfast", "Lunch", "Dinner", "Snacks"]
          and texts(page, ".today-tab b") == ["988", "", "1,304", ""] and page.locator(f"{SCREEN} .today-pg").count() == 4
          and texts(page, '.today-pg[data-pg="breakfast"] .fr .name') == [names[e["foodId"]] for e in logged("breakfast")]
          and len(logged("breakfast")) == 3, st)

    # the empty page: says so, offers Add to <meal>, and is no .fr row
    st = tab(page, "lunch")
    lunch = page.locator(f'{SCREEN} .today-pg[data-pg="lunch"]')
    add_to = lunch.get_by_role("button", name="Add to lunch", exact=True)
    check("tapping Lunch opens its page: it says 'Nothing in lunch that day.' and offers 'Add to lunch'; no placeholder is a "
          ".fr row; Today still has one 'Add food' (the +) and one 'Scan a barcode'",
          resting(st, "lunch") and text(page, '.today-pg[data-pg="lunch"] .note') == "Nothing in lunch that day."
          and add_to.count() == 1 and page.locator(f'{SCREEN} .today-pg:not(:has(.today-li)) .fr').count() == 0
          and page.locator(f"{SCREEN} .fr").count() == 4 and page.get_by_role("button", name="Add food").count() == 1
          and page.get_by_role("button", name="Scan a barcode").count() == 1, st)
    went = tap_goes(page, '.today-pg[data-pg="lunch"] [data-act="addto"]', day)
    st = pages_at(page, "lunch")
    check("'Add to lunch' opens lunch's list for the day; back on Today the lunch page shows again",
          went == f"#/add/lunch/{day}" and resting(st, "lunch"), (went, st))

    # a tab far away: the tabs passed on the way stay unlit
    tab(page, "breakfast")
    page.evaluate("""() => { window.__lit = []; new MutationObserver(ms => ms.forEach(m => {
        if (m.target.getAttribute('aria-selected') === 'true') window.__lit.push(m.target.dataset.page); }))
        .observe(document.querySelector('[data-screen="today"] .today-tabs'), { subtree: true, attributeFilter: ['aria-selected'] }); }""")
    st = tab(page, "snacks")
    lit = page.evaluate("window.__lit")
    check("tapping Snacks from Breakfast scrolls the pages to snacks; only Snacks lights up on the way (lunch and dinner do not)",
          resting(st, "snacks") and lit == ["snacks"], (lit, st))

    # one sideways swipe, one meal; it moves nothing else
    before = tab(page, "breakfast")
    box = page.locator(f"{SCREEN} .today-pages").bounding_box()
    y = box["y"] + 28
    held_drag(page, 330, 90, y)
    one = pages_at(page, "lunch")
    held_drag(page, 90, 330, y)
    back = pages_at(page, "breakfast")
    held_drag(page, 352, 8, y)
    far = pages_at(page, "lunch")
    same = lambda s: (s["h1"], s["strip"], s["hash"], s["state"]) == (before["h1"], before["strip"], before["hash"], before["state"])  # noqa: E731
    check("a sideways swipe on the pages moves one meal (left: lunch, right: breakfast again; a swipe across the whole "
          "screen still one meal) and leaves the day, the strip, the address and history alone",
          resting(one, "lunch") and resting(back, "breakfast") and resting(far, "lunch") and same(one) and same(back) and same(far),
          (one, back, far))

    # a row opens Edit entry; back, and Save, return to the same meal page
    tab(page, "dinner")
    page.locator(f'{SCREEN} .today-pg[data-pg="dinner"] .fr').click()
    until(page, "() => location.hash.startsWith('#/entry/')")
    went = page.evaluate("location.hash")
    page.evaluate("history.back()")
    until(page, BACK_TO_JS, "19 Oct")
    back = pages_at(page, "dinner")
    page.locator(f'{SCREEN} .today-pg[data-pg="dinner"] .fr').click()
    page.wait_for_selector('[data-screen="entry"]')
    page.locator('[data-screen="entry"]').get_by_role("button", name="Save").click()
    page.wait_for_selector(f"{SCREEN} .today-frame")
    saved = pages_at(page, "dinner")
    check("a dinner row opens 'entry <its id>'; back from Edit entry, and its Save, show the dinner page again",
          went == f"#/entry/{logged('dinner')[0]['id']}" and resting(back, "dinner") and resting(saved, "dinner"), (went, back, saved))

    # two deliberate taps take an entry out, through Pantry.removeEntry; Undo puts it back
    tab(page, "breakfast")
    doc0 = A.stored(page)
    rows = f'{SCREEN} .today-pg[data-pg="breakfast"] .today-li'
    first = page.locator(rows).first
    entry_id = first.locator(".fr").get_attribute("data-entry")
    first.locator(".today-del").click()
    one_tap = A.stored(page)
    offered = first.get_by_role("button", name="Delete", exact=True)
    keep = first.locator(".today-del").get_attribute("aria-label")
    food = names[logged("breakfast")[0]["foodId"]]
    shown = offered.count() == 1 and offered.is_visible() and keep == f"Keep {food}"
    if offered.count() == 1:
        offered.click()
    gone = A.stored(page)
    st = pages_at(page, "breakfast")
    toast = page.locator("#toast")
    said = toast.inner_text().strip() if toast.count() else ""
    lines = [r for r in gone.get("removed", []) if r.get("id") == entry_id]
    check("the trash is the first tap (nothing is removed; Delete takes the kcal's place and the trash becomes Keep), Delete "
          "the second: the entry is gone with a doc.removed line, the breakfast page stays, the toast offers Undo",
          one_tap == doc0 and shown and entry_id not in [e["id"] for e in gone["entries"]] and len(lines) == 1
          and isinstance(lines[0].get("at"), str) and resting(st, "breakfast") and said.startswith(f"Deleted {food}")
          and "Undo" in said, (shown, keep, said, lines, st))
    undo = toast.get_by_role("button", name="Undo")
    if undo.count() == 1:
        undo.click()
    undone = A.stored(page)
    check("Undo puts the entry back deep-equal at its place and drops its removed line",
          undone["entries"] == doc0["entries"] and undone.get("removed") == doc0.get("removed")
          and page.locator(rows).count() == 3, (len(undone["entries"]), undone.get("removed")))

    # a double tap on the trash is not two deliberate steps: the second lands on Keep
    spot = centre_of(page, '.today-pg[data-pg="breakfast"] .today-del')
    page.mouse.click(*spot)
    page.mouse.click(*spot)
    st = page.evaluate(PAGES_JS)
    check("two quick taps on one trash remove nothing: the second is Keep, and nothing stays offered",
          A.stored(page)["entries"] == doc0["entries"] and st["armed"] == 0, st)

    # a sideways swipe never removes anything, even one that starts on an offered Delete or on a trash
    page.locator(f"{rows} .today-del").first.click()
    yes = centre_of(page, '.today-pg[data-pg="breakfast"] .today-yes')
    held_drag(page, yes[0], yes[0] - 240, yes[1])
    from_yes = pages_at(page, "lunch")
    tab(page, "breakfast")
    trash = centre_of(page, '.today-pg[data-pg="breakfast"] .today-del')
    held_drag(page, trash[0], trash[0] - 240, trash[1])
    from_trash = pages_at(page, "lunch")
    check("a sideways swipe that starts on an offered Delete, or on a trash, changes the meal and removes nothing; the offer goes",
          resting(from_yes, "lunch") and resting(from_trash, "lunch") and from_yes["armed"] == 0 and from_trash["armed"] == 0
          and A.stored(page)["entries"] == doc0["entries"], (from_yes, from_trash))

    # Delete on Edit entry returns to the same page, which now says it is empty
    tab(page, "dinner")
    page.locator(f'{SCREEN} .today-pg[data-pg="dinner"] .fr').click()
    page.wait_for_selector('[data-screen="entry"]')
    page.locator('[data-screen="entry"]').get_by_role("button", name="Delete").click()
    page.wait_for_selector(f"{SCREEN} .today-frame")
    st = pages_at(page, "dinner")
    check("after a delete on Edit entry, Today shows the dinner page, now 'Nothing in dinner that day.'",
          resting(st, "dinner") and text(page, '.today-pg[data-pg="dinner"] .note') == "Nothing in dinner that day.", st)
    page.locator("#toast").get_by_role("button", name="Undo").click()
    until(page, "() => document.querySelectorAll('[data-screen=\"today\"] .today-pg[data-pg=\"dinner\"] .fr').length === 1")

    # the page he chose holds across the meal clock (11:00): back from Edit entry, on Today and on a past day, and a
    # delete in place; Today brought back to the screen once the clock's meal has moved on opens on the clock's meal
    clock = lambda h, m: page.clock.set_fixed_time(datetime.datetime(2026, 10, 20, h, m, tzinfo=A.DARWIN))  # noqa: E731
    page.evaluate("""() => Pantry.change(d => { for (const [id, meal] of [['tt-b1', 'breakfast'], ['tt-b2', 'breakfast'], ['tt-d1', 'dinner']])
        d.entries.push({ id, date: Pantry.today(), meal, foodId: d.foods[0].id, amount: '1 g', grams: 1, totals: { kcal: 10 } }); })""")
    across = {}
    for d, title in ((None, "Today"), (day, "19 Oct")):
        clock(10, 58)
        show(page, d)
        tab(page, "dinner")
        page.locator(f'{SCREEN} .today-pg[data-pg="dinner"] .fr').first.click()
        page.wait_for_selector('[data-screen="entry"]')
        clock(11, 1)
        page.evaluate("history.back()")
        until(page, BACK_TO_JS, title)
        across[title] = pages_at(page, "dinner")
    clock(10, 58)
    show(page)
    tab(page, "breakfast")
    clock(11, 1)
    n0 = len(A.stored(page)["entries"])
    page.locator(f'{SCREEN} .today-pg[data-pg="breakfast"] .today-del').first.click()
    page.locator(f'{SCREEN} .today-pg[data-pg="breakfast"] .today-yes').click()
    deleted = pages_at(page, "breakfast")
    n1 = len(A.stored(page)["entries"])
    clock(11, 30)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    woken = pages_at(page, "lunch")
    page.clock.set_fixed_time(A.NOW)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => !e.id.startsWith('tt-')); })")
    show(page, day)
    check("the page he chose holds across 11:00 (the clock's meal turning to lunch): back from Edit entry, on Today and on "
          "19 Oct, the dinner page shows; a delete at 11:01 leaves the breakfast page where it is; only Today brought back "
          "to the screen at 11:30 opens on lunch, and its + adds to lunch",
          resting(across["Today"], "dinner") and resting(across["19 Oct"], "dinner") and resting(deleted, "breakfast")
          and n1 == n0 - 1 and resting(woken, "lunch"), (across, deleted, n0, n1, woken))

    # back from logging: the meal just logged to
    tab(page, "breakfast")
    page.evaluate("""day => { Pantry.go('add', 'snacks', day);
        Pantry.change(d => { d.entries.push({ id: 'tt-snack', date: day, meal: 'snacks', foodId: d.foods[0].id, amount: '1 g', grams: 1,
          totals: { kcal: 10 } }); });
        Pantry.go('today', day); }""", day)
    page.wait_for_selector(f"{SCREEN} .today-frame")
    after_log = pages_at(page, "snacks")
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'tt-snack'); })")
    page.evaluate("""() => Pantry.change(d => { d.entries.push({ id: 'tt-dinner-only', date: '2026-07-02', meal: 'dinner',
        foodId: d.foods[0].id, amount: '1 g', grams: 1, totals: { kcal: 10 } }); })""")
    show(page, "2026-07-02")
    only_dinner = pages_at(page, "dinner")
    show(page)
    today = pages_at(page, "breakfast")
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'tt-dinner-only'); })")
    check("the page it opens on: back from logging a snack, snacks; a past day with dinner alone, dinner; Today at 07:00, breakfast",
          resting(after_log, "snacks") and resting(only_dinner, "dinner") and resting(today, "breakfast"), (after_log, only_dinner, today))

    for scheme in ("dark", "light"):
        page.emulate_media(color_scheme=scheme)
        show(page, day)
        tab(page, "lunch")
        A.fits(page, f"Today 19 Oct on its empty lunch page, {scheme}, 360 x 780, text 1.0")
        tab(page, "breakfast")
        page.locator(f"{rows} .today-del").first.click()
        A.fits(page, f"Today 19 Oct with a Delete offered, {scheme}, 360 x 780, text 1.0")
        page.screenshot(path=str(ROOT / ".tmp" / f"today-pages-{scheme}.png"))
        page.locator(f"{rows} .today-del").first.click()
    ctx.close()


def check_double_delete(browser, url, doc, errors):
    """A double tap on Delete takes one entry out and stays on Today: the second tap, on the row that slid up under the
    finger, does nothing; a tap there once the hold is over opens that row. 8 Aug's snacks (the gate's long day): a
    synthetic row (kcal only, so the macro strip above keeps its height) mid-screen, clear of the toast the delete
    brings up; finger taps with the times they claim."""
    ctx, page = A.phone(browser, errors, "today-double-delete", text=1.0)
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", long_day(doc))
    day = "2026-08-08"
    show(page, day)
    tab(page, "snacks")
    trash = '.today-pg[data-pg="snacks"] [data-del="synthetic-scroll-0"]'
    page.evaluate("s => scrollTo(0, scrollY + document.querySelector(s).getBoundingClientRect().top - 300)", f"{SCREEN} {trash}")
    n0 = len(A.stored(page)["entries"])
    page.touchscreen.tap(*centre_of(page, trash))
    page.wait_for_selector(f"{SCREEN} .today-yes")
    spot = centre_of(page, ".today-yes")
    page.touchscreen.tap(*spot)
    page.wait_for_timeout(80)
    under = page.evaluate("""([x, y]) => { const b = document.elementFromPoint(x, y).closest('button');
        return b && b.dataset.entry ? b.dataset.entry : null; }""", list(spot))
    page.touchscreen.tap(*spot)
    page.wait_for_timeout(300)
    twice = page.evaluate(f"() => document.querySelector('{SCREEN} .today-pages') ? ({PAGES_JS})() : {{ hash: location.hash }}")
    n1 = len(A.stored(page)["entries"])
    page.wait_for_timeout(200)
    page.touchscreen.tap(*spot)
    until(page, "() => location.hash.startsWith('#/entry/')")
    later = page.evaluate("location.hash")
    check("two finger taps on Delete 80 ms apart take out one entry and stay on Today's snacks page: the second, on the "
          "row that slid up under the finger, does nothing; a tap there once the hold (350 ms) is over opens that row",
          under is not None and n1 == n0 - 1 and twice["hash"] == f"#/today/{day}" and resting(twice, "snacks")
          and later == f"#/entry/{under}", (under, n0, n1, twice, later))
    ctx.close()


# The text of each row on the shown meal page (ink, not boxes) against the + and Scan; and how the two float.
FAB_CLEAR_JS = "() => {" + INK_JS + """
  const s = document.querySelector('[data-screen="today"]'), r = el => el.getBoundingClientRect();
  const add = s.querySelector('[data-act="add"]'), scan = s.querySelector('[data-act="scan"]');
  const hit = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  const parts = [...s.querySelectorAll('.today-pg:not([inert]) .fr')].flatMap(fr => [...fr.querySelectorAll('.name, .sub, .k')]);
  const under = parts.filter(el => { const i = ink(el), box = { left: i.left, right: i.right, top: r(el).top, bottom: r(el).bottom };
    return hit(box, r(add)) || hit(box, r(scan)); }).map(el => el.textContent);
  const cs = el => getComputedStyle(el);
  const probe = v => { const p = document.createElement('i'); p.style.color = v; s.appendChild(p); const c = cs(p).color; p.remove(); return c; };
  return { rows: parts.length / 3, under, end: Math.abs(scrollY + innerHeight - document.documentElement.scrollHeight) < 1,
           shadow: [cs(add).boxShadow, cs(scan).boxShadow], scanBg: cs(scan).backgroundColor, scanLine: cs(scan).borderTopColor,
           level: { surface1: probe('var(--surface-1)'), surface3: probe('var(--surface-3)'), strong: probe('var(--hairline-strong)') } };
}"""


def long_day(doc):
    """The fixture plus 16 synthetic snacks on 8 Aug (as tests/test_shell.py's scroll checks have it)."""
    d = json.loads(json.dumps(doc))
    potato = "v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg="
    for i in range(16):
        d["entries"].append({"id": f"synthetic-scroll-{i}", "date": "2026-08-08", "meal": "snacks", "foodId": potato,
                             "amount": "100 g", "grams": 100, "totals": {"kcal": 59}})
    return d


def check_fab(browser, url, doc, errors):
    """Scrolled to the end, no row's words or kcal lie under the floating + or Scan, on the longest page and on a short
    one; Scan floats as the + does (the base's level 3: the same shadow; dark a step up with a strong hairline)."""
    for scheme in ("dark", "light"):
        ctx, page = A.phone(browser, errors, f"today-fab-{scheme}", text=1.0)
        page.emulate_media(color_scheme=scheme)
        A.open_today(page, url)
        page.evaluate("d => Pantry.change(() => d, { dirty: false })", long_day(doc))
        for date, meal in (("2026-08-08", "snacks"), ("2026-08-08", "breakfast"), ("2026-10-19", "breakfast")):
            show(page, date)
            tab(page, meal)
            page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(150)
            r = page.evaluate(FAB_CLEAR_JS)
            check(f"{scheme}, {date} on its {meal} page scrolled to the end: no row's name, amount or kcal lies under the + or Scan "
                  f"({int(r['rows'])} rows)", r["end"] and r["rows"] >= 1 and not r["under"], r)
        lvl = r["level"]
        level3 = (r["scanBg"] == lvl["surface3"] and r["scanLine"] == lvl["strong"]) if scheme == "dark" else \
            (r["scanBg"] == lvl["surface1"] and r["shadow"][1] != "none")
        check(f"{scheme}: Scan floats as the + does: the same shadow ({r['shadow'][0]}), the base's level 3 surface, not the flat grey tile",
              r["shadow"][0] == r["shadow"][1] and level3, r)
        A.fits(page, f"Today 19 Oct scrolled to the end, {scheme}, 360 x 780, text 1.0")
        ctx.close()


def check_scrollbar(p, url, doc, errors):
    """No scrollbar line at the page's right edge: a browser that draws classic scrollbars (Playwright hides them by
    default) gives the long Today no scrollbar width, and it still scrolls."""
    browser = p.chromium.launch(ignore_default_args=["--hide-scrollbars"])
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, timezone_id="Australia/Darwin", locale="en-AU")
    ctx.clock.set_fixed_time(A.NOW)
    page = ctx.new_page()
    A.watch(page, errors, "today-scrollbar")
    A.open_today(page, url)
    page.evaluate("d => Pantry.change(() => d, { dirty: false })", long_day(doc))
    show(page, "2026-08-08")
    tab(page, "snacks")
    r = page.evaluate("""() => { const before = scrollY; scrollTo(0, 300); const y = scrollY; scrollTo(0, before);
        return { bar: innerWidth - document.documentElement.clientWidth, room: document.documentElement.scrollHeight - innerHeight, y }; }""")
    check("the long Today scrolls with no page scrollbar at its right edge (0 px of scrollbar where one would take 15)",
          r["bar"] == 0 and r["room"] > 300 and r["y"] == 300, r)
    ctx.close()
    browser.close()


SCENARIOS = ["main", "fit", "first launch", "status", "tap after swipe", "edges", "motion", "pages", "fab", "scrollbar"]


def main():
    want = set(sys.argv[1:]) or set(SCENARIOS)
    unknown = want - set(SCENARIOS)
    if unknown:
        raise SystemExit(f"unknown scenario {sorted(unknown)}; choose from {SCENARIOS}")
    days = fixture_days()
    doc = imported()
    srv, site, url = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            if "main" in want:
                ctx, page = A.phone(browser, errors, "today")
                A.open_today(page, url)
                page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
                for name, fn, args in (("8 Aug", check_day, (page, days)), ("ring", check_ring, (page, days)),
                                       ("deviation mark", check_marks, (page, days)),
                                       ("strip", check_strip, (page, url)), ("waves", check_waves, (page,)),
                                       ("routes", check_routes, (page,)), ("live", check_live, (page,)),
                                       ("banner", check_banner, (page,)), ("dates", check_dates, (page,)),
                                       ("midnight", check_midnight, (page,)), ("meal follows the clock", check_meal_clock, (page,)), ("ring swipe", check_swipe, (page,)),
                                       ("days in place", check_in_place, (page,)), ("text and theme", check_text_and_theme, (page, url))):
                    A.guarded(f"Today {name} checks", fn, *args)
                ctx.close()
            for key, name, fn, args in (("fit", "fit", check_fit, (browser, url, doc, errors)),
                                        ("first launch", "first launch", check_first_launch, (browser, url, errors)),
                                        ("status", "budget status", check_status, (browser, url, doc, errors)),
                                        ("tap after swipe", "tap after a swipe", check_tap_after_swipe, (browser, url, doc, errors)),
                                        ("edges", "moving edge", check_moving_edges, (browser, url, doc, errors)),
                                        ("motion", "motion", check_motion, (browser, url, doc, errors)),
                                        ("pages", "meal pages", check_pages, (browser, url, doc, errors)),
                                        ("pages", "double tap on Delete", check_double_delete, (browser, url, doc, errors)),
                                        ("fab", "floating + and Scan", check_fab, (browser, url, doc, errors)),
                                        ("scrollbar", "page scrollbar", check_scrollbar, (p, url, doc, errors))):
                if key in want:
                    A.guarded(f"Today {name} checks", fn, *args)
            browser.close()
        check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

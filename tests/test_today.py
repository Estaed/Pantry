"""Checks for Task-02, Today: day strip, meals in the corners, the G3 ring, the macro strip, the eaten list; and for
Task-09: the budget status tones, days switched in place, the ring swipe, and the motion that shows what changed.

Run from the repo root: python tests/test_today.py   (exit 0 = no FAIL). Reuses the gate's server and phone from
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

# Start and end of each ring segment in degrees clockwise from 12 o'clock, read from the drawn path: the M point, then
# the end point of every arc in it, unwrapped so the end follows the start.
ARCS_JS = """() => Object.fromEntries([...document.querySelectorAll('[data-screen="today"] .today-seg')].map(p => {
  const n = p.getAttribute('d').match(/-?\\d+(?:\\.\\d+)?/g).map(Number);
  const box = p.ownerSVGElement.viewBox.baseVal, cx = box.width / 2, cy = box.height / 2;
  const pts = [[n[0], n[1]]];
  for (let i = 2; i + 6 < n.length; i += 7) pts.push([n[i + 5], n[i + 6]]);
  const ang = ([x, y]) => Math.atan2(x - cx, cy - y) * 180 / Math.PI;
  let start = ang(pts[0]);
  if (start < -90.5) start += 360;
  let end = start;
  for (let k = 1; k < pts.length; k++) { let d = ang(pts[k]) - ang(pts[k - 1]); while (d <= 0) d += 360; end += d; }
  return [p.dataset.meal, [start, end]];
}))"""

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

STRIP_JS = """() => [...document.querySelectorAll('[data-screen="today"] .today-day')].map(d => {
  const liq = d.querySelector('.today-liq');
  return { day: d.dataset.day, name: d.querySelector('span').textContent, num: d.querySelector('b').textContent,
           label: d.querySelector('em').textContent, over: d.classList.contains('today-ov'), on: d.classList.contains('today-on'),
           fill: liq ? liq.getBoundingClientRect().height / d.clientHeight : 0,
           wordsFit: [...d.querySelectorAll('span, b, em')].every(w => w.getBoundingClientRect().width <= d.clientWidth) };
})"""

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

# The visible words of an element as line boxes: one rect per line per text node, surrounding spaces left out.
INK_JS = """const ink = el => {
  const rects = [], walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let size = null;
  for (let n; (n = walk.nextNode());) {
    const t = n.textContent;
    if (!t.trim() || getComputedStyle(n.parentElement).visibility !== 'visible') continue;
    const r = document.createRange(); r.setStart(n, t.search(/\\S/)); r.setEnd(n, t.trimEnd().length);
    rects.push(...[...r.getClientRects()].filter(x => x.width > 0));
    if (size === null) size = parseFloat(getComputedStyle(n.parentElement).fontSize);
  }
  return { left: Math.min(...rects.map(x => x.left)), right: Math.max(...rects.map(x => x.right)),
           lines: new Set(rects.map(x => Math.round(x.top))).size, size };
};"""

# Each macro label against its bar and its neighbours; the gap the labels keep is one em of their text (0.75rem).
LABELS_JS = "() => {" + INK_JS + """
  const q = s => [...document.querySelectorAll('[data-screen="today"] ' + s)];
  const row = document.querySelector('[data-screen="today"] .today-labs').getBoundingClientRect();
  return { sep: 0.75 * parseFloat(getComputedStyle(document.documentElement).fontSize), row: [row.left, row.right],
           bars: q('.today-bar').map(b => [b.getBoundingClientRect().left, b.getBoundingClientRect().right]),
           labels: q('.today-labs > div').map(ink) };
}"""

# The bottom button's words: how many lines, whether its + shows, their size against 1rem.
ADD_JS = "() => {" + INK_JS + """
  const b = document.querySelector('[data-screen="today"] .bottom [data-act="add"]');
  return { text: b.textContent, ...ink(b), plus: getComputedStyle(b.querySelector('svg')).display !== 'none',
           rem: parseFloat(getComputedStyle(document.documentElement).fontSize) };
}"""

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


def spill(kcals):
    """The G3 rule worked by hand: each meal starts at its quarter or where the one before ended, whichever is later."""
    end, out = None, {}
    for meal, start, k in zip(MEALS, (-90, 0, 90, 180), kcals):
        if k:
            s = start if end is None else max(start, end)
            end = s + k / BUDGET * 360
            out[meal] = (s, end)
    return out


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
    check("a past day: eyebrow 'Saturday, 8 August', title '8 Aug', 'Eaten that day', 'Add to this day'",
          text(page, ".top .eyebrow") == "Saturday, 8 August" and text(page, "h1") == "8 Aug"
          and text(page, ".today-eaten .eyebrow") == "Eaten that day" and text(page, '[data-act="add"]') == "Add to this day",
          (text(page, ".top .eyebrow"), text(page, "h1"), text(page, '[data-act="add"]')))
    rows = texts(page, ".fr .sub")
    check("a past day lists what was eaten in meal order", rows == ["Breakfast, 3 pieces", "Lunch, 1 servings", "Dinner, 1000 g",
                                                                     "Snacks, 1.5 slices"], rows)
    A.rows_single_line(page, "Today, 8 Aug")


def check_ring(page, days):
    show(page, "2026-08-08")
    arcs = page.evaluate(ARCS_JS)
    want = {"breakfast": (-90, 55), "lunch": (55, 112), "dinner": (112, 209), "snacks": (209, 233)}
    rule = spill([days["2026-08-08"]["meals"][m] for m in MEALS])
    check("the hand-worked spill rule gives the angles the task names for 8 Aug",
          all(abs(rule[m][0] - want[m][0]) <= 2 and abs(rule[m][1] - want[m][1]) <= 2 for m in MEALS), rule)
    check("8 Aug ring, measured from the drawn arcs: breakfast -90..55, lunch 55..112, dinner 112..209, snacks 209..233 (2 deg)",
          set(arcs) == set(MEALS) and all(abs(arcs[m][0] - want[m][0]) <= 2 and abs(arcs[m][1] - want[m][1]) <= 2 for m in MEALS), arcs)
    initials = texts(page, ".today-ini")
    check("each segment carries its meal's initial", initials == ["B", "L", "D", "S"], initials)

    show(page, "2026-10-19")
    arcs = page.evaluate(ARCS_JS)
    b = arcs.get("breakfast", (None, None))
    d = arcs.get("dinner", (None, None))
    check("19 Oct ring: breakfast -90..71.7; dinner starts in its own quarter at 90, not at 71.7 (2 deg)",
          set(arcs) == {"breakfast", "dinner"} and abs(b[0] + 90) <= 2 and abs(b[1] - 71.7) <= 2
          and d[0] is not None and abs(d[0] - 90) <= 2 and abs(d[0] - 71.7) > 10, arcs)
    check("19 Oct is 92 over: the ring is full (a closed track), the tail stops at 9 o'clock, the centre says '92 kcal over'",
          page.locator(f"{SCREEN} .today-track.today-full").count() == 1 and d[1] is not None and d[1] <= 270.5
          and text(page, '[data-test="kcal-left"]') == "92" and text(page, ".today-lbl") == "kcal over", (d, text(page, ".today-lbl")))

    # under budget, a heavy last meal that would run past 9 o'clock is pulled back into free space, never over breakfast
    page.evaluate("""() => Pantry.change(d => { d.entries.push(
        { id: 'tt-b', date: '2026-07-01', meal: 'breakfast', foodId: 'x', amount: '1', grams: null, totals: { kcal: 300 } },
        { id: 'tt-d', date: '2026-07-01', meal: 'dinner', foodId: 'x', amount: '1', grams: null, totals: { kcal: 900 } },
        { id: 'tt-s', date: '2026-07-01', meal: 'snacks', foodId: 'x', amount: '1', grams: null, totals: { kcal: 700 } }); })""")
    show(page, "2026-07-01")
    arcs = page.evaluate(ARCS_JS)
    sizes = {m: arcs[m][1] - arcs[m][0] for m in arcs}
    order = sorted(arcs.values())
    check("under budget, every arc keeps its size and none overlaps another or passes a full turn",
          all(abs(sizes[m] - k / BUDGET * 360) <= 0.5 for m, k in (("breakfast", 300), ("dinner", 900), ("snacks", 700)))
          and all(a[1] <= c[0] + 0.01 for a, c in zip(order, order[1:])) and order[0][0] >= -90.01 and order[-1][1] <= 270.01, arcs)
    page.evaluate("() => Pantry.change(d => { d.entries = d.entries.filter(e => !e.id.startsWith('tt-')); })")


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
    check("the opened day's strip ends at it", strip_days(page)[-1] == "2026-08-05" and text(page, "h1") == "5 Aug", strip_days(page))

    show(page, "2026-08-08")
    box = page.locator(f"{SCREEN} .today-days").bounding_box()
    y = box["y"] + box["height"] / 2
    hash_before = page.evaluate("location.hash")
    swipe(page, box["x"] + 60, box["x"] + box["width"] - 30, y)
    earlier = strip_days(page)
    swipe(page, box["x"] + box["width"] - 30, box["x"] + 60, y)
    back = strip_days(page)
    swipe(page, box["x"] + box["width"] - 30, box["x"] + 60, y)
    later = strip_days(page)
    check("a swipe right shows the week before (26 Jul to 1 Aug), a swipe left the week after, the shown day stays 8 Aug",
          earlier[0] == "2026-07-26" and earlier[-1] == "2026-08-01" and back[-1] == "2026-08-08" and later[-1] == "2026-08-15"
          and text(page, "h1") == "8 Aug" and page.evaluate("location.hash") == hash_before, (earlier, back, later))
    show(page, "2026-10-19")
    swipe(page, box["x"] + box["width"] - 30, box["x"] + 60, y)
    check("the strip never runs past today: a swipe left from 19 Oct stops at 20 Oct", strip_days(page)[-1] == "2026-10-20", strip_days(page))
    page.wait_for_timeout(450)                 # a tap right after a swipe is the swipe's own touch ending, so it is ignored
    page.locator(f'{SCREEN} .today-day[data-day="2026-10-20"]').click()
    check("tapping today in the strip shows Today in place, which follows the clock (state.day null, no date)",
          text(page, "h1") == "Today" and page.evaluate("'day' in history.state && history.state.day === null")
          and page.evaluate("location.hash") == "#/today/2026-10-19", (text(page, "h1"), page.evaluate("history.state")))


def check_waves(page):
    show(page)
    waves = page.evaluate(WAVES_JS)
    filled = sum(1 for d in page.evaluate(STRIP_JS) if d["fill"] > 0)
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
    check("on a past day, Add to this day opens add <the clock's meal> <date>, scan opens scan <meal> <date>, a row opens entry <id>, the gear settings",
          went == want, went)
    show(page)
    check("on Today at 07:00 the bottom button says 'Add to breakfast' and is found as 'Add food'",
          text(page, '[data-act="add"]') == "Add to breakfast" and page.get_by_role("button", name="Add food").count() == 1
          and page.get_by_role("button", name="Scan a barcode").count() == 1, text(page, '[data-act="add"]'))
    went = [tap_goes(page, '[data-act="add"]', None), tap_goes(page, '.today-corner[data-meal="lunch"]', None)]
    check("on Today the bottom button opens add breakfast 2026-10-20 and the Lunch corner add lunch 2026-10-20",
          went == ["#/add/breakfast/2026-10-20", "#/add/lunch/2026-10-20"], went)


def check_live(page):
    show(page)
    food = page.evaluate("Pantry.doc().foods[0].id")
    seen = page.evaluate("""f => {
        const read = () => [document.querySelector('[data-test="kcal-left"]').textContent,
                            (document.querySelector('.today-corner[data-meal="lunch"] .today-ck') || {}).textContent || null,
                            document.querySelector('[data-screen="today"] .fr .sub').textContent];
        const before = read();
        Pantry.change(d => { d.entries.push({ id: 'tt-live', date: Pantry.today(), meal: 'lunch', foodId: f, amount: '1 g', grams: 1, totals: { kcal: 500 } }); });
        const added = read();
        Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== 'tt-live'); });
        return [before, added, read()];
    }""", food)
    check("an entry added or removed shows in the same frame: kcal left, the corner, the newest row first",
          seen[0][:2] == ["896", None] and seen[1] == ["396", "500", "Lunch, 1 g"] and seen[2][:2] == ["896", None], seen)


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
    label = text(page, '[data-act="add"]')
    went = [tap_goes(page, '[data-act="add"]', None), tap_goes(page, '[data-act="scan"]', None)]
    page.clock.set_fixed_time(A.NOW)
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    check("Today left open from 07:00 to 12:00: the bottom button says 'Add to lunch' and Add and Scan open lunch",
          label == "Add to lunch" and went == ["#/add/lunch/2026-10-20", "#/scan/lunch/2026-10-20"], (label, went))


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
            add = page.evaluate(ADD_JS)
            check(f"{label}: '{add['text']}' stays on one line beside Scan", add["lines"] == 1, add)
            if size[0] == 360 and scale <= 1.5:
                check(f"{label}: with room for it, the button keeps its + and its words at 1rem", add["plus"]
                      and abs(add["size"] - add["rem"]) < 0.01, add)
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
    check("every text on Today for 8 Aug grows with the text size, the ring's initials included (rem only)",
          len(small) == len(big) and small and not flat and sum(1 for n in names if n in ("span:B", "span:L", "span:D", "span:S")) >= 4,
          flat or (len(small), len(big)))

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
    bar = page.evaluate("""() => { const b = document.querySelector('[data-screen="today"] .bottom'), r = b.getBoundingClientRect(),
        add = b.querySelector('[data-act="add"]').getBoundingClientRect(), scan = b.querySelector('[data-act="scan"]').getBoundingClientRect();
        return [add.left - r.left, r.right - scan.right, scan.left - add.right]; }""")
    check("first launch: Add and Scan fill the bottom bar edge to edge (20 px sides, 10 px apart)",
          all(abs(a - b) <= 0.5 for a, b in zip(bar, (20, 20, 10))), bar)
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
  return { ring: [...s.querySelectorAll('.today-seg')].map(p => rgb(cs(p).stroke)), num: rgb(cs(num).color),
           sw: [...s.querySelectorAll('.today-sw')].map(e => rgb(cs(e).backgroundColor)),
           bars: [...s.querySelectorAll('.today-bar')].map(e => rgb(cs(e).backgroundColor)),
           cells, accent: probe('var(--primary-display)'), words: [num.textContent, s.querySelector('.today-lbl').textContent] };
}"""

NEUTRAL, TONED = 0.02, 0.05      # OKLCH chroma: below is grey, above carries a hue


def check_status(browser, url, doc, errors):
    """Within budget the greys and the orange answer; over it one hue on the ring, its swatches, the number and the
    day's tank, clear of the orange accent; a macro bar over its own target takes it too; an empty day stays neutral.
    Synthetic days: 2,200.4 kcal (shown as 2,200: within), 2,200.6 (shown as 2,201: over by 1), 1,500, and nothing."""
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
        tone = over["num"]
        check(f"{scheme}: 2,200.4 kcal reads '0 kcal left' and stays within: the ring grey, the number the orange answer",
              within["words"] == ["0", "kcal left"] and within["ring"] and all(chroma(c) < NEUTRAL for c in within["ring"])
              and delta(within["num"], within["accent"]) < 0.01 and all(chroma(c) < NEUTRAL for c in within["sw"]),
              {"words": within["words"], "ring": within["ring"], "num": within["num"], "accent": within["accent"]})
        check(f"{scheme}: 2,200.6 kcal reads '1 kcal over' and the ring, its swatches and the number turn to one hue, clear of the orange",
              over["words"] == ["1", "kcal over"] and chroma(tone) >= 0.1 and delta(tone, over["accent"]) >= 0.15
              and over["ring"] and all(chroma(c) >= TONED and hue_gap(c, tone) <= 20 for c in over["ring"] + over["sw"]),
              {"words": over["words"], "num": tone, "ring": over["ring"], "sw": over["sw"], "accent": over["accent"]})
        check(f"{scheme}: within and over differ on the ring, the swatches and the number",
              delta(within["ring"][0], over["ring"][0]) > 0.1 and delta(within["num"], tone) > 0.1
              and delta(within["sw"][0], over["sw"][0]) > 0.1, (within["ring"][0], over["ring"][0], within["num"], tone))
        shown_over = over["cells"]["2026-09-11"]
        check(f"{scheme}: the shown day over budget fills its tank in the over tone, not the orange of the shown day",
              shown_over["over"] and shown_over["fill"] and chroma(shown_over["fill"]) >= TONED and hue_gap(shown_over["fill"], tone) <= 20,
              shown_over)
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
        check(f"{scheme}: 8 Aug's protein (258 / 110 g) is over its target and takes the over tone; carbs (186 / 248) and fat (34 / 86) stay grey",
              len(bars) == 3 and chroma(bars[1]) >= TONED and hue_gap(bars[1], tone) <= 20
              and chroma(bars[0]) < NEUTRAL and chroma(bars[2]) < NEUTRAL, bars)
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
    strip_swipe(page, 160)
    shifted = until(page, "() => !!document.querySelector('[data-screen=\"today\"] .today-day[data-day=\"2026-10-10\"]')")
    touch_tap(page, '.today-day[data-day="2026-10-10"]')
    check("a swipe on the strip to the week before, then at once a finger tap on 10 Oct: 10 Oct",
          shifted and until(page, BACK_TO_JS, "10 Oct"), text(page, "h1"))
    ctx.close()


# The ring's frame offset, and the strip's slide paused at its first frame (where it starts farthest out)
OFFSET_JS = """() => { const f = document.querySelector('[data-screen="today"] .today-frame');
  const m = f.style.transform.match(/translateX\\((-?[\\d.]+)px\\)/); return m ? Number(m[1]) : 0; }"""
SLIDE_JS = """at => { const nav = document.querySelector('[data-screen="today"] .today-days');
  const slides = nav.getAnimations({ subtree: true }).filter(a => a.animationName === 'today-in');
  slides.forEach(a => { a.pause(); a.currentTime = at; });
  return { slides: slides.length, left: nav.querySelector('.today-day').getBoundingClientRect().left }; }"""


def check_moving_edges(browser, url, doc, errors):
    """At 360 px and text 1.0, whatever Today moves sideways stays inside the screen: the ring held mid-drag either way,
    the ring coming in after a swipe, the strip's days sliding in after a week swipe. Page clock paused: the frames are
    read where they start, farthest out."""
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
    for dx, week in ((160, "the week before"), (-160, "the week after")):
        strip_swipe(page, dx)
        first = page.evaluate(SLIDE_JS, 0)
        fit = page.evaluate(A.FIT_JS)
        last = page.evaluate(SLIDE_JS, 10000)
        check(f"the strip's days sliding in for {week} start off to the side, inside the screen: no horizontal scroll",
              first["slides"] > 0 and abs(first["left"] - last["left"]) >= 8 and fit["scroll"] <= 0 and not fit["bad"],
              (first, last, fit))
    ctx.close()


# What the motion has on screen: the swapped numbers and their ghosts, the bars, the day's tank, the tone.
STATE_JS = """() => {
  const s = document.querySelector('[data-screen="today"]');
  const st = el => el ? { text: el.textContent, opacity: el.style.opacity === '' ? 1 : parseFloat(el.style.opacity), transform: el.style.transform } : null;
  const ghost = k => st(s.querySelector(`.today-ghost[data-k="${k}"]`));
  const liq = s.querySelector('.today-day[data-day="2026-10-20"] .today-liq');
  const macs = [0, 1, 2].map(i => ({ g: st(s.querySelectorAll('.today-g > span:first-child')[i]), gGhost: ghost('g' + i),
                                     pct: st(s.querySelectorAll('.today-pct')[i]), pctGhost: ghost('pct' + i) }));
  return { motion: s.dataset.motion || null, macs, num: st(s.querySelector('.today-frame [data-test="kcal-left"]')), numGhost: ghost('num'),
           ck: st(s.querySelector('.today-corner[data-meal="dinner"] .today-ck')), tot: st(s.querySelector('.today-tot')), totGhost: ghost('tot'),
           bars: [...s.querySelectorAll('.today-bar')].map(b => parseFloat(b.style.flexGrow)), ghosts: s.querySelectorAll('.today-ghost').length,
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
    check("back after logging dinner: the dinner arc grows from its old end (its own start, 123 deg) to 270, never back",
          "dinner" not in first_arcs and grown and all(abs(d[0] - final_arcs["dinner"][0]) < 0.01 for d in grown)
          and all(b[1] >= a[1] - 0.01 for a, b in zip(grown, grown[1:])) and abs(final_arcs["dinner"][1] - 270) < 0.5
          and len({round(d[1], 1) for d in grown}) > 3, [None if d is None else [round(x, 1) for x in d] for d in dinner[:12]])
    check("only what changed moves: breakfast's arc stays at -90..123 in every frame, no other meal gets an arc",
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


def main():
    days = fixture_days()
    doc = imported()
    srv, site, url = A.start_site()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx, page = A.phone(browser, errors, "today")
            A.open_today(page, url)
            page.evaluate("d => Pantry.change(() => d, { dirty: false })", doc)
            for name, fn, args in (("8 Aug", check_day, (page, days)), ("ring", check_ring, (page, days)),
                                   ("strip", check_strip, (page, url)), ("waves", check_waves, (page,)),
                                   ("routes", check_routes, (page,)), ("live", check_live, (page,)),
                                   ("banner", check_banner, (page,)), ("dates", check_dates, (page,)),
                                   ("midnight", check_midnight, (page,)), ("meal follows the clock", check_meal_clock, (page,)), ("ring swipe", check_swipe, (page,)),
                                   ("days in place", check_in_place, (page,)), ("text and theme", check_text_and_theme, (page, url))):
                A.guarded(f"Today {name} checks", fn, *args)
            ctx.close()
            A.guarded("Today fit checks", check_fit, browser, url, doc, errors)
            A.guarded("Today first launch checks", check_first_launch, browser, url, errors)
            A.guarded("Today budget status checks", check_status, browser, url, doc, errors)
            A.guarded("Today tap after a swipe checks", check_tap_after_swipe, browser, url, doc, errors)
            A.guarded("Today moving edge checks", check_moving_edges, browser, url, doc, errors)
            A.guarded("Today motion checks", check_motion, browser, url, doc, errors)
            browser.close()
        check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

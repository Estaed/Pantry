"""Checks for Task-02, Today: day strip, meals in the corners, the G3 ring, the macro strip, the eaten list.

Run from the repo root: python tests/test_today.py   (exit 0 = no FAIL). Reuses the gate's server and phone from
tests/acceptance.py (360 x 780, text at 150 %, Darwin, 07:00 on 20 Oct 2026). The data is the committed fixture
(tests/fixtures/mynetdiary-slice.json: 8 Aug, 19 Oct, 20 Oct 2026, the days design/screens.html shows), converted by
tools/import_mynetdiary.py into .tmp/test_today/ as Tarik converts his history. Expected numbers are worked out here
from the fixture, never read from the app. Synthetic entries are built in the page only to exercise a rule.
Screenshots of Today in dark and light go to .tmp/today-dark.png and .tmp/today-light.png.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

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
    kc = [aug8["p"] * 4, aug8["c"] * 4, aug8["f"] * 9]
    shares = [k / sum(kc) * 100 for k in kc]
    pcts = texts(page, ".today-pct")
    check("the macro strip reads 50 / 36 / 15 % for protein, carbs, fat", pcts == ["50%", "36%", "15%"]
          and [f"{round(s)}%" for s in shares] == pcts, pcts)
    widths = page.evaluate("() => [...document.querySelectorAll('[data-screen=\"today\"] .today-bar')].map(b => b.getBoundingClientRect().width)")
    got = [w / sum(widths) * 100 for w in widths]
    check("each macro bar's width is its share of protein x 4 + carbs x 4 + fat x 9 (within 1 point)",
          len(got) == 3 and all(abs(g - s) <= 1.0 for g, s in zip(got, shares)), (got, shares))
    grams = texts(page, ".today-g")
    check("under each bar: grams eaten against the target from 20 / 45 / 35 % of 2,200",
          grams == ["258 / 110 g", "186 / 248 g", "34 / 86 g"] and text(page, ".today-fig") == "target 20 / 45 / 35%", grams)
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
    went = tap_goes(page, '.today-day[data-day="2026-08-05"]', "2026-08-08")
    check("tapping 5 Aug in the strip opens that day (today 2026-08-05)", went == "#/today/2026-08-05", went)
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
    went = tap_goes(page, '.today-day[data-day="2026-10-20"]', None)
    check("tapping today in the strip opens Today, which follows the clock (today, no date)", went == "#/today", went)


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
                                   ("midnight", check_midnight, (page,)), ("meal follows the clock", check_meal_clock, (page,)), ("text and theme", check_text_and_theme, (page, url))):
                A.guarded(f"Today {name} checks", fn, *args)
            ctx.close()
            A.guarded("Today fit checks", check_fit, browser, url, doc, errors)
            A.guarded("Today first launch checks", check_first_launch, browser, url, errors)
            browser.close()
        check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

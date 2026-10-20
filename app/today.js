/* Today: the day at a glance (design/screens.html: 1. Today, 7. A past day, First launch, Sync failed).
   Route `today [date]`: no date, a date that is not YYYY-MM-DD, or today's date shows Today and follows the clock past
   midnight; any other date shows that day ("8 Aug").

   Top to bottom: the date with Settings; the day strip, seven days ending at the shown day, each a tank filled to its
   kcal on a scale of max(2,750, 1.25 x budget) with a slow wave on top, the dashed budget line and the difference to
   budget (a swipe moves it a week, the shown day stays); the ring with the four meals in the corners; the macro strip
   (each macro's width is its share of protein x 4 + carbs x 4 + fat x 9); what was eaten; Add to <meal> and Scan.

   Ring (G3): a meal's arc is its kcal / budget x 360 degrees. It starts in its own quarter (breakfast at 9 o'clock,
   lunch at 12, dinner at 3, snacks at 6) or where the meal before it ended, whichever is later, and runs on. Under
   budget a tail that would pass 9 o'clock again is pulled back into free space; over budget the ring is full and the
   tail stops at 9 o'clock. Each arc's path holds its exact angles; the gap between neighbours is the dash pattern.

   layout() places the ring between the corners so no meal name or kcal touches the ring's box and no drawing touches
   the ring, and keeps the centre's words inside the ring, at any text size and width. Gate hooks: data-test="kcal-left"; .top .eyebrow; eaten rows .fr with
   .name/.sub; one .banner; the buttons "Add food" (the bottom button's accessible name is "Add food to <meal>",
   its text "Add to <meal>") and "Scan a barcode".

   First launch differs from design/screens.html (First launch) only to keep those hooks: the gate opens an empty log,
   reads "2,200" from kcal-left and taps "Add food" and "Scan a barcode" there, so the sentence starts with
   "2,200 kcal left today." and the bottom bar (Add to <meal>, Scan) stands in for the secondary "Scan a product"
   button. Once the gate's first-launch steps move, this screen can follow the design exactly. */
(() => {
  'use strict';
  const P = window.Pantry;
  const MEALS = ['breakfast', 'lunch', 'dinner', 'snacks'];
  const NAME = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snacks: 'Snacks' };
  const CORNER = ['today-tl', 'today-tr', 'today-br', 'today-bl'];
  const QUARTER = [-90, 0, 90, 180];                 // degrees clockwise from 12 o'clock
  const FULL = 270;                                   // back at 9 o'clock: the ring is full
  const SIZE = 196, MID = 98, RADIUS = 87, OUTER = 94, GAP = 2.5;   // ring geometry in its viewBox (px at 100 % text)
  const DAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MONTH = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MACROS = [['protein', 'Protein', 4], ['carbs', 'Carbs', 4], ['fat', 'Fat', 9]];
  // one period of the design's wave (M0 3 Q5 0 10 3 T20 3, closed below), tiled along the top of each day's fill
  const WAVE = 'url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 20 7%27 preserveAspectRatio=%27none%27%3E%3Cpath d=%27M0 3Q5 0 10 3T20 3V7H0Z%27/%3E%3C/svg%3E")';
  const GEAR = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';

  P.css(`
    [data-screen="today"] { -webkit-text-size-adjust: none; text-size-adjust: none;
      --today-g1: var(--ink); --today-g3: color-mix(in oklab, var(--ink) 40%, var(--canvas)); --today-dx: 24px; }
    @media (prefers-reduced-motion: reduce) { [data-screen="today"] { --today-dx: 0px; } }
    .today-top > div { flex: 1; }
    .today-t1 { background: var(--today-g1); color: var(--canvas); }
    .today-t3 { background: var(--today-g3); color: var(--ink); }

    .today-days { display: flex; gap: 5px; padding: 12px 14px 0; touch-action: pan-y; }
    .today-days.today-from-r, .today-days.today-from-l { animation: today-in var(--dur-base) var(--ease-enter); }
    .today-days.today-from-l { --today-dx: -24px; }
    @media (prefers-reduced-motion: reduce) { .today-days.today-from-l { --today-dx: 0px; } }
    @keyframes today-in { from { opacity: 0; transform: translateX(var(--today-dx)); } }
    .today-day {
      --today-fill: color-mix(in oklab, var(--ink) 13%, transparent);
      /* tall enough, and the words low enough, that the dashed budget line stays above them at any text size */
      flex: 1 1 0; min-width: 0; min-height: 4.625rem; padding: 6px 0 7px; position: relative; overflow: hidden;
      display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
      border-radius: 14px; background: var(--surface-1); border: 1px solid var(--hairline);
      font: 600 calc(0.6875rem * var(--today-fit, 1))/1.25 var(--font-sans); color: var(--ink-muted);
    }
    .today-day.today-ov { --today-fill: color-mix(in oklab, var(--ink) 24%, transparent); }
    .today-day.today-on { --today-fill: color-mix(in oklab, var(--primary) 20%, transparent); border: 1.5px solid var(--ink); }
    .today-day > span, .today-day > b, .today-day > em { position: relative; z-index: 1; white-space: nowrap; }
    .today-day > b { font: 700 calc(0.9375rem * var(--today-fit, 1))/1.2 var(--font-figure); color: var(--ink); }
    .today-day > em { margin-top: 1px; font: 700 calc(0.6875rem * var(--today-fit, 1))/1.25 var(--font-figure); font-style: normal; color: var(--ink-subtle); letter-spacing: -0.02em; }
    .today-day.today-ov > em { color: var(--ink); }
    /* a label too wide for its cell (large text, narrow phone): every label in the strip goes condensed; a word that
       still does not fit (200 % text) scales the whole strip's text by one factor, --today-fit, set by layout() */
    .today-tight .today-day > em { font-family: var(--font-display); font-stretch: 62%; font-weight: 600; letter-spacing: 0; }
    .today-liq { position: absolute; left: 0; right: 0; bottom: 0; background: var(--today-fill); }
    /* the wave is a mask sliding over a strip as wide as the cell, so nothing it draws reaches past the cell */
    .today-wave {
      position: absolute; left: 0; right: 0; bottom: calc(100% - 1px); height: 7px; background: var(--today-fill);
      -webkit-mask: ${WAVE} 0 0 / 20px 7px repeat-x; mask: ${WAVE} 0 0 / 20px 7px repeat-x;
      animation: today-wave 5s linear infinite;
    }
    .today-day:nth-child(2n) .today-wave { animation-duration: 6.2s; animation-delay: -1.3s; }
    .today-day:nth-child(3n) .today-wave { animation-duration: 5.6s; animation-delay: -2.7s; }
    @keyframes today-wave { to { -webkit-mask-position: -40px 0; mask-position: -40px 0; } }
    @media (prefers-reduced-motion: reduce) { .today-wave { animation: none; } }
    .today-bud { position: absolute; left: 0; right: 0; z-index: 1; border-top: 1px dashed var(--ink-subtle); }
    @media (max-width: 330px) { .today-days { gap: 3px; padding: 12px 8px 0; } }

    .today-frame { position: relative; margin: 8px 20px 0; height: calc(12.25rem + 50px); }
    .today-ring { position: absolute; left: 50%; top: 25px; width: min(12.25rem, 100%); aspect-ratio: 1; transform: translateX(-50%); }
    .today-ring > svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .today-track, .today-seg { fill: none; stroke-width: 14px; stroke-linecap: butt; }
    .today-track { stroke: var(--surface-3); }
    .today-track.today-full { stroke: color-mix(in oklab, var(--ink) 24%, var(--canvas)); }
    .today-s1 { stroke: var(--today-g1); }
    .today-s3 { stroke: var(--today-g3); }
    .today-ini { position: absolute; transform: translate(-50%, -50%); font: 800 0.6875rem/1 var(--font-sans); pointer-events: none; }
    .today-i1 { color: var(--canvas); }
    .today-i3 { color: var(--ink); }
    .today-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; pointer-events: none; }
    /* sized to the ring by layout(): --today-nfit shrinks the number alone, --today-cfit all three lines */
    .today-num { font-size: calc(2.75rem * var(--today-nfit, 1) * var(--today-cfit, 1)); line-height: 1; letter-spacing: -0.034em; color: var(--primary-display); }
    .today-lbl { margin-top: 3px; font: 600 calc(0.75rem * var(--today-cfit, 1))/1.3 var(--font-sans); color: var(--ink-muted); }
    .today-tot { margin-top: 6px; font: 600 calc(0.75rem * var(--today-cfit, 1))/1.3 var(--font-figure); color: var(--ink-subtle); }
    .today-tot b { color: var(--ink); font-weight: 700; }
    /* half the frame until layout() lets a corner take what its row neighbour leaves, so names stay whole */
    .today-corner {
      position: absolute; max-width: calc(50% - 4px); padding: 0; border: 0; background: none; text-align: left;
      display: flex; flex-direction: column; align-items: flex-start; font: 600 0.75rem/1.3 var(--font-sans); color: var(--ink-muted);
    }
    .today-tl { left: 0; top: 0; } .today-tr { right: 0; top: 0; } .today-br { right: 0; bottom: 0; } .today-bl { left: 0; bottom: 0; }
    .today-tr, .today-br { align-items: flex-end; text-align: right; }
    .today-cn { display: flex; align-items: center; gap: 4px; max-width: 100%; }
    .today-cn > span { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .today-sw { flex: none; width: 1rem; height: 1rem; border-radius: 50%; display: grid; place-items: center; font: 800 0.625rem/1 var(--font-sans); font-style: normal; }
    .today-ck { font: 700 1.1875rem/1.15 var(--font-figure); color: var(--ink); }
    .today-fs { display: flex; margin-top: 4px; }
    .today-fs > span { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--surface-2); border: 2px solid var(--canvas); }
    .today-fs > span + span { margin-left: -8px; }
    .today-fs svg { width: 24px; height: 24px; }
    .today-fs > .today-more { font: 700 0.625rem/1 var(--font-figure); color: var(--ink-muted); }
    .today-addm { width: 30px; height: 30px; margin-top: 4px; border-radius: 50%; border: 1.5px dashed var(--hairline-strong); display: grid; place-items: center; color: var(--ink-muted); }
    .today-addm svg.i { width: 16px; height: 16px; }

    .today-mac { margin: 12px 20px 0; }
    .today-mh { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 0 12px; margin-bottom: 8px; }
    .today-fig { font: 600 0.75rem/1.3 var(--font-figure); color: var(--ink-subtle); }
    .today-bars { display: flex; gap: 4px; }
    /* no padding on the bar itself, so its width is exactly its share; a percentage too wide for its bar moves under it */
    .today-bar {
      position: relative; flex: 1 1 0; min-width: 0; min-height: 30px; border-radius: 8px; display: flex; align-items: center;
      font: 700 0.8125rem/1.2 var(--font-figure); white-space: nowrap; overflow: hidden;
    }
    .today-pct { padding: 0 8px; }
    .today-bar.today-none { background: var(--surface-3); }
    /* a hidden percentage keeps its box inside its bar or label, so nothing hidden reaches past the screen's edge */
    .today-bar.today-out .today-pct { position: absolute; left: 0; max-width: 100%; visibility: hidden; }
    .today-lpct { position: absolute; left: 0; top: 0; max-width: 100%; visibility: hidden; color: var(--ink); font-family: var(--font-figure); font-weight: 700; }
    .today-labs > .today-out .today-lpct { position: static; visibility: visible; }
    /* each label is as wide as its words; layout() sets the margins that start it under its bar */
    .today-labs { display: flex; }
    .today-labs > div { position: relative; flex: none; width: max-content; }
    .today-lab { display: block; margin-top: 4px; font: 600 0.75rem/1.3 var(--font-sans); color: var(--ink-muted); white-space: nowrap; }
    .today-g { display: block; font: 500 0.75rem/1.3 var(--font-figure); color: var(--ink-subtle); white-space: nowrap; }
    .today-g > span { white-space: nowrap; }
    /* two lines when one cannot start every label at its bar: the name over its %, grams eaten over the target */
    .today-labs.today-wrap > div { width: min-content; }
    .today-labs.today-wrap .today-lab, .today-labs.today-wrap .today-g { white-space: normal; }
    /* still wider than the row (page zoom and large text together): a third each, a word breaks rather than overflow */
    .today-labs.today-free { gap: 0.75rem; }
    .today-labs.today-free > div { flex: 1 1 0; width: auto; min-width: 0; overflow-wrap: anywhere; }

    .today-eaten { margin-top: 16px; }
    .today-eaten .rows { margin: 0; }
    .today-food { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--surface-2); }
    .today-food svg { width: 32px; height: 32px; }

    .today-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 24px 28px; }
    .today-empty svg { width: 132px; height: 132px; }
    .today-empty h2 { margin: 10px 0 0; font: var(--display-weight) 1.625rem/1.06 var(--font-display); font-stretch: var(--display-stretch); letter-spacing: -0.017em; }
    .today-empty p { margin: 8px 0 0; max-width: 22rem; font: 500 0.875rem/1.5 var(--font-sans); color: var(--ink-muted); }
    .today-empty p b { color: var(--primary-text); font-weight: 700; }
    .today-empty .btn { margin-top: 18px; }
    /* base.css's section class .sec also matches the secondary button .btn.sec and gives it section margins */
    [data-screen="today"] .bottom .btn.sec { margin: 0; }
    /* Add to <meal> stays one line beside Scan, as drawn. When its words would wrap (large text, narrow phone) it drops
       its + and narrows its padding; words that still wrap shrink by one factor, --today-afit, set by layout() */
    [data-screen="today"] .bottom .btn { min-width: 0; }
    .today-al { min-width: 0; font-size: calc(1em * var(--today-afit, 1)); }
    [data-screen="today"] .bottom.today-narrow .btn { padding-left: 10px; padding-right: 10px; }
    [data-screen="today"] .bottom.today-narrow .btn svg.i { display: none; }
  `);

  // ── days: the phone's local calendar, never UTC ──
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate() + n); return iso(d); };
  const isDate = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && iso(parse(s)) === s;
  const short = s => `${Number(s.slice(8))} ${MONTH[Number(s.slice(5, 7)) - 1]}`;
  const signed = v => (v > 0 ? '+' : v < 0 ? '−' : '') + P.fmt(Math.abs(v));
  const drawing = (food, size) => (window.PantryDrawing ? window.PantryDrawing(food || { name: '' }, size) : '');

  // ── the ring ──
  // [start, end] in degrees per meal: null when nothing was eaten, or when over budget the meal starts past a full turn.
  function arcs(kcals, budget, over) {
    let end = -Infinity;
    const spans = kcals.map((k, i) => {
      if (!(k > 0)) return null;
      const s = Math.max(QUARTER[i], end), e = s + k / budget * 360;
      end = e;
      return [s, e];
    });
    let limit = FULL;
    for (let i = spans.length - 1; i >= 0; i -= 1) {
      const sp = spans[i];
      if (!sp) continue;
      if (over) {
        if (sp[0] >= FULL) spans[i] = null; else sp[1] = Math.min(sp[1], FULL);
      } else if (sp[1] > limit) {
        const back = sp[1] - limit;
        sp[0] -= back; sp[1] -= back;
      }
      if (spans[i]) limit = sp[0];
    }
    return spans;
  }

  const f2 = v => v.toFixed(2);
  const pt = a => { const r = a * Math.PI / 180; return [MID + RADIUS * Math.sin(r), MID - RADIUS * Math.cos(r)]; };
  // One subpath; past half a turn it is drawn as two arcs, so a full circle stays one dashable line.
  function arc(a0, a1) {
    const [x0, y0] = pt(a0);
    const to = a => { const [x, y] = pt(a); return `A${RADIUS} ${RADIUS} 0 0 1 ${f2(x)} ${f2(y)}`; };
    return `M${f2(x0)} ${f2(y0)}${a1 - a0 > 180 ? to((a0 + a1) / 2) : ''}${to(a1)}`;
  }

  function ring(kcals, eaten, budget) {
    const over = eaten > budget;
    const spans = arcs(kcals, budget, over);
    const gap = RADIUS * GAP * Math.PI / 180;
    let paths = over ? `<path class="today-track today-full" d="${arc(-90, FULL)}"/>`
      : QUARTER.map(q => `<path class="today-track" d="${arc(q + 3, q + 87)}"/>`).join('');
    let initials = '';
    spans.forEach((sp, i) => {
      if (!sp) return;
      const [s, e] = sp, len = RADIUS * (e - s) * Math.PI / 180;
      const shown = len - 2 * gap > 2 ? len - 2 * gap : Math.min(len, 2);
      paths += `<path class="today-seg ${i % 2 ? 'today-s3' : 'today-s1'}" data-meal="${MEALS[i]}" d="${arc(s, e)}"`
        + ` stroke-dasharray="0 ${f2((len - shown) / 2)} ${f2(shown)} ${f2(len + 1)}"/>`;
      if (e - s > 14) {
        const [x, y] = pt((s + e) / 2);
        initials += `<span class="today-ini ${i % 2 ? 'today-i3' : 'today-i1'}" style="left:${f2(x / SIZE * 100)}%;top:${f2(y / SIZE * 100)}%"`
          + ` aria-hidden="true">${NAME[MEALS[i]][0]}</span>`;
      }
    });
    const left = budget - eaten;
    return `<div class="today-ring"><svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${P.fmt(eaten)} of ${P.fmt(budget)} kcal">${paths}</svg>${initials}
      <div class="today-center"><span class="today-num disp" data-test="kcal-left">${P.fmt(Math.abs(left))}</span>
        <span class="today-lbl">${left < 0 ? 'kcal over' : 'kcal left'}</span>
        <span class="today-tot"><b>${P.fmt(eaten)}</b> / ${P.fmt(budget)}</span></div></div>`;
  }

  function corner(i, list, kcal, foods) {
    const meal = MEALS[i], right = i === 1 || i === 2;
    const sw = `<i class="today-sw ${i % 2 ? 'today-t3' : 'today-t1'}" aria-hidden="true">${NAME[meal][0]}</i>`;
    const label = `<span class="today-cn">${right ? '' : sw}<span>${NAME[meal]}</span>${right ? sw : ''}</span>`;
    const open = `<button class="today-corner ${CORNER[i]}" type="button" data-meal="${meal}"`;
    if (!list.length) return `${open} aria-label="Add to ${meal}">${label}<span class="today-addm" aria-hidden="true">${P.icon('plus')}</span></button>`;
    const ids = [...new Set(list.map(e => e.foodId))];
    const shown = ids.length > 3 ? ids.slice(0, 2) : ids;
    const art = shown.map(id => `<span>${drawing(foods.get(id), 24)}</span>`).join('')
      + (ids.length > shown.length ? `<span class="today-more">+${ids.length - shown.length}</span>` : '');
    return `${open} aria-label="${NAME[meal]}, ${P.fmt(kcal)} kcal">${label}<b class="today-ck">${P.fmt(kcal)}</b>`
      + `<span class="today-fs" aria-hidden="true">${art}</span></button>`;
  }

  function macros(entries, targets, budget) {
    const sum = P.sum(entries);
    const pcts = [targets.proteinPct ?? 20, targets.carbsPct ?? 45, targets.fatPct ?? 35];
    const kcal = MACROS.map(([k, , per]) => (sum[k] || 0) * per);
    const total = kcal.reduce((a, b) => a + b, 0);
    const bars = MACROS.map((_, i) => {
      if (!total) return `<span class="today-bar today-none" style="flex-grow:${pcts[i]}"></span>`;
      const share = kcal[i] / total * 100;
      return `<span class="today-bar ${i % 2 ? 'today-t3' : 'today-t1'}" style="flex-grow:${share}">`
        + `<span class="today-pct">${Math.round(share)}%</span></span>`;
    }).join('');
    const labels = MACROS.map(([k, name, per], i) => {
      const grams = sum[k] === undefined ? (entries.length ? '–' : '0') : P.fmt(sum[k]);
      const pct = total ? `<span class="today-lpct"> ${Math.round(kcal[i] / total * 100)}%</span>` : '';
      return `<div><span class="today-lab">${name}${pct}</span>`
        + `<span class="today-g"><span>${grams} /</span> <span>${P.fmt(budget * pcts[i] / 100 / per)} g</span></span></div>`;
    }).join('');
    return `<section class="today-mac" aria-label="Calories from protein, carbs and fat">
      <div class="today-mh"><h2 class="eyebrow">Calories from</h2><span class="today-fig">target ${pcts.join(' / ')}%</span></div>
      <div class="today-bars">${bars}</div><div class="today-labs">${labels}</div></section>`;
  }

  function strip(days, kcalOn, now, date, budget) {
    const scale = Math.max(2750, 1.25 * budget);
    const cells = days.map(d => {
      const kcal = kcalOn.get(d), isNow = d === now, over = !isNow && Math.round(kcal) > budget;
      const diff = Math.round(kcal) - budget;
      const label = isNow ? 'today' : signed(diff);
      const said = kcal ? `${P.fmt(kcal)} kcal, ${diff > 0 ? `${P.fmt(diff)} over` : `${P.fmt(-diff)} under`}` : 'nothing logged';
      const liquid = kcal > 0 ? `<i class="today-liq" style="height:${f2(Math.min(100, kcal / scale * 100))}%" aria-hidden="true">`
        + '<i class="today-wave"></i></i>' : '';
      return `<button class="today-day${d === date ? ' today-on' : ''}${over ? ' today-ov' : ''}" type="button" data-day="${d}"`
        + `${d === date ? ' aria-current="date"' : ''} aria-label="${P.dayLabel(d)}${isNow ? ', today' : ''}: ${said}">${liquid}`
        + `<i class="today-bud" style="bottom:${f2(budget / scale * 100)}%" aria-hidden="true"></i>`
        + `<span aria-hidden="true">${DAY[parse(d).getDay()]}</span><b aria-hidden="true">${Number(d.slice(8))}</b>`
        + `<em aria-hidden="true">${label}</em></button>`;
    }).join('');
    return `<nav class="today-days${slide ? ' ' + slide : ''}" aria-label="Days">${cells}</nav>`;
  }

  function syncBanner(text) {
    const cut = text.indexOf('. ');
    const body = cut > 0 ? `<b>${P.esc(text.slice(0, cut + 1))}</b>${P.esc(text.slice(cut + 1))}` : P.esc(text);
    return `<div class="banner" role="status">${P.icon('alert')}<div>${body}</div></div>`;
  }

  // ── the screen ──
  let root = null;
  let pinned = null;       // the date shown when it is not today; null follows the clock
  let stripEnd = null;     // the last day in the strip
  let drawnToday = null;
  let slide = '';
  let swiped = false;
  let touch = null;
  let watcher = null;

  const shownDate = () => pinned || P.today();

  function draw() {
    const doc = P.doc(), now = P.today(), date = shownDate(), isToday = date === now;
    if (drawnToday !== now) { drawnToday = now; stripEnd = null; }
    if (!stripEnd) stripEnd = date;
    const budget = doc.settings.targets.kcal;
    const foods = new Map(doc.foods.map(f => [f.id, f]));
    const days = Array.from({ length: 7 }, (_, i) => addDays(stripEnd, i - 6));
    const kcalOn = new Map(days.map(d => [d, 0]));
    const entries = [];
    for (const e of doc.entries) {
      if (kcalOn.has(e.date)) kcalOn.set(e.date, kcalOn.get(e.date) + e.totals.kcal);
      if (e.date === date) entries.push(e);
    }
    const problem = P.problem(), syncError = P.syncState().lastError;
    const banner = problem ? `<div class="banner" role="alert">${P.icon('alert')}<div>${P.esc(problem)}</div></div>`
      : typeof syncError === 'string' && syncError.trim() ? syncBanner(syncError.trim()) : '';
    const first = !problem && doc.entries.length === 0;
    const meal = P.mealNow();
    const add = isToday ? `Add to ${meal}` : 'Add to this day';
    const year = date.slice(0, 4) === now.slice(0, 4) ? '' : ` ${date.slice(0, 4)}`;

    const head = `<header class="top today-top"><div><p class="eyebrow">${P.dayLabel(date)}${year}</p>`
      + `<h1 class="title">${isToday ? 'Today' : short(date)}</h1></div>`
      + `<button class="ibtn" type="button" data-act="settings" aria-label="Settings">${GEAR}</button></header>`;
    const bottom = `<div class="bottom"><button class="btn${first ? ' sec' : ''}" type="button" data-act="add" data-for="${meal}"`
      + ` aria-label="${add.replace('Add', 'Add food')}">${P.icon('plus')}<span class="today-al">${add}</span></button>`
      + `<button class="ibtn box" type="button" data-act="scan" data-for="${meal}" aria-label="Scan a barcode">${P.icon('scan')}</button></div>`;

    if (first) {
      root.innerHTML = `${head}${banner}<section class="today-empty">${window.PantryDrawing ? window.PantryDrawing.named('plate', 132) : ''}
        <h2>An empty plate.</h2>
        <p><b data-test="kcal-left">${P.fmt(budget)}</b> kcal left today. Bring your MyNetDiary history in once, or scan your first product. Your frequent foods grow from here.</p>
        <button class="btn" type="button" data-act="import">Import MyNetDiary history</button></section>${bottom}`;
      layout();
      watch();
      return;
    }

    const perMeal = MEALS.map(m => entries.filter(e => e.meal === m));
    const mealKcal = perMeal.map(list => list.reduce((a, e) => a + e.totals.kcal, 0));
    const eaten = Math.round(mealKcal.reduce((a, b) => a + b, 0));
    const ordered = isToday ? [...entries].reverse() : perMeal.flat();
    const rows = ordered.map(e => {
      const food = foods.get(e.foodId);
      return `<li><button class="fr" type="button" data-entry="${P.esc(e.id)}"><span class="today-food" aria-hidden="true">${drawing(food, 32)}</span>`
        + `<span class="t"><span class="name">${P.esc(food ? food.name : 'A food no longer in your list')}</span>`
        + `<span class="sub">${NAME[e.meal]}, ${P.esc(e.amount)}</span></span><span class="k">${P.fmt(e.totals.kcal)}</span></button></li>`;
    }).join('');

    root.innerHTML = `${head}${strip(days, kcalOn, now, date, budget)}${banner}
      <div class="today-frame">${ring(mealKcal, eaten, budget)}${MEALS.map((m, i) => corner(i, perMeal[i], mealKcal[i], foods)).join('')}</div>
      ${macros(entries, doc.settings.targets, budget)}
      <section class="sec today-eaten"><h2 class="eyebrow">${isToday ? 'Eaten today' : 'Eaten that day'}</h2>
        ${rows ? `<ul class="rows">${rows}</ul>` : `<p class="note">Nothing logged ${isToday ? 'yet today' : 'that day'}.</p>`}</section>
      ${bottom}`;
    layout();
    watch();
  }

  // Macro labels: each starts where its bar starts, at least 0.75rem (one em of its text) from the next and never past
  // the row. When one line per label cannot do that, two lines; a label that still meets its neighbour or the row's end
  // moves only as far as it must (one wider than the last bar ends where the row ends).
  function placeLabels(labs, bars) {
    const cols = [...labs.children];
    labs.classList.remove('today-wrap', 'today-free');
    cols.forEach(c => c.style.removeProperty('margin-left'));
    const row = labs.getBoundingClientRect();
    const sep = 0.75 * parseFloat(getComputedStyle(document.documentElement).fontSize);
    const starts = bars.map(b => b.getBoundingClientRect().left - row.left);
    const plan = () => {
      const w = cols.map(c => c.getBoundingClientRect().width), s = [];
      let end = -Infinity;
      w.forEach((wi, i) => { s[i] = Math.max(starts[i], end + sep); end = s[i] + wi; });
      let limit = row.width;
      for (let i = w.length - 1; i >= 0; i -= 1) { s[i] = Math.min(s[i], limit - w[i]); limit = s[i] - sep; }
      // a start within the 4 px gap before its bar still reads as under it
      return { w, s, fits: s[0] >= -0.5, aligned: s.every((x, i) => Math.abs(x - starts[i]) <= 4) };
    };
    let p = plan();
    if (!p.aligned) { labs.classList.add('today-wrap'); p = plan(); }
    if (!p.fits) { labs.classList.add('today-free'); return; }
    p.s.forEach((x, i) => { cols[i].style.marginLeft = `${x - (i ? p.s[i - 1] + p.w[i - 1] : 0)}px`; });
  }

  // Add to <meal> on one line: without its + and with narrow padding when its words would wrap, then smaller words.
  function fitAdd(bar) {
    const label = bar.querySelector('.today-al');
    if (!label) return;
    bar.classList.remove('today-narrow');
    bar.style.removeProperty('--today-afit');
    const wraps = () => label.getBoundingClientRect().height > 1.5 * parseFloat(getComputedStyle(label).lineHeight);
    if (!wraps()) return;
    bar.classList.add('today-narrow');
    if (!wraps()) return;
    const btn = label.parentElement, s = getComputedStyle(btn);
    const room = btn.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
    label.style.whiteSpace = 'nowrap';
    const need = label.getBoundingClientRect().width;
    label.style.removeProperty('white-space');
    let fit = Math.min(1, Math.floor(100 * room / need) / 100);
    bar.style.setProperty('--today-afit', String(fit));
    while (wraps() && fit > 0.5) { fit = Math.round(100 * fit - 2) / 100; bar.style.setProperty('--today-afit', String(fit)); }
  }

  // The centre inside the ring's inner edge: the ring stops growing at the frame's width while rem text keeps growing.
  // The number shrinks first, down to twice the size of the words under it; then all three lines shrink together. A
  // shrunk line's farthest box corner lands at least that factor closer, so the first guess is never too small.
  function fitCentre(ringEl) {
    const lines = [...ringEl.querySelectorAll('.today-center > span')];
    ringEl.style.removeProperty('--today-nfit');
    ringEl.style.removeProperty('--today-cfit');
    const r = ringEl.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const inner = r.width * (RADIUS - 7) / SIZE;       // the stroke is 14 wide around RADIUS
    const reach = () => Math.max(...lines.map(el => { const b = el.getBoundingClientRect();
      return Math.hypot(Math.max(cx - b.left, b.right - cx), Math.max(cy - b.top, b.bottom - cy)); }));
    const shrink = (name, floor) => {
      let far = reach();
      if (far <= inner) return true;
      let f = Math.max(floor, Math.floor(100 * inner / far) / 100);
      for (;;) {
        ringEl.style.setProperty(name, String(f));
        far = reach();
        if (far <= inner || f <= floor) return far <= inner;
        f = Math.max(floor, Math.round(100 * f - 1) / 100);
      }
    };
    if (!shrink('--today-nfit', 0.55)) shrink('--today-cfit', 0.3);
  }

  // Fits Today to the text size and width: the strip's words in their days, the macro labels under their bars, Add on
  // one line beside Scan, whole corner names, the centre inside the ring, and the lowest frame that keeps each corner's
  // name and kcal off the ring's box and its drawings off the ring.
  function layout() {
    if (!root || !root.isConnected) return;
    const days = root.querySelector('.today-days');
    if (days) {
      days.classList.remove('today-tight');
      days.style.removeProperty('--today-fit');
      const words = [...days.querySelectorAll('.today-day > span, .today-day > b, .today-day > em')];
      const over = el => el.getBoundingClientRect().width / (el.parentElement.clientWidth - 2);
      if (words.some(el => el.tagName === 'EM' && over(el) > 1)) days.classList.add('today-tight');
      const worst = Math.max(1, ...words.map(over));
      if (worst > 1) days.style.setProperty('--today-fit', String(Math.floor(100 / worst) / 100));
    }
    const labs = root.querySelector('.today-labs');
    const labels = labs ? [...labs.children] : [];
    const bars = [...root.querySelectorAll('.today-bar')];
    [...bars, ...labels].forEach(el => el.classList.remove('today-out'));
    const outs = bars.map(bar => { const pct = bar.querySelector('.today-pct'); return !!pct && pct.getBoundingClientRect().width > bar.clientWidth; });
    outs.forEach((out, i) => {
      bars[i].classList.toggle('today-out', out);
      if (labels[i]) labels[i].classList.toggle('today-out', out);
    });
    if (labs) placeLabels(labs, bars);
    const bar = root.querySelector('.bottom');
    if (bar) fitAdd(bar);
    const frame = root.querySelector('.today-frame');
    if (!frame) return;
    const ringEl = frame.querySelector('.today-ring');
    fitCentre(ringEl);
    const box = frame.getBoundingClientRect();
    const W = box.width, S = ringEl.getBoundingClientRect().width;
    // corners in one row share its width: a short name leaves the rest to its neighbour, both 8 px apart
    const els = [...frame.querySelectorAll('.today-corner')];
    els.forEach(el => { el.style.maxWidth = 'none'; });
    const natural = els.map(el => el.getBoundingClientRect().width);
    [[0, 1], [3, 2]].forEach(([a, b]) => {
      const room = W - 8, half = room / 2;
      let wa = natural[a], wb = natural[b];
      if (wa + wb > room) {
        if (wa <= half) wb = room - wa; else if (wb <= half) wa = room - wb; else wa = wb = half;
      }
      els[a].style.maxWidth = `${wa}px`;
      els[b].style.maxWidth = `${wb}px`;
    });
    const x0 = (W - S) / 2, x1 = x0 + S, reach = S * OUTER / SIZE + 4;
    const corners = [...frame.querySelectorAll('.today-corner')].map(el => {
      const c = el.getBoundingClientRect(), top = el.classList.contains('today-tl') || el.classList.contains('today-tr');
      // parts in frame x and in y measured from the frame edge the corner sits on
      const part = p => { const r = p.getBoundingClientRect(); const y = r.top - c.top;
        return { x: r.left - box.left, w: r.width, h: r.height, y: top ? y : c.height - y - r.height }; };
      return { top, h: c.height, words: [...el.querySelectorAll('.today-cn, .today-ck')].map(part), art: [...el.querySelectorAll('.today-fs, .today-addm')].map(part) };
    });
    const clear = (c, t) => {
      const cx = W / 2, cy = t + S / 2;
      return c.words.every(p => p.x >= x1 || p.x + p.w <= x0 || p.y + p.h <= t)
        && c.art.every(p => Math.hypot(Math.min(Math.max(cx, p.x), p.x + p.w) - cx, Math.min(Math.max(cy, p.y), p.y + p.h) - cy) >= reach);
    };
    const gap = group => { let t = 25; while (t < 2000 && !group.every(c => clear(c, t))) t += 1; return t; };
    const top = gap(corners.filter(c => c.top)), bottom = gap(corners.filter(c => !c.top));
    const height = Math.max(top + S + bottom, corners[0].h + corners[3].h + 8, corners[1].h + corners[2].h + 8);
    ringEl.style.top = `${top}px`;
    frame.style.height = `${height}px`;
  }

  // A font arriving late or the phone's text size changing resizes the corners; layout() never resizes them.
  function watch() {
    if (watcher) watcher.disconnect();
    watcher = null;
    const corners = root.querySelectorAll('.today-corner');
    if (!corners.length) return;
    watcher = new ResizeObserver(layout);
    corners.forEach(el => watcher.observe(el));
  }

  function shift(days) {
    const date = shownDate(), now = P.today(), last = date > now ? date : now;
    let end = addDays(stripEnd, days);
    if (end > last) end = last;
    if (end === stripEnd) return;
    stripEnd = end;
    slide = days > 0 ? 'today-from-r' : 'today-from-l';
    draw();
    slide = '';
  }

  function onClick(e) {
    const b = e.target.closest('button');
    if (!b || !root || !root.contains(b)) return;
    const date = shownDate();
    if (b.dataset.day) {
      if (swiped || b.dataset.day === date) return;
      P.go('today', b.dataset.day === P.today() ? undefined : b.dataset.day);
    } else if (b.dataset.meal) P.go('add', b.dataset.meal, date);
    else if (b.dataset.entry) P.go('entry', b.dataset.entry);
    else if (b.dataset.act === 'add') P.go('add', b.dataset.for, date);
    else if (b.dataset.act === 'scan') P.go('scan', b.dataset.for, date);
    else if (b.dataset.act === 'settings' || b.dataset.act === 'import') P.go('settings');
  }

  function render(el, date) {
    root = el;
    pinned = isDate(date) && date !== P.today() ? date : null;
    stripEnd = null;
    el.addEventListener('click', onClick);
    el.addEventListener('pointerdown', e => {
      touch = e.target.closest('.today-days') ? { x: e.clientX, y: e.clientY, id: e.pointerId } : null;
    });
    el.addEventListener('pointerup', e => {
      if (!touch || e.pointerId !== touch.id) return;
      const dx = e.clientX - touch.x, dy = e.clientY - touch.y;
      touch = null;
      if (Math.abs(dx) >= 40 && Math.abs(dx) > 1.5 * Math.abs(dy)) {
        // the click a mouse drag ends with is part of the swipe, not a tap on a day
        swiped = true;
        setTimeout(() => { swiped = false; }, 400);
        shift(dx < 0 ? 7 : -7);
      }
    });
    el.addEventListener('pointercancel', () => { touch = null; });
    draw();
  }

  window.addEventListener('resize', () => { if (root && root.isConnected) layout(); });
  if (document.fonts) document.fonts.addEventListener('loadingdone', () => { if (root && root.isConnected) layout(); });
  P.view('today', {
    render,
    update() { if (root && root.isConnected) draw(); },
    leave() { if (watcher) watcher.disconnect(); watcher = null; root = null; },
  });
})();

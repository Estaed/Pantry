/* Today: the day at a glance (design/screens.html: 1. Today, 7. A past day, First launch, Sync failed).
   Route `today [date]`: no date, a date that is not YYYY-MM-DD, or today's date shows Today and follows the clock past
   midnight; any other date shows that day ("8 Aug").

   Top to bottom: the date with Settings (a past day adds a Today action); the day strip, seven days ending at the shown
   day, each a tank filled to its kcal on a scale of max(2,750, 1.25 x budget) with a slow wave on top, the dashed budget
   line and the difference to budget (a swipe moves it a week, the shown day stays); the ring with the four meals in the
   corners; the macro strip in Pantry.MACROS order, carbs, protein, fat (each macro's width is its share of carbs x 4 +
   protein x 4 + fat x 9); what was eaten; Add to <meal> and Scan.

   Ring (G3): a meal's arc is its kcal / budget x 360 degrees. It starts in its own quarter (breakfast at 9 o'clock,
   lunch at 12, dinner at 3, snacks at 6) or where the meal before it ended, whichever is later, and runs on. Under
   budget a tail that would pass 9 o'clock again is pulled back into free space; over budget the ring is full and the
   tail stops at 9 o'clock. Each arc's path holds its exact angles; the gap between neighbours is the dash pattern.

   Budget status (Blueprint, Decisions 2026-10-21): within budget the screen keeps its calm greys with the orange answer.
   Once the kcal eaten, rounded as shown, passes the budget, the ring, its swatches, the kcal-left number (then "kcal
   over") and the day's tank in the strip take the over tone: the base's chart-5 violet, the only base hue that is
   neither the orange accent (the warm status tokens sit within 0.05-0.08 OKLab of it) nor MyNetDiary's green or red.
   Each macro bar turns on its own when its grams, rounded as shown, pass its target; a day with nothing logged stays
   neutral. The tones are the custom properties below, built from tokens.css only.

   Days in place: a tap on a day in the strip, a swipe on the ring (left: the next day, right: the one before; nothing
   after today) or the Today action switches the shown day without a new screen. The strip stays where it is; it moves a
   week only when the shown day leaves it. The first switch pushes one history entry with the same address and
   `state.day` (null for today); later switches replace it, and a switch back to the day under it pops it, so Back
   returns to the day shown before the first switch. This file never changes location.hash.

   Motion (base Motion, tokens.css): coming back to a day whose drawn values changed (a log, an edit, an Undo), the arcs
   that changed move from their old ends, the bars and the day's tank move to their new values, the corner kcal and the
   eaten total swap, each bar's percentage and grams swap after their bar, and the kcal-left number swaps last; the over
   tone lands with it. What changed is found by
   comparing the values drawn last, so a redraw for another reason never replays it. Numbers never count up. Reduced
   motion: the chart is drawn at once and the numbers only crossfade. A day switch fades the content in; a ring swipe
   brings it from the side it was pushed to. Every frame is computed from performance.now() in requestAnimationFrame,
   so the page clock drives it; data-motion on the screen names the motion while one runs.

   layout() places the ring between the corners so no meal name or kcal touches the ring's box and no drawing touches
   the ring, and keeps the centre's words inside the ring, at any text size and width. Gate hooks: data-test="kcal-left"; .top .eyebrow; eaten rows .fr with
   .name/.sub; one .banner; the buttons "Add food" (the floating +, accessible name "Add food to <meal>" or "Add food to this day") and
   "Scan a barcode".

   First launch differs from design/screens.html (First launch) only to keep those hooks: the gate opens an empty log,
   reads "2,200" from kcal-left and taps "Add food" and "Scan a barcode" there, so the sentence starts with
   "2,200 kcal left today." and the floating + and Scan stand in for the secondary "Scan a product"
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
  const MACRO = { carbs: ['Carbs', 4, 45], protein: ['Protein', 4, 20], fat: ['Fat', 9, 35] };   // name, kcal per g, target % unset
  const MACROS = P.MACROS.map(k => [k, ...MACRO[k]]);
  const SHIFT = 24;                                   // px: the farthest anything travels (base Motion)
  // one period of the design's wave (M0 3 Q5 0 10 3 T20 3, closed below), tiled along the top of each day's fill
  const WAVE = 'url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 20 7%27 preserveAspectRatio=%27none%27%3E%3Cpath d=%27M0 3Q5 0 10 3T20 3V7H0Z%27/%3E%3C/svg%3E")';
  const GEAR = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';

  P.css(`
    [data-screen="today"] {
      --today-g1: var(--ink); --today-g3: color-mix(in oklab, var(--ink) 40%, var(--canvas));
      /* over budget: the base palette's chart-5 violet, a full step and a half step as G3 has them in grey */
      --today-over: var(--chart-5);
      --today-o1: var(--today-over); --today-o3: color-mix(in oklab, var(--today-over) 50%, var(--canvas));
      --today-c1: var(--today-g1); --today-c3: var(--today-g3); --today-cn: var(--primary-display); }
    .today-frame.today-over, .today-bar.today-bo { --today-c1: var(--today-o1); --today-c3: var(--today-o3); --today-cn: var(--today-over); }
    .today-top > div { flex: 1; }
    .today-now {
      flex: none; min-width: 44px; min-height: 44px; padding: 8px 6px; border: 0; border-radius: var(--r-md);
      background: none; color: var(--ink); font: 600 0.875rem/1.2 var(--font-sans);
    }
    .today-t1 { background: var(--today-c1); color: var(--canvas); }
    .today-t3 { background: var(--today-c3); color: var(--ink); }

    /* the browser's own sideways scroll: it follows the finger, a flick runs on and stops on a day; seven days to a
       screen (100cqi is the strip's width inside its side margins) */
    .today-days {
      --today-side: 14px; --today-gap: 5px; display: flex; gap: var(--today-gap); padding: 12px var(--today-side) 0;
      overflow-x: auto; overscroll-behavior-x: contain; scroll-snap-type: x mandatory; scroll-padding-inline: var(--today-side);
      scrollbar-width: none; container-type: inline-size;
    }
    .today-days::-webkit-scrollbar { display: none; }
    .today-day {
      --today-fill: color-mix(in oklab, var(--ink) 13%, transparent);
      /* tall enough, and the words low enough, that the dashed budget line stays above them at any text size */
      flex: 0 0 calc((100cqi - 6 * var(--today-gap)) / 7); scroll-snap-align: start; min-height: 4.625rem; padding: 6px 0 7px; position: relative; overflow: hidden;
      display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
      border-radius: 14px; background: var(--surface-1); border: 1px solid var(--hairline);
      font: 600 calc(0.6875rem * var(--today-fit, 1))/1.25 var(--font-sans); color: var(--ink-muted);
    }
    .today-day.today-on { --today-fill: color-mix(in oklab, var(--primary) 20%, transparent); border: 1.5px solid var(--ink); }
    .today-day.today-ov, .today-day.today-on.today-ov { --today-fill: color-mix(in oklab, var(--today-over) 45%, transparent); }
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
    @media (max-width: 330px) { .today-days { --today-side: 8px; --today-gap: 3px; } }

    /* pan-y: a vertical drag on the ring scrolls the page, a sideways one is the day swipe */
    .today-frame { position: relative; margin: 8px 20px 0; height: calc(12.25rem + 50px); touch-action: pan-y; }
    .today-ring { position: absolute; left: 50%; top: 25px; width: min(12.25rem, 100%); aspect-ratio: 1; transform: translateX(-50%); }
    .today-ring > svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .today-track, .today-seg { fill: none; stroke-width: 14px; stroke-linecap: butt; }
    .today-track { stroke: var(--surface-3); }
    .today-track.today-full { stroke: color-mix(in oklab, var(--today-over) 28%, var(--canvas)); }
    .today-s1 { stroke: var(--today-c1); }
    .today-s3 { stroke: var(--today-c3); }
    .today-ini { position: absolute; transform: translate(-50%, -50%); font: 800 0.6875rem/1 var(--font-sans); pointer-events: none; }
    .today-i1 { color: var(--canvas); }
    .today-i3 { color: var(--ink); }
    .today-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; pointer-events: none; }
    /* sized to the ring by layout(): --today-nfit shrinks the number alone, --today-cfit all three lines */
    .today-num, .today-gnum { font-size: calc(2.75rem * var(--today-nfit, 1) * var(--today-cfit, 1)); line-height: 1; letter-spacing: -0.034em; color: var(--today-cn); }
    .today-lbl, .today-glbl { margin-top: 3px; font: 600 calc(0.75rem * var(--today-cfit, 1))/1.3 var(--font-sans); color: var(--ink-muted); }
    .today-tot, .today-gtot { margin-top: 6px; font: 600 calc(0.75rem * var(--today-cfit, 1))/1.3 var(--font-figure); color: var(--ink-subtle); }
    .today-tot b, .today-gtot b { color: var(--ink); font-weight: 700; }
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
    .today-ck, .today-gck { font: 700 1.1875rem/1.15 var(--font-figure); color: var(--ink); }
    .today-fs { display: flex; margin-top: 4px; }
    .today-fs > span { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; flex: none; background: var(--surface-2); border: 2px solid var(--canvas); }
    .today-fs > span + span { margin-left: -8px; }
    .today-fs svg { width: 24px; height: 24px; }
    .today-fs > .today-more { font: 700 0.625rem/1 var(--font-figure); color: var(--ink-muted); }
    .today-addm { width: 30px; height: 30px; margin-top: 4px; border-radius: 50%; border: 1.5px dashed var(--hairline-strong); display: grid; place-items: center; color: var(--ink-muted); }
    .today-addm svg.i { width: 16px; height: 16px; }
    /* the old value of a number while it swaps (motion only): over the new one, never in the screen's text */
    .today-ghost { position: absolute; margin: 0; pointer-events: none; white-space: nowrap; font-style: normal; }

    .today-mac { margin: 12px 20px 0; }
    .today-mh { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 0 12px; margin-bottom: 8px; }
    .today-fig { font: 600 0.75rem/1.3 var(--font-figure); color: var(--ink-subtle); }
    .today-bars { display: flex; gap: 4px; }
    /* no padding on the bar itself, so its width is exactly its share; a percentage too wide for its bar moves under it */
    .today-bar {
      position: relative; flex: 1 1 0; min-width: 0; min-height: 30px; border-radius: 8px; display: flex; align-items: center;
      font: 700 0.8125rem/1.2 var(--font-figure); white-space: nowrap; overflow: hidden;
    }
    .today-pct, .today-gpct { padding: 0 8px; }
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
    /* inline-block, as the base numberSwap makes a number it swaps: a transform skips an inline box */
    .today-g > span, .today-lpn { display: inline-block; white-space: nowrap; }
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
    /* Add and Scan float at the bottom right over the screen, as in MyNetDiary (design/deviations.md): a 56 px + with
       Scan beside it; the band behind them lets the rows show through */
    .today-fab { justify-content: flex-end; background: none; pointer-events: none; }
    .today-fab > * { pointer-events: auto; }
    .today-fab .btn { flex: none; width: 56px; height: 56px; min-height: 0; padding: 0; margin: 0; box-shadow: var(--shadow-3); }
    .today-fab .btn svg.i { width: 26px; height: 26px; }
  `);

  // ── days: the phone's local calendar, never UTC ──
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate() + n); return iso(d); };
  const isDate = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && iso(parse(s)) === s;
  const short = s => `${Number(s.slice(8))} ${MONTH[Number(s.slice(5, 7)) - 1]}`;
  const signed = v => (v > 0 ? '+' : v < 0 ? '−' : '') + P.fmt(Math.abs(v));
  const whole = v => Math.round(Number(v.toPrecision(12)));     // a number as P.fmt shows it
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

  // The track and the meals' arcs as SVG, and the initials over them; the motion draws its frames with it too.
  function ringParts(spans, over) {
    const gap = RADIUS * GAP * Math.PI / 180;
    let paths = over ? `<path class="today-track today-full" d="${arc(-90, FULL)}"/>`
      : QUARTER.map(q => `<path class="today-track" d="${arc(q + 3, q + 87)}"/>`).join('');
    let initials = '';
    spans.forEach((sp, i) => {
      if (!sp || !(sp[1] > sp[0])) return;
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
    return { paths, initials };
  }

  function ring(spans, eaten, budget, over) {
    const { paths, initials } = ringParts(spans, over);
    const left = budget - eaten;
    return `<div class="today-ring"><svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${P.fmt(eaten)} of ${P.fmt(budget)} kcal">${paths}</svg>${initials}
      <div class="today-center"><span class="today-num disp" data-test="kcal-left">${P.fmt(Math.abs(left))}</span>
        <span class="today-lbl">${left < 0 ? 'kcal over' : 'kcal left'}</span>
        <span class="today-tot">${tot(eaten, budget)}</span></div></div>`;
  }
  const tot = (eaten, budget) => `<b>${P.fmt(eaten)}</b> / ${P.fmt(budget)}`;

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

  // The macro strip, and what the motion compares: each bar's flex-grow, which bars are over their target, the grams
  // eaten and the percentage each shows.
  function macros(entries, targets, budget) {
    const sum = P.sum(entries);
    const pcts = MACROS.map(([k, , , unset]) => targets[`${k}Pct`] ?? unset);
    const kcal = MACROS.map(([k, , per]) => (sum[k] || 0) * per);
    const total = kcal.reduce((a, b) => a + b, 0);
    const goal = MACROS.map(([, , per], i) => budget * pcts[i] / 100 / per);
    const over = MACROS.map(([k], i) => sum[k] !== undefined && whole(sum[k]) > whole(goal[i]));
    const grow = total ? kcal.map(k => k / total * 100) : pcts;
    const gram = MACROS.map(([k]) => (sum[k] === undefined ? (entries.length ? '–' : '0') : P.fmt(sum[k])));
    const pct = grow.map(g => (total ? Math.round(g) : null));
    const bars = MACROS.map((_, i) => {
      if (!total) return `<span class="today-bar today-none" style="flex-grow:${grow[i]}"></span>`;
      return `<span class="today-bar ${i % 2 ? 'today-t3' : 'today-t1'}${over[i] ? ' today-bo' : ''}" style="flex-grow:${grow[i]}">`
        + `<span class="today-pct">${pct[i]}%</span></span>`;
    }).join('');
    const labels = MACROS.map(([, name], i) => {
      const under = total ? `<span class="today-lpct"> <span class="today-lpn">${pct[i]}%</span></span>` : '';
      return `<div><span class="today-lab">${name}${under}</span>`
        + `<span class="today-g"><span>${gram[i]} /</span> <span>${P.fmt(goal[i])} g</span></span></div>`;
    }).join('');
    const names = MACROS.map(([, name]) => name.toLowerCase());
    const html = `<section class="today-mac" aria-label="Calories from ${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}">
      <div class="today-mh"><h2 class="eyebrow">Calories from</h2><span class="today-fig">target ${pcts.join(' / ')}%</span></div>
      <div class="today-bars">${bars}</div><div class="today-labs">${labels}</div></section>`;
    return { html, grow, over, gram, pct };
  }

  function strip(days, kcalOn, now, date, budget) {
    return `<nav class="today-days" aria-label="Days">${dayCells(days, kcalOn, now, date, budget)}</nav>`;
  }

  function dayCells(days, kcalOn, now, date, budget) {
    const scale = Math.max(2750, 1.25 * budget);
    return days.map(d => {
      const kcal = kcalOn.get(d), isNow = d === now, over = kcal > 0 && Math.round(kcal) > budget;
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
  }

  function syncBanner(text) {
    const cut = text.indexOf('. ');
    const body = cut > 0 ? `<b>${P.esc(text.slice(0, cut + 1))}</b>${P.esc(text.slice(cut + 1))}` : P.esc(text);
    return `<div class="banner" role="status">${P.icon('alert')}<div>${body}</div></div>`;
  }

  // ── the screen ──
  let root = null;
  let pinned = null;       // the date shown when it is not today; null follows the clock
  let routeDay = null;     // the date the route names (null: today), which the history entry under ours shows
  let stripFrom = null;    // the first day in the strip; it runs to lastEnd()
  let swallow = false;     // a swipe just ended: the click it ends with is not a tap (the next press clears it)
  let touch = null;
  let watcher = null;
  let lastHtml = null;     // the markup on screen, so a redraw that changes nothing leaves the screen alone
  let drawn = null;        // the values drawn last, kept across visits: what the motion compares against
  let popping = false;     // our history entry is being popped (a switch back to the day under it)
  let queued;              // a day switched to while it was popping: its entry is pushed once the pop lands

  const shownDate = () => pinned || P.today();

  function draw(via) {
    const doc = P.doc(), now = P.today(), date = shownDate(), isToday = date === now;
    // the strip begins at least a week before the shown day
    if (!stripFrom) stripFrom = addDays(lastEnd(), -STRIP_DAYS + 1);
    if (stripFrom > addDays(date, -6)) stripFrom = addDays(date, -27);
    const budget = doc.settings.targets.kcal;
    const foods = new Map(doc.foods.map(f => [f.id, f]));
    const days = [];
    for (let d = stripFrom, last = lastEnd(); d <= last; d = addDays(d, 1)) days.push(d);
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
      + (isToday ? '' : '<button class="today-now" type="button" data-act="today">Today</button>')
      + `<button class="ibtn" type="button" data-act="settings" aria-label="Settings">${GEAR}</button></header>`;
    const bottom = `<div class="bottom today-fab"><button class="ibtn box" type="button" data-act="scan" data-for="${meal}" aria-label="Scan a barcode">${P.icon('scan')}</button>`
      + `<button class="btn${first ? ' sec' : ''}" type="button" data-act="add" data-for="${meal}" aria-label="${add.replace('Add', 'Add food')}">${P.icon('plus')}</button></div>`;

    if (first) {
      put(`${head}${banner}<section class="today-empty">${window.PantryDrawing ? window.PantryDrawing.named('plate', 132) : ''}
        <h2>An empty plate.</h2>
        <p><b data-test="kcal-left">${P.fmt(budget)}</b> kcal left today. Bring your MyNetDiary history in once, or scan your first product. Your frequent foods grow from here.</p>
        <button class="btn" type="button" data-act="import">Import MyNetDiary history</button></section>${bottom}`, { date, first: true }, via);
      return;
    }

    const perMeal = MEALS.map(m => entries.filter(e => e.meal === m));
    const mealKcal = perMeal.map(list => list.reduce((a, e) => a + e.totals.kcal, 0));
    const eaten = Math.round(mealKcal.reduce((a, b) => a + b, 0));
    const over = eaten > budget;
    const spans = arcs(mealKcal, budget, over);
    const mac = macros(entries, doc.settings.targets, budget);
    const ordered = isToday ? [...entries].reverse() : perMeal.flat();
    const rows = ordered.map(e => {
      const food = foods.get(e.foodId);
      return `<li><button class="fr" type="button" data-entry="${P.esc(e.id)}"><span class="today-food" aria-hidden="true">${drawing(food, 32)}</span>`
        + `<span class="t"><span class="name">${P.esc(food ? food.name : 'A food no longer in your list')}</span>`
        + `<span class="sub">${NAME[e.meal]}, ${P.esc(e.amount)}</span></span><span class="k">${P.fmt(e.totals.kcal)}</span></button></li>`;
    }).join('');
    const scale = Math.max(2750, 1.25 * budget), dayKcal = kcalOn.get(date);
    const snap = {
      date, first: false, over, spans, grow: mac.grow, barOver: mac.over, gram: mac.gram, pct: mac.pct,
      num: P.fmt(Math.abs(budget - eaten)), lbl: eaten > budget ? 'kcal over' : 'kcal left', tot: tot(eaten, budget),
      ck: perMeal.map((list, i) => (list.length ? P.fmt(mealKcal[i]) : null)),
      cell: dayKcal === undefined ? null : { fill: dayKcal > 0 ? Math.min(100, dayKcal / scale * 100) : 0, over: dayKcal > 0 && Math.round(dayKcal) > budget },
    };

    put(`${head}${strip(days, kcalOn, now, date, budget)}${banner}
      <div class="today-frame${over ? ' today-over' : ''}">${ring(spans, eaten, budget, over)}${MEALS.map((m, i) => corner(i, perMeal[i], mealKcal[i], foods)).join('')}</div>
      ${mac.html}
      <section class="sec today-eaten"><h2 class="eyebrow">${isToday ? 'Eaten today' : 'Eaten that day'}</h2>
        ${rows ? `<ul class="rows">${rows}</ul>` : `<p class="note">Nothing logged ${isToday ? 'yet today' : 'that day'}.</p>`}</section>
      ${bottom}`, snap, via);
  }

  // Puts the markup on screen when it differs from what is there, then starts what the switch or the change calls for.
  function put(html, snap, via) {
    const before = drawn;
    // changed against what was drawn last; a change that lands mid-motion starts from what is on screen
    const changed = !!before && differs(before, snap);
    const from = changed && motion && motion.kind === 'change' ? motion.at(clock() - motion.t0) : before;
    drawn = snap;
    // another day: the running motion drew the old day, so it stops where it is and none of it lands on the new markup
    if (motion && before && before.date !== snap.date) { cancelAnimationFrame(motion.raf); motion = null; delete root.dataset.motion; }
    if (html !== lastHtml) {
      const focus = focused();
      const old = root.querySelector('.today-days');
      const fromEnd = old ? old.scrollWidth - old.scrollLeft : null;   // days only ever join at the start
      root.innerHTML = html;
      lastHtml = html;
      const nav = root.querySelector('.today-days');
      if (nav) {
        nav.scrollLeft = fromEnd === null ? nav.scrollWidth : nav.scrollWidth - fromEnd;
        nav.addEventListener('scrollend', moreDays, { passive: true });
      }
      // only where a sideways touch is a gesture, so a scroll elsewhere never waits for this page
      root.querySelectorAll('.today-frame').forEach(z => z.addEventListener('touchmove', onTouchMove, { passive: false }));
      waves();
      layout();
      watch();
      if (focus) { const el = root.querySelector(focus); if (el) el.focus({ preventScroll: true }); }
      // another day shown brings it into view; any other redraw leaves the strip where his finger left it
      if (fromEnd === null || !before || before.date !== snap.date) inView(fromEnd !== null);
    }
    if (via !== undefined) play(entrance(via));
    else if (changed) play(change(from, snap));
    else if (motion) motion.apply(clock() - motion.t0);   // the same values redrawn: the running motion goes on
  }

  // The control that has focus, as a selector, so a redraw gives the focus back to its new copy.
  function focused() {
    const a = document.activeElement;
    if (!a || a === root || !root.contains(a)) return null;
    for (const k of ['day', 'act', 'meal', 'entry']) if (a.dataset[k]) return `[data-${k}="${CSS.escape(a.dataset[k])}"]`;
    return null;
  }

  // Each wave keeps its phase on the page's clock, so a redraw (a tap, a sync, a return) never makes the strip jump.
  function waves() {
    const now = clock();
    root.querySelectorAll('.today-day').forEach((d, i) => {
      const w = d.querySelector('.today-wave');
      if (!w) return;
      const n = i + 1, [dur, off] = n % 3 === 0 ? [5600, 2700] : n % 2 === 0 ? [6200, 1300] : [5000, 0];
      w.style.animationDelay = `${-Math.round((now + off) % dur)}ms`;
    });
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

  // Fits Today to the text size and width: the strip's words in their days, the macro labels under their bars, whole
  // corner names, the centre inside the ring, and the lowest frame that keeps each corner's
  // name and kcal off the ring's box and its drawings off the ring. A running motion is set aside while it measures.
  function layout() {
    if (!root || !root.isConnected) return;
    const m = motion;
    if (m) m.clear();
    try { fit(); } finally { if (m && motion === m) m.apply(clock() - m.t0); }
  }

  function fit() {
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

  // ── motion: one at a time, every frame a function of the time since it started ──
  let motion = null;       // { kind, t0, end, apply(t), clear() }, and at(t) on a change
  const clock = () => performance.now();
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = v => (v < 0 ? 0 : v > 1 ? 1 : v);
  const lerp = (a, b, p) => a + (b - a) * p;

  // An easing token, cubic-bezier(x1, y1, x2, y2), as a function of progress.
  function bezier(text) {
    const m = String(text).match(/-?\d*\.?\d+/g);
    if (!m || m.length < 4) return x => x;
    const [x1, y1, x2, y2] = m.map(Number);
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const X = t => ((ax * t + bx) * t + cx) * t, Y = t => ((ay * t + by) * t + cy) * t;
    return x => {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      let lo = 0, hi = 1, t = x;
      for (let i = 0; i < 40; i += 1) { const v = X(t); if (Math.abs(v - x) < 1e-5) break; if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; }
      return Y(t);
    };
  }

  function tokens() {
    const s = getComputedStyle(document.documentElement), ms = n => parseFloat(s.getPropertyValue(n)) || 0;
    return { fast: ms('--dur-fast'), base: ms('--dur-base'), chart: ms('--dur-chart'), stagger: ms('--stagger'),
      enter: bezier(s.getPropertyValue('--ease-enter')), exit: bezier(s.getPropertyValue('--ease-exit')),
      standard: bezier(s.getPropertyValue('--ease-standard')) };
  }

  function play(m) {
    finish();
    if (!m || !(m.end > 0) || document.visibilityState === 'hidden') { if (m) m.apply(Infinity); return; }
    motion = m;
    m.t0 = clock();
    root.dataset.motion = m.kind;
    m.apply(0);
    const step = () => {
      if (motion !== m) return;
      const t = clock() - m.t0;
      if (t >= m.end) { finish(); return; }
      m.apply(t);
      m.raf = requestAnimationFrame(step);
    };
    m.raf = requestAnimationFrame(step);
  }

  // Ends the running motion at its last frame: the screen as draw() put it, with nothing of the motion left on it.
  function finish() {
    const m = motion;
    if (!m) return;
    motion = null;
    cancelAnimationFrame(m.raf);
    if (root) { m.apply(Infinity); delete root.dataset.motion; }
  }

  const sameList = (a, b, d) => a.length === b.length && a.every((x, i) => Math.abs(x - b[i]) <= d);
  const sameSpan = (a, b) => (!a && !b) || (!!a && !!b && sameList(a, b, 0.01));
  function differs(a, b) {
    if (a.first || b.first || a.date !== b.date) return false;
    return a.over !== b.over || !a.spans.every((s, i) => sameSpan(s, b.spans[i])) || !sameList(a.grow, b.grow, 0.01)
      || a.barOver.some((o, i) => o !== b.barOver[i]) || a.num !== b.num || a.lbl !== b.lbl || a.tot !== b.tot
      || a.ck.some((c, i) => c !== b.ck[i]) || a.gram.some((g, i) => g !== b.gram[i]) || a.pct.some((x, i) => x !== b.pct[i])
      || (!!a.cell && !!b.cell && (Math.abs(a.cell.fill - b.cell.fill) > 0.01 || a.cell.over !== b.cell.over));
  }

  // The macro numbers a swap can change: [the bar or label column, the number in it].
  const MAC_PART = { pct: ['.today-bar', '.today-pct'], lpct: ['.today-labs > div', '.today-lpn'], g: ['.today-labs > div', '.today-g > span'] };

  // What changed between two drawings of the same day, as one motion. The greys go first: the arcs that changed run
  // from their old ends and the bars move (chart, 40 ms apart), the day's tank follows, the corner kcal and the eaten
  // total swap in the middle, each bar's percentage and grams swap after their bar (base barsIn: at 60 % of chart, 40 ms
  // apart); the kcal-left number swaps last, 120 ms after the greys, and the over tone lands with it.
  function change(from, to) {
    const T = tokens(), rm = reduced();
    const chart = rm ? 0 : T.chart, stagger = rm ? 0 : T.stagger;
    const swapLen = T.fast + T.base;
    const atCk = rm ? 0 : chart / 2, atTot = atCk + stagger;
    const atMac = i => i * stagger + 0.6 * chart;
    const greys = Math.max(chart + 2 * stagger, atTot + swapLen, atMac(MACROS.length - 1) + swapLen);
    const atNum = rm ? 0 : greys + 120 - swapLen;
    const flipAt = atNum + T.fast;
    const ringMoves = !from.spans.every((s, i) => sameSpan(s, to.spans[i]));
    const barsMove = !sameList(from.grow, to.grow, 0.01);
    const fillMoves = !!(from.cell && to.cell) && Math.abs(from.cell.fill - to.cell.fill) > 0.01;
    const tones = from.over !== to.over || from.barOver.some((o, i) => o !== to.barOver[i])
      || !!(from.cell && to.cell && from.cell.over !== to.cell.over);
    const swaps = [];
    if (from.num !== to.num) swaps.push({ k: 'num', at: atNum, old: from.num });
    if (from.lbl !== to.lbl) swaps.push({ k: 'lbl', at: atNum, old: from.lbl });
    if (from.tot !== to.tot) swaps.push({ k: 'tot', at: atTot, old: from.tot });
    from.ck.forEach((c, i) => { if (c !== to.ck[i]) swaps.push({ k: 'ck', i, at: atCk, old: c, now: to.ck[i] }); });
    MACROS.forEach((_, i) => {
      if (from.gram[i] !== to.gram[i]) swaps.push({ k: 'g', i, at: atMac(i), old: `${from.gram[i]} /` });
      if (from.pct[i] === to.pct[i]) return;
      const old = from.pct[i] === null ? null : `${from.pct[i]}%`;
      swaps.push({ k: 'pct', i, at: atMac(i), old }, { k: 'lpct', i, at: atMac(i), old });
    });
    const key = s => (s.i === undefined ? s.k : `${s.k}${s.i}`);
    const ends = [swaps.length ? Math.max(...swaps.map(s => s.at + swapLen)) : 0, ringMoves || fillMoves ? chart : 0,
      barsMove ? chart + 2 * stagger : 0, tones ? flipAt : 0];
    const end = Math.max(...ends);
    // where a span grows from or shrinks to when the meal had nothing: its own start
    const pair = to.spans.map((s, i) => {
      const a = from.spans[i];
      if (!a && !s) return null;
      return [a || [s[0], s[0]], s || [a[0], a[0]]];
    });
    // a frame draws no arc shorter than 0.05 degrees (under a tenth of a pixel)
    const spansAt = p => pair.map(x => {
      const sp = x && [lerp(x[0][0], x[1][0], p), lerp(x[0][1], x[1][1], p)];
      return sp && sp[1] - sp[0] >= 0.05 ? sp : null;
    });
    const bar = (t, i) => (chart ? T.enter(clamp((t - i * stagger) / chart)) : 1);
    const chartAt = t => (chart ? T.enter(clamp(t / chart)) : 1);
    const q = s => root.querySelector(s);
    const realOf = s => {
      if (MAC_PART[s.k]) {
        const [col, part] = MAC_PART[s.k], el = root.querySelectorAll(col)[s.i];
        return el ? el.querySelector(part) : null;
      }
      return s.k === 'num' ? q('.today-frame [data-test="kcal-left"]') : s.k === 'lbl' ? q('.today-lbl')
        : s.k === 'tot' ? q('.today-tot') : q(`.today-corner[data-meal="${MEALS[s.i]}"] .today-ck`);
    };

    function ghostOf(s) {
      let g = root.querySelector(`.today-ghost[data-k="${key(s)}"]`);
      if (g || s.old === null || s.hidden) return g;
      const real = realOf(s);
      // a percentage that moved under its bar is hidden in it: no ghost there, decided once
      if (MAC_PART[s.k] && (!real || getComputedStyle(real).visibility !== 'visible')) { s.hidden = true; return null; }
      g = document.createElement('i');
      g.className = `today-ghost today-g${s.k === 'num' ? 'num disp' : s.k}`;
      g.dataset.k = key(s);
      g.setAttribute('aria-hidden', 'true');
      g.innerHTML = s.old;
      if (s.k === 'ck') {
        const c = q(`.today-corner[data-meal="${MEALS[s.i]}"]`), cn = c && c.querySelector('.today-cn');
        if (!c || !cn) return null;
        const right = s.i === 1 || s.i === 2;
        g.style.top = `${real ? real.offsetTop : cn.offsetTop + cn.offsetHeight}px`;
        if (right) g.style.right = `${real ? c.clientWidth - real.offsetLeft - real.offsetWidth : 0}px`;
        else g.style.left = `${real ? real.offsetLeft : 0}px`;
        c.appendChild(g);
      } else if (MAC_PART[s.k]) {
        // the old value starts where the new one does and, like every label, stays inside the row
        g.style.left = `${real.offsetLeft}px`;
        g.style.top = `${real.offsetTop}px`;
        real.parentElement.appendChild(g);
        const row = s.k !== 'pct' && q('.today-labs');
        const out = row ? g.getBoundingClientRect().right - row.getBoundingClientRect().right : 0;
        if (out > 0) g.style.left = `${real.offsetLeft - out}px`;
      } else {
        if (!real) return null;
        g.style.left = `${real.offsetLeft + real.offsetWidth / 2}px`;
        g.style.top = `${real.offsetTop}px`;
        g.dataset.centre = '1';
        real.parentElement.appendChild(g);
      }
      return g;
    }

    // The old value leaves upward and fades (fast, exit); the new one rises from below (base, enter). Reduced motion:
    // the same timing as a fade alone. Each part leaves nothing behind once its own phase is over.
    function swapAt(s, t, done) {
      const real = realOf(s), outEnd = s.at + T.fast, inEnd = outEnd + T.base;
      const art = s.k === 'ck' && (s.old === null || s.now === null)
        ? q(`.today-corner[data-meal="${MEALS[s.i]}"] ${s.now === null ? '.today-addm' : '.today-fs'}`) : null;
      if (done || t >= outEnd) {
        const g = root.querySelector(`.today-ghost[data-k="${key(s)}"]`);
        if (g) g.remove();
      } else {
        const g = ghostOf(s);
        if (g) {
          const p = T.exit(clamp((t - s.at) / T.fast)), base = g.dataset.centre ? 'translateX(-50%) ' : '';
          g.style.opacity = String(1 - p);
          g.style.transform = `${base}translateY(${rm ? 0 : f2(-40 * p)}%)`;
        }
      }
      const p = T.enter(clamp((t - outEnd) / T.base));
      [real, art].forEach(el => {
        if (!el) return;
        if (done || t >= inEnd) { el.style.removeProperty('opacity'); el.style.removeProperty('transform'); return; }
        el.style.opacity = String(p);
        el.style.transform = rm || el === art ? 'none' : `translateY(${f2(40 * (1 - p))}%)`;
      });
    }

    function apply(t) {
      if (!root) return;
      const done = t >= end, flipped = done || t >= flipAt;
      const frame = q('.today-frame');
      if (!frame) return;
      const over = flipped ? to.over : from.over;
      if (tones) frame.classList.toggle('today-over', over);
      if (ringMoves || from.over !== to.over) {
        const svg = frame.querySelector('.today-ring > svg');
        const { paths, initials } = ringParts(done ? to.spans : spansAt(chartAt(t)), over);
        svg.innerHTML = paths;
        frame.querySelectorAll('.today-ini').forEach(n => n.remove());
        svg.insertAdjacentHTML('afterend', initials);
      }
      const bars = root.querySelectorAll('.today-bar');
      bars.forEach((b, i) => {
        if (barsMove) b.style.flexGrow = String(done ? to.grow[i] : lerp(from.grow[i], to.grow[i], bar(t, i)));
        if (tones) b.classList.toggle('today-bo', flipped ? to.barOver[i] : from.barOver[i]);
      });
      const cell = to.cell && q(`.today-day[data-day="${to.date}"]`);
      if (cell) {
        const liq = cell.querySelector('.today-liq');
        if (fillMoves && liq) liq.style.height = `${f2(done ? to.cell.fill : lerp(from.cell.fill, to.cell.fill, chartAt(t)))}%`;
        if (tones && from.cell) cell.classList.toggle('today-ov', flipped ? to.cell.over : from.cell.over);
      }
      swaps.forEach(s => swapAt(s, t, done));
    }

    return {
      kind: 'change', end, apply,
      // layout() measures the final geometry: no swap offsets, the bars at their new values
      clear() {
        swaps.forEach(s => { const r = realOf(s); if (r) r.style.removeProperty('transform'); });
        if (barsMove) root.querySelectorAll('.today-bar').forEach((b, i) => { b.style.flexGrow = String(to.grow[i]); });
      },
      // what is on screen at t, for a change that arrives before this one has landed
      at(t) {
        const p = chartAt(t);
        return { ...to, over: t >= flipAt ? to.over : from.over, spans: ringMoves ? spansAt(p) : to.spans,
          grow: barsMove ? to.grow.map((g, i) => lerp(from.grow[i], g, bar(t, i))) : to.grow,
          cell: to.cell && from.cell ? { ...to.cell, fill: lerp(from.cell.fill, to.cell.fill, p) } : to.cell };
      },
    };
  }

  // How far the ring's frame may move sideways: SHIFT, or less where the screen's edge is nearer (its 20 px margin), so
  // neither it nor a corner ever passes the edge. Measured where the frame rests, without the offset a motion gave it.
  function travel(frame) {
    const w = document.documentElement.clientWidth, offset = frame.style.transform;
    frame.style.removeProperty('transform');
    const room = Math.min(...[frame, ...frame.children].map(el => { const r = el.getBoundingClientRect(); return Math.min(r.left, w - r.right); }));
    if (offset) frame.style.transform = offset;
    return Math.max(0, Math.min(SHIFT, Math.floor(room)));
  }

  // Another day: the date, the ring and what is under it fade in (fast); after a ring swipe the ring comes from the side
  // it was pushed to (base), from as far as travel() allows. Reduced motion keeps the fade alone.
  function entrance(dir) {
    const f = root.querySelector('.today-frame');
    const T = tokens(), dx = reduced() || !dir || !f ? 0 : dir * travel(f), dur = dir ? T.base : T.fast, start = dir ? 0 : 0.25;
    const parts = () => root.querySelectorAll('.today-top > div, .today-frame, .today-mac, .today-eaten');
    return {
      kind: 'enter', end: dur,
      apply(t) {
        const done = t >= dur, p = T.enter(clamp(t / dur));
        parts().forEach(el => {
          if (done) { el.style.removeProperty('opacity'); el.style.removeProperty('transform'); return; }
          el.style.opacity = String(lerp(start, 1, p));
          if (dx && el.classList.contains('today-frame')) el.style.transform = `translateX(${f2(dx * (1 - p))}px)`;
        });
      },
      clear() { const f = root.querySelector('.today-frame'); if (f) f.style.removeProperty('transform'); },
    };
  }

  // A ring dragged but not swiped far enough goes back where it was (base, standard easing).
  function settle(x) {
    const T = tokens();
    play({
      kind: 'settle', end: x ? T.base : 0,
      apply(t) {
        const f = root.querySelector('.today-frame');
        if (!f) return;
        if (t >= T.base) { f.style.removeProperty('transform'); f.style.removeProperty('opacity'); return; }
        const v = x * (1 - T.standard(clamp(t / T.base)));
        f.style.transform = `translateX(${f2(v)}px)`;
        f.style.opacity = String(1 - 0.3 * Math.abs(v) / SHIFT);
      },
      clear() { const f = root.querySelector('.today-frame'); if (f) f.style.removeProperty('transform'); },
    });
  }

  // ── switching the shown day in place ──
  const ours = st => !!st && 'day' in st && st.dayOf === location.hash;

  // History for a switch: one entry of ours over the route's, replaced while it lives, popped on the way back to the
  // route's own day.
  function remember(day) {
    if (popping) { queued = day; return; }
    const st = history.state || {};
    if (ours(st)) {
      if (day === routeDay) { popping = true; queued = undefined; history.back(); }
      else history.replaceState({ ...st, day }, '', location.href);
    } else if (day !== routeDay) {
      history.pushState({ ...st, depth: (st.depth || 0) + 1, day, dayOf: location.hash }, '', location.href);
    }
  }

  // dir: 0 a fade (a tap, the Today action, Back), 1 the next day from the right, -1 the day before from the left.
  function switchTo(day, dir, fromHistory) {
    const next = day === P.today() ? null : day;
    if ((next || P.today()) === shownDate()) return;
    if (!fromHistory) remember(next);
    pinned = next;
    draw(dir);
  }

  window.addEventListener('popstate', () => {
    if (!root || !root.isConnected) return;
    if (popping) {
      popping = false;
      const q = queued;
      queued = undefined;
      if (q !== undefined && q !== routeDay) {
        const st = history.state || {};
        history.pushState({ ...st, depth: (st.depth || 0) + 1, day: q, dayOf: location.hash }, '', location.href);
      }
      return;
    }
    const st = history.state;
    const want = ours(st) ? (isDate(st.day) ? st.day : null) : routeDay;
    switchTo(want || P.today(), 0, true);
  });

  function onClick(e) {
    const b = e.target.closest('button');
    if (!b || !root || !root.contains(b)) return;
    if (swallow) { swallow = false; return; }     // the click a swipe ends with is part of the swipe, not a tap
    const date = shownDate();
    if (b.dataset.day) { if (b.dataset.day !== date) switchTo(b.dataset.day, 0); }
    else if (b.dataset.act === 'today') switchTo(P.today(), 0);
    else if (b.dataset.meal) P.go('add', b.dataset.meal, date);
    else if (b.dataset.entry) P.go('entry', b.dataset.entry);
    else if (b.dataset.act === 'add') P.go('add', P.mealNow(), date);
    else if (b.dataset.act === 'scan') P.go('scan', P.mealNow(), date);
    else if (b.dataset.act === 'settings' || b.dataset.act === 'import') P.go('settings');
  }

  // ── gestures: a swipe on the strip moves it a week; a swipe on the ring goes to the next or the day before ──
  function onDown(e) {
    if (!e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    swallow = false;
    const zone = e.target.closest('.today-frame') ? 'ring' : null;
    touch = zone ? { zone, x: e.clientX, y: e.clientY, id: e.pointerId, t: e.timeStamp, side: false, pull: 0 } : null;
  }

  // Which way a touch leans, from where it went down: the page decides nothing by a distance of its own. Chrome (pan-y)
  // takes the page's scroll when the touch leaves its slop (on Android the phone's own, 8 dp unless it sets another)
  // leaning up or down there, and then cancels the pointer (onCancel); leaning sideways there, the touch is this gesture's.
  const leansSideways = (from, x, y) => Math.abs(x - from.x) > Math.abs(y - from.y);

  // The ring follows a drag that leans sideways past 10 px, eased to at most travel() (24 px, 20 at the 20 px margin),
  // 8 px toward a day that does not exist yet.
  function onMove(e) {
    if (!touch || e.pointerId !== touch.id || touch.zone !== 'ring') return;
    const dx = e.clientX - touch.x;
    const frame = root.querySelector('.today-frame');
    if (!frame) return;
    if (!touch.side) {
      if (Math.abs(dx) <= 10 || !leansSideways(touch, e.clientX, e.clientY)) return;
      touch.side = true;
      if (motion && motion.kind !== 'change') finish();
      touch.room = travel(frame);
    }
    const ahead = dx < 0 && shownDate() >= P.today();
    touch.pull = (ahead ? Math.min(8, touch.room) : touch.room) * Math.tanh(dx / 96);
    frame.style.transform = `translateX(${f2(touch.pull)}px)`;
    frame.style.opacity = String(1 - 0.3 * Math.abs(touch.pull) / SHIFT);
  }

  function onUp(e) {
    if (!touch || e.pointerId !== touch.id) return;
    const { zone, side, pull } = touch, dx = e.clientX - touch.x, dy = e.clientY - touch.y, dt = Math.max(1, e.timeStamp - touch.t);
    touch = null;
    const sideways = Math.abs(dx) > 1.5 * Math.abs(dy);
    const swipe = sideways && (Math.abs(dx) >= 40 || (Math.abs(dx) >= 20 && Math.abs(dx) / dt >= 0.5));
    if (side || swipe) swallow = true;
    const date = shownDate();
    if (swipe && dx < 0 && date < P.today()) switchTo(addDays(date, 1), 1);
    else if (swipe && dx > 0) switchTo(addDays(date, -1), -1);
    else if (side) settle(pull);
  }

  function onCancel() {
    if (touch && touch.side) settle(touch.pull);
    touch = null;
  }

  // ── the strip ──
  // About three months of days to begin with; scrolled near its start it takes three more, once the scroll has stopped
  // (taking them mid-flick would stop the flick). A day after today shows only while it is the shown day.
  const STRIP_DAYS = 91;
  const lastEnd = () => { const d = shownDate(), now = P.today(); return d > now ? d : now; };

  function moreDays(e) {
    const nav = e.currentTarget;
    if (!root || !nav.isConnected || nav.scrollLeft > 2 * nav.clientWidth) return;
    stripFrom = addDays(stripFrom, -STRIP_DAYS);
    draw();
  }

  // The shown day inside the strip's view: at its right end when it was out of sight; `glide`: a scroll the eye can
  // follow (base Motion), else at once.
  function inView(glide) {
    const nav = root.querySelector('.today-days'), on = nav && nav.querySelector('.today-on');
    if (!on) return;
    const side = parseFloat(getComputedStyle(nav).paddingLeft), a = on.offsetLeft - side, b = on.offsetLeft + on.offsetWidth + side;
    if (a >= nav.scrollLeft - 1 && b <= nav.scrollLeft + nav.clientWidth + 1) return;
    nav.scrollTo({ left: b - nav.clientWidth, behavior: glide && !reduced() ? 'smooth' : 'instant' });
  }

  // A move made while the touch leans sideways is consumed. Left to Chrome on a pan-y area, a quick sideways swipe made
  // the next tap get no click (the Today action or a day in the strip doing nothing), with or without a redraw: measured
  // in headless Chromium, most likely the fling Chrome starts from it and never shows, which that tap only stops.
  // Consumed from before the touch slop ends they fix it; consumed later they do not. A move leaning up or down is left
  // alone, so the move that ends the slop is consumed only where pan-y refuses the scroll anyway: a scroll whose first
  // px lean sideways and then go up scrolls as it would without this page. Pointer events still arrive.
  function onTouchMove(e) {
    const t = touch && e.touches[0];
    if (t && e.cancelable && leansSideways(touch, t.clientX, t.clientY)) e.preventDefault();
  }

  function render(el, date) {
    finish();
    root = el;
    lastHtml = null;
    popping = false;
    queued = undefined;
    routeDay = isDate(date) && date !== P.today() ? date : null;
    const st = history.state;
    pinned = ours(st) ? (isDate(st.day) && st.day !== P.today() ? st.day : null) : routeDay;
    stripFrom = null;
    el.addEventListener('click', onClick);
    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerup', onUp);
    el.addEventListener('pointercancel', onCancel);
    el.addEventListener('keydown', () => { swallow = false; });
    draw();
  }

  window.addEventListener('resize', () => { if (root && root.isConnected) layout(); });
  // A phone keeps Today open from breakfast to lunch: coming back, the bottom button names the meal the clock suggests now.
  document.addEventListener('visibilitychange', () => {
    const btn = root && root.isConnected && root.querySelector('[data-act="add"]');
    if (document.visibilityState === 'visible' && btn && btn.dataset.for !== P.mealNow()) draw();
  });
  if (document.fonts) document.fonts.addEventListener('loadingdone', () => { if (root && root.isConnected) layout(); });
  P.view('today', {
    render,
    update() { if (root && root.isConnected) draw(); },
    leave() { finish(); if (watcher) watcher.disconnect(); watcher = null; touch = null; root = null; },
  });
})();

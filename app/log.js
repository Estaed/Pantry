/* Log: a meal's food list and the gram sheet drawn over it (design/screens.html → 2, 3, 3b).

   Routes (Blueprint → Screens and seams; a missing date is today, a missing meal Pantry.mealNow()):
     '#/add/<meal>/<date>'        the meal's foods: search by food or brand, tabs Frequent / Recent / My foods. A row's
                                  + logs its usual amount at once and the list stays (toast with Undo); tapping the row
                                  opens the gram sheet over the list, and the phone's back gesture closes it again.
     '#/food/<id>/<meal>/<date>'  the same list with the gram sheet for one food already open; closing it goes back.
   "Add to <meal>" on the sheet logs and returns with Pantry.go('today', date); Back from Today shows the list, not the sheet.

   Rules
     Frequent    the foods logged at that meal in the 90 days up to today, most often first (then the latest first);
                 with no entries at all, the starter foods in their order.
     Recent      the last distinct foods logged; My foods every food, A to Z.
     Search      every typed word starts a word of the food's name or brand, ignoring case and accents.
     Usual       Pantry.usualAmounts(foodId, meal)[0], the one rule in core; the sheet's chips are that list.
     Servings    a food without per100 is logged by its servings: n x (its last entry's totals / that entry's
                 servings), so his macros stay; with no entry yet, kcal from its first serving only. grams is null.
     Every entry keeps its totals from log time. Undo deletes like any delete: the entry goes, a removed line is added.
   The list keeps its order while it is shown, so a + never moves the row under his thumb.

   Gate hooks (tests/acceptance.py): row buttons whose accessible name starts with the food name; the five starter
   foods in order with "Brand, N g" on an empty log; the "Grams" field and its data-test="portion-kcal"; the meal
   radios Breakfast to Snacks; the "Add to <meal>" button; the error line .err. */
(() => {
  'use strict';
  const P = window.Pantry;
  const MEALS = ['breakfast', 'lunch', 'dinner', 'snacks'];
  const LABEL = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snacks: 'Snacks' };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const WINDOW = 90;          // days Frequent looks back, as Pantry.usualAmounts does
  const RECENT = 30;          // distinct foods on the Recent tab
  const CHIPS = 4;            // usual amounts offered on the sheet
  const MAX_GRAMS = 10000;
  const MEASURES = new Set(['g', 'kg', 'mg', 'mcg', 'ml', 'l', 'oz', 'fl oz', 'lb']);   // units that take no plural s
  const SIZES = new Set(['small', 'medium', 'large']);   // '2 medium' (bananas): a size, not a thing to count
  // "All nutrients": the four the task names always show (a missing one as a dash); the rest only when the food has them.
  const MAIN = [['salt', 'Salt', 'g'], ['sugars', 'Sugars', 'g'], ['fibre', 'Fibre', 'g'], ['satFat', 'Saturated fat', 'g']];
  const MORE = [['addedSugars', 'Added sugars', 'g'], ['sugarAlcohols', 'Sugar alcohols', 'g'], ['solubleFiber', 'Soluble fibre', 'g'],
    ['transFat', 'Trans fat', 'g'], ['monoUnsatFat', 'Monounsaturated fat', 'g'], ['polyUnsatFat', 'Polyunsaturated fat', 'g'],
    ['sodium', 'Sodium', 'mg'], ['cholesterol', 'Cholesterol', 'mg'], ['potassium', 'Potassium', 'mg'], ['calcium', 'Calcium', 'mg'],
    ['iron', 'Iron', 'mg'], ['vitaminA', 'Vitamin A', ''], ['vitaminC', 'Vitamin C', 'mg'], ['vitaminD', 'Vitamin D', 'mcg'],
    ['caffeine', 'Caffeine', 'mg'], ['alcohol', 'Alcohol', 'g']];
  const SHOWN = new Set(['kcal', 'protein', 'carbs', 'fat', ...MAIN.map(n => n[0]), ...MORE.map(n => n[0])]);
  const MACROS = [['protein', 'Protein', 4], ['carbs', 'Carbs', 4], ['fat', 'Fat', 9]];
  const ICON = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    up: '<path d="m18 15-6-6-6 6"/>',
  };
  const icon = name => (ICON[name] ? `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[name]}</svg>` : P.icon(name));

  P.css(`
    .log-main { flex: 1; display: flex; flex-direction: column; }
    .log-head { position: sticky; top: 0; z-index: 2; background: var(--canvas); padding: 14px 20px 0; display: flex; flex-direction: column; gap: 14px; }
    .log-search { display: flex; gap: 8px; align-items: center; }
    .log-field {
      flex: 1; min-width: 0; min-height: 46px; display: flex; align-items: center; gap: 10px; padding: 0 4px 0 16px;
      border-radius: 23px; background: var(--surface-2); color: var(--ink-muted);
    }
    .log-field:focus-within { box-shadow: inset 0 0 0 2px var(--primary); }
    .log-field > svg.i { width: 18px; height: 18px; }
    .log-field input {
      flex: 1; min-width: 0; height: 44px; padding: 0; border: 0; background: none; outline: none; color: var(--ink);
      font: 500 0.9375rem/1.3 var(--font-sans); text-overflow: ellipsis;
    }
    /* a narrow screen with big text has no room for the whole hint (or a long query, once the field loses focus):
       it ends in an ellipsis rather than mid-letter */
    .log-field input::placeholder { color: var(--ink-muted); opacity: 1; text-overflow: ellipsis; }
    .log-field input::-webkit-search-cancel-button { display: none; }
    .log-clear { width: 40px; height: 40px; flex: none; display: grid; place-items: center; padding: 0; border: 0; border-radius: 50%; background: none; color: var(--ink-muted); }
    .log-clear svg.i { width: 18px; height: 18px; }
    .log-scan { width: 46px; height: 46px; border-radius: 50%; background: var(--surface-2); }
    /* each label stays on one line (design 2); the gap narrows on a narrow screen, and a tab that still has no room
       moves whole to a second row rather than breaking "My foods" in two */
    .log-tabs { display: flex; flex-wrap: wrap; gap: 0 clamp(12px, 5vw, 18px); border-bottom: 1px solid var(--hairline); }
    .log-tab {
      position: relative; min-width: 0; min-height: 44px; padding: 8px 0; border: 0; background: none; white-space: nowrap;
      font: 600 0.875rem/1.3 var(--font-sans); color: var(--ink-subtle); text-align: left;
    }
    .log-tab[aria-selected="true"] { color: var(--ink); }
    .log-tab[aria-selected="true"]::after { content: ''; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: var(--ink); }
    .log-list { padding: 0 20px 24px; }
    .log-list.log-swap { animation: log-fade var(--dur-fast) var(--ease-enter); }
    .log-list .rows { margin: 0; }
    .log-row { padding: 0; gap: 4px; }
    .log-open {
      flex: 1; min-width: 0; min-height: 56px; display: grid; grid-template-columns: 40px minmax(0, 1fr) auto;
      grid-template-areas: "food name k" "food sub k"; align-items: center; gap: 0 12px; padding: 6px 0;
      border: 0; background: none; color: inherit; text-align: left;
    }
    .log-open .t { display: contents; }
    .log-open .name { grid-area: name; align-self: end; }
    .log-open .sub { grid-area: sub; align-self: start; }
    .log-open .k { grid-area: k; }
    /* big text or a narrow screen: the name takes the whole row, the kcal moves to the second line */
    @media (max-width: 20rem) {
      .log-open { grid-template-areas: "food name name" "food sub k"; column-gap: 10px; }
      .log-open .k { align-self: start; font-weight: 600; line-height: 1.35; }
    }
    /* the amount is what the + logs, so it is never cut: the brand gives way first (fitRows) */
    .log-open .sub .b, .log-open .sub .a { display: inline-block; max-width: 100%; vertical-align: top; overflow: hidden; text-overflow: ellipsis; }
    .log-open .sub .b[hidden] { display: none; }
    /* an amount longer than its line even without the brand: the kcal moves up beside the name, the amount gets the whole line */
    .log-open.log-long { grid-template-areas: "food name k" "food sub sub"; }
    .log-open.log-long .k { align-self: end; }
    .log-food { grid-area: food; width: 40px; height: 40px; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); }
    .log-food svg { width: 32px; height: 32px; }
    .log-plus { position: relative; width: 48px; height: 48px; flex: none; display: grid; place-items: center; padding: 0; border: 0; background: none; color: var(--ink); }
    .log-plus::before { content: ''; position: absolute; inset: 4px; border-radius: 50%; border: 1.5px solid var(--hairline-strong); transition: background-color var(--fast); }
    .log-plus:active::before { background: var(--surface-3); }
    .log-plus svg.i { position: relative; width: 18px; height: 18px; }
    .log-empty { display: flex; flex-direction: column; gap: 14px; padding-top: 6px; }
    .log-empty .note { margin: 0; }
    .log-empty .btn, .log-gone .btn { margin: 0; }   /* base.css .sec is also the section margin */
    .log-gone { margin: 24px 20px 0; display: flex; flex-direction: column; gap: 14px; }
    .log-gone .banner { margin: 0; }

    .log-layer { position: fixed; inset: 0; z-index: 10; }
    .log-scrim { position: absolute; inset: 0; width: 100%; padding: 0; border: 0; border-radius: 0; background: var(--scrim); touch-action: none; animation: log-fade var(--dur-slow) var(--ease-enter); }
    .log-sheet {
      position: absolute; left: 0; right: 0; bottom: 0; max-height: calc(100% - 24px); display: flex; flex-direction: column;
      background: var(--surface-1); border-top: 1px solid var(--hairline-strong); border-radius: var(--r-xl) var(--r-xl) 0 0;
      box-shadow: var(--shadow-3); outline: none; animation: log-up var(--dur-slow) var(--ease-enter);
      --log-g1: var(--ink); --log-g3: color-mix(in oklab, var(--ink) 40%, var(--canvas));
    }
    .log-scroll { min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 10px 20px 4px; display: flex; flex-direction: column; align-items: center; gap: 12px; }
    .log-handle { width: 36px; height: 4px; flex: none; border-radius: 4px; background: var(--hairline-strong); }
    .log-hero { width: 104px; height: 104px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); }
    .log-hero svg { width: 78px; height: 78px; }
    @media (max-height: 680px) { .log-hero { width: 72px; height: 72px; } .log-hero svg { width: 54px; height: 54px; } }
    .log-name { margin: 0; max-width: 100%; font: 700 1.1875rem/1.25 var(--font-sans); text-align: center; overflow-wrap: anywhere; }
    .log-per { margin: -8px 0 0; font: 500 0.8125rem/1.4 var(--font-sans); color: var(--ink-muted); text-align: center; }
    .log-amt { max-width: 100%; display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline; gap: 4px 18px; }
    .log-g { display: flex; align-items: baseline; padding: 0 4px 2px; border-bottom: 2px solid var(--primary); cursor: text; }
    .log-g:focus-within { box-shadow: 0 1px 0 var(--primary); }
    .log-g input {
      width: 4.4ch; min-width: 0; padding: 0; border: 0; border-radius: 0; background: none; outline: none; color: var(--ink); text-align: right;
      font-family: var(--font-display); font-weight: var(--display-weight); font-stretch: var(--display-stretch);
      font-size: 2.75rem; line-height: 1.05; letter-spacing: -0.02em;
    }
    @supports (field-sizing: content) { .log-g input { width: auto; min-width: 1.6ch; field-sizing: content; } }
    .log-g small, .log-k small { margin-left: 4px; font: 600 0.9375rem var(--font-sans); letter-spacing: 0; color: var(--ink-muted); }
    .log-k { font-size: 1.75rem; line-height: 1.05; letter-spacing: -0.01em; color: var(--ink-muted); white-space: nowrap; }
    .log-err { align-self: stretch; display: flex; gap: 8px; align-items: center; justify-content: center; margin: -4px 0 0; font: 600 0.8125rem/1.4 var(--font-sans); color: var(--danger); }
    .log-err svg.i { width: 16px; height: 16px; }
    .log-chips { max-width: 100%; display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
    .log-chip {
      position: relative; min-height: 36px; padding: 6px 14px; display: inline-flex; align-items: center; border-radius: 18px;
      border: 1px solid var(--hairline-strong); background: none; color: var(--ink); font: 600 0.875rem/1.2 var(--font-sans);
      transition: background-color var(--fast), color var(--fast);
    }
    .log-chip::before { content: ''; position: absolute; inset: -4px -2px; }
    .log-chip em { margin-left: 5px; font-style: normal; font-weight: 500; font-size: 0.75rem; color: var(--ink-subtle); }
    .log-chip[aria-pressed="true"] { background: var(--action); color: var(--on-action); border-color: var(--action); }
    .log-chip[aria-pressed="true"] em { color: var(--on-action); opacity: 0.7; }
    .log-portion { width: 100%; }
    .log-portion .eyebrow { display: block; margin-bottom: 8px; }
    .log-bars { display: flex; gap: 4px; }
    .log-bars > span {
      min-width: 0; height: 30px; display: flex; align-items: center; padding: 0 8px; border-radius: 8px; overflow: hidden; white-space: nowrap;
      font: 700 0.8125rem/1 var(--font-figure);
    }
    .log-macros { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 2px 12px; margin-top: 6px; font: 600 0.75rem/1.4 var(--font-figure); color: var(--ink-muted); }
    .log-macros b { font-weight: 700; color: var(--ink); }
    .log-more {
      width: 100%; min-height: 44px; display: flex; justify-content: space-between; align-items: center; padding: 0;
      border: 0; border-top: 1px solid var(--hairline); background: none; font: 600 0.875rem/1.3 var(--font-sans); color: var(--ink-muted);
    }
    .log-more svg.i { width: 18px; height: 18px; }
    .log-nutr { width: 100%; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 8.5rem), 1fr)); gap: 0 18px; margin-top: -8px; }
    .log-nutr > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0 8px; padding: 6px 0; border-bottom: 1px solid var(--hairline); font: 500 0.875rem/1.35 var(--font-sans); color: var(--ink-muted); }
    .log-nutr b { margin-left: auto; font: 600 0.875rem/1.35 var(--font-figure); color: var(--ink); white-space: nowrap; }
    .log-meals { width: 100%; min-width: 0; margin: 0; padding: 3px; border: 0; display: flex; flex-wrap: wrap; gap: 3px; border-radius: var(--r-button); background: var(--surface-2); }
    .log-meal { position: relative; flex: 1 1 auto; }
    @media (max-width: 20rem) { .log-meals { display: grid; grid-template-columns: 1fr 1fr; } }
    .log-meal input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
    .log-meal span {
      min-height: 44px; display: flex; align-items: center; justify-content: center; padding: 4px 10px; border-radius: 9px;
      font: 600 0.8125rem/1.2 var(--font-sans); color: var(--ink-muted); transition: background-color var(--fast), color var(--fast);
    }
    .log-meal input:checked + span { background: var(--action); color: var(--on-action); }
    .log-meal input:focus-visible + span { outline: 2px solid var(--primary); outline-offset: 2px; }
    .log-vh { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    .log-foot { padding: 10px 20px calc(18px + env(safe-area-inset-bottom)); }
    .log-layer.log-out { pointer-events: none; }
    .log-layer.log-out .log-sheet { transform: translateY(100%); transition: transform var(--dur-base) var(--ease-exit); }
    .log-layer.log-out .log-scrim { opacity: 0; transition: opacity var(--dur-base) var(--ease-exit); }
    @keyframes log-up { from { transform: translateY(100%); } }
    @keyframes log-fade { from { opacity: 0; } }
    @media (prefers-reduced-motion: reduce) {
      .log-sheet { animation-name: log-fade; }
      .log-layer.log-out .log-sheet { transform: none; opacity: 0; transition-property: opacity; }
    }
  `);

  // ── numbers, amounts, dates ───────────────────────────────────────
  const isNum = v => typeof v === 'number' && Number.isFinite(v);
  // toPrecision(12) drops binary noise first, the way core rounds totals.
  const round = (v, digits) => { const f = 10 ** digits; return Math.round(Number((v * f).toPrecision(12))) / f; };
  const exact = v => Number(v.toPrecision(12));   // n x totals as they are, minus binary noise (1.875 stays 1.875)
  const scale = (totals, factor) => {
    const out = {};
    for (const [k, v] of Object.entries(totals || {})) if (isNum(v)) out[k] = exact(v * factor);
    return out;
  };
  const numText = n => String(round(n, 2));

  // '2 servings' -> { n: 2, unit: 'serving' }; 'serving' -> { n: 1, unit: 'serving' }; '250 ml' -> { n: 250, unit: 'ml' }
  function parseAmount(text) {
    const m = /^\s*(\d+(?:[.,]\d+)?)?\s*(.*?)\s*$/.exec(String(text || ''));
    return { n: m[1] ? Number(m[1].replace(',', '.')) : 1, unit: singular(m[2].toLowerCase()) };
  }
  function singular(unit) {
    if (!unit || MEASURES.has(unit) || !/^[a-z]+$/.test(unit)) return unit;
    if (/(ch|sh|ss|x)es$/.test(unit)) return unit.slice(0, -2);   // sandwiches, glasses, boxes
    return /[^s]s$/.test(unit) ? unit.slice(0, -1) : unit;
  }
  function plural(unit, n) {
    if (n === 1 || !unit || MEASURES.has(unit) || SIZES.has(unit) || !/^[a-z]+$/.test(unit)) return unit;
    return /(ch|sh|s|x)$/.test(unit) ? `${unit}es` : `${unit}s`;
  }
  // A stored amount as the screen says it, by the same rule as the sheet's unit: MyNetDiary's '1 servings' reads
  // '1 serving', '0.5 serving' reads '0.5 servings'. The entry keeps its text, so his usual amounts still count together.
  function amountText(amount) {
    const m = /^(\d+(?:[.,]\d+)?) ([a-z]+)$/.exec(String(amount || '').trim());
    return m ? `${m[1]} ${plural(singular(m[2]), Number(m[1].replace(',', '.')))}` : amount;
  }

  // Text the user typed as a positive number, or why it is not one.
  function readNumber(text, max, digits) {
    const t = String(text).trim();
    if (!t) return { error: 'empty' };
    if (/^-/.test(t)) return { error: 'zero' };
    if (!/^(\d+([.,]\d*)?|[.,]\d+)$/.test(t)) return { error: 'nan', text: t };
    const v = round(Number(t.replace(',', '.')), digits);
    if (!(v > 0)) return { error: 'zero' };
    if (v > max) return { error: 'big' };
    return { value: v };
  }

  const validDate = d => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return false;
    const [y, m, day] = d.split('-').map(Number), t = new Date(y, m - 1, day);
    return t.getFullYear() === y && t.getMonth() === m - 1 && t.getDate() === day;
  };
  const shortDay = d => { const [, m, day] = d.split('-').map(Number); return `${day} ${MON[m - 1]}`; };
  function daysBefore(date, days) {
    const [y, m, d] = date.split('-').map(Number), t = new Date(y, m - 1, d - days);
    return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
  }
  const words = text => String(text || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/['\u2019`]/g, '')
    .split(/[^\p{L}\p{N}%+]+/u).filter(Boolean);

  const drawing = (food, size) => (window.PantryDrawing ? window.PantryDrawing(food, size) : '');
  const depth = () => (history.state && history.state.depth) || 0;

  // ── how a food is measured and what its usual amount holds ────────
  // grams for a food with per100; else its servings, priced from its last entry in that unit, or from a serving label.
  function measure(doc, food, meal) {
    if (food.per100) return { kind: 'grams' };
    const usual = P.usualAmounts(food.id, meal)[0];
    const unit = usual ? parseAmount(usual.amount).unit : null;
    if (usual) {
      let last = null, lastN = 0;
      doc.entries.forEach(e => {
        if (e.foodId !== food.id) return;
        const a = parseAmount(e.amount);
        if (a.unit === unit && a.n > 0 && (!last || e.date >= last.date)) { last = e; lastN = a.n; }
      });
      if (last) return { kind: 'servings', unit, last, lastN };
    }
    const serving = food.servings.find(s => isNum(s.kcal) && parseAmount(s.label).n > 0);
    if (!serving) return null;
    const a = parseAmount(serving.label);
    return { kind: 'servings', unit: a.unit, serving, servingN: a.n };
  }

  function servingTotals(m, n) {
    return m.last ? scale(m.last.totals, n / m.lastN) : { kcal: exact(m.serving.kcal * n / m.servingN) };
  }

  function totalsFor(food, m, n) { return m.kind === 'grams' ? P.totals(food, n) : servingTotals(m, n); }

  // { amount, grams, totals } that the + logs, or null when the food has no usual amount yet.
  function usualFor(doc, food, meal) {
    const m = measure(doc, food, meal);
    if (!m) return null;
    const u = P.usualAmounts(food.id, meal)[0];
    if (m.kind === 'grams') return u && isNum(u.grams) && u.grams > 0 ? { amount: u.amount, grams: u.grams, totals: P.totals(food, u.grams) } : null;
    if (u) {
      const a = parseAmount(u.amount);
      if (a.unit === m.unit && a.n > 0) return { amount: u.amount, grams: null, totals: servingTotals(m, a.n) };
    }
    return m.serving ? { amount: m.serving.label, grams: null, totals: servingTotals(m, m.servingN) } : null;
  }

  // ── the three lists and search ────────────────────────────────────
  function frequent(doc, meal, byId) {
    if (!doc.entries.length) return P.starter.map(s => s.food.id).filter(id => byId.has(id));
    const t = P.today(), from = daysBefore(t, WINDOW), by = new Map();
    doc.entries.forEach((e, i) => {
      if (e.meal !== meal || e.date < from || e.date > t || !byId.has(e.foodId)) return;
      const x = by.get(e.foodId) || { id: e.foodId, count: 0, last: '', at: -1 };
      x.count += 1;
      if (e.date >= x.last) { x.last = e.date; x.at = i; }
      by.set(e.foodId, x);
    });
    return [...by.values()].sort((a, b) => b.count - a.count || (a.last < b.last ? 1 : a.last > b.last ? -1 : b.at - a.at)).map(x => x.id);
  }

  function recent(doc, byId) {
    const t = P.today();
    const order = doc.entries.map((e, i) => [e, i]).filter(([e]) => e.date <= t && byId.has(e.foodId))
      .sort((a, b) => (a[0].date < b[0].date ? 1 : a[0].date > b[0].date ? -1 : b[1] - a[1]));
    const out = [];
    for (const [e] of order) {
      if (!out.includes(e.foodId)) out.push(e.foodId);
      if (out.length === RECENT) break;
    }
    return out;
  }

  const byName = (a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }) || (a.brand || '').localeCompare(b.brand || '', 'en', { sensitivity: 'base' });
  const mine = doc => [...doc.foods].sort(byName).map(f => f.id);

  function search(doc, meal, query) {
    const want = words(query);
    const t = P.today(), from = daysBefore(t, WINDOW), atMeal = new Map(), all = new Map();
    for (const e of doc.entries) {
      all.set(e.foodId, (all.get(e.foodId) || 0) + 1);
      if (e.meal === meal && e.date >= from && e.date <= t) atMeal.set(e.foodId, (atMeal.get(e.foodId) || 0) + 1);
    }
    return doc.foods.filter(f => { const have = words(`${f.name} ${f.brand || ''}`); return want.every(w => have.some(h => h.startsWith(w))); })
      .sort((a, b) => (atMeal.get(b.id) || 0) - (atMeal.get(a.id) || 0) || (all.get(b.id) || 0) - (all.get(a.id) || 0) || byName(a, b))
      .map(f => f.id);
  }

  // ── the shown screen ──────────────────────────────────────────────
  let S = null;   // { el, route, meal, dateArg, tab, query, ids, main, list, sheet, afterPop }

  const dateOf = () => S.dateArg || P.today();
  const mealWord = meal => LABEL[meal].toLowerCase();

  function header(eyebrow, title) {
    return `<header class="top back"><button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>`
      + `<div><p class="eyebrow" data-test="log-day">${P.esc(eyebrow)}</p><h1 class="title">${P.esc(title)}</h1></div></header>`;
  }

  // A route that names a meal or a day that does not exist, or a food that is not in the list.
  function gone(el, title, text, meal, dateArg) {
    S = null;
    if (fitter) fitter.disconnect();
    el.innerHTML = `${header(dateArg && validDate(dateArg) ? P.dayLabel(dateArg) : P.dayLabel(P.today()), title)}
      <div class="log-gone"><div class="banner" role="alert">${P.icon('alert')}<div>${text}</div></div>
      ${meal ? `<button class="btn sec" type="button" data-act="list">Show ${P.esc(mealWord(meal))} foods</button>` : ''}</div>`;
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    const list = el.querySelector('[data-act="list"]');
    if (list) list.addEventListener('click', () => P.go('add', meal, dateArg && validDate(dateArg) ? dateArg : undefined));
  }

  function badArgs(el, mealArg, dateArg) {
    if (mealArg !== undefined && !MEALS.includes(mealArg)) {
      gone(el, 'Add food', `<b>There is no meal called “${P.esc(mealArg)}”.</b> Go back and pick breakfast, lunch, dinner or snacks.`);
      return true;
    }
    if (dateArg !== undefined && !validDate(dateArg)) {
      gone(el, LABEL[mealArg || P.mealNow()], `<b>“${P.esc(dateArg)}” is not a day.</b> Go back and open the day from the day strip.`);
      return true;
    }
    return false;
  }

  function renderList(el, route, mealArg, dateArg) {
    const meal = mealArg || P.mealNow();
    S = { el, route, meal, dateArg, tab: 'frequent', query: '', ids: null, sheet: null };
    el.innerHTML = `<div class="log-main">
      ${header(P.dayLabel(dateOf()), LABEL[meal])}
      <div class="log-head">
        <div class="log-search">
          <label class="log-field">${icon('search')}<input type="search" name="q" placeholder="Food or brand" aria-label="Search food or brand"
            autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search">
            <button class="log-clear" type="button" data-act="clear" aria-label="Clear the search" hidden>${P.icon('x')}</button></label>
          <button class="ibtn log-scan" type="button" data-act="scan" aria-label="Scan a barcode">${P.icon('scan')}</button>
        </div>
        <div class="log-tabs" role="tablist" aria-label="Foods">
          ${[['frequent', 'Frequent'], ['recent', 'Recent'], ['mine', 'My foods']].map(([k, t]) => `<button class="log-tab" type="button" role="tab"
            id="log-tab-${k}" data-tab="${k}" aria-controls="log-list" aria-selected="${k === S.tab}">${t}</button>`).join('')}
        </div>
      </div>
      <div class="log-list" id="log-list" role="tabpanel" aria-labelledby="log-tab-frequent"></div>
    </div>`;
    S.main = el.querySelector('.log-main');
    S.list = el.querySelector('.log-list');
    const q = el.querySelector('input[name="q"]');
    const clear = el.querySelector('[data-act="clear"]');
    const tabs = el.querySelector('.log-tabs');
    const setQuery = text => {
      S.query = text;
      clear.hidden = !text;
      tabs.hidden = !!text.trim();
      if (text.trim()) { S.list.removeAttribute('aria-labelledby'); S.list.setAttribute('aria-label', 'Search results'); }
      else { S.list.setAttribute('aria-labelledby', `log-tab-${S.tab}`); S.list.removeAttribute('aria-label'); }
      drawRows(true);
    };
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    el.querySelector('[data-act="scan"]').addEventListener('click', () => P.go('scan', S.meal, S.dateArg));
    q.addEventListener('input', () => setQuery(q.value));
    q.addEventListener('keydown', e => {
      if (e.key === 'Escape' && q.value) { e.preventDefault(); q.value = ''; setQuery(''); }
      if (e.key === 'Enter') { e.preventDefault(); q.blur(); }
    });
    clear.addEventListener('click', () => { q.value = ''; setQuery(''); q.focus(); });
    tabs.addEventListener('click', e => {
      const tab = e.target.closest('[data-tab]');
      if (!tab || tab.dataset.tab === S.tab) return;
      S.tab = tab.dataset.tab;
      tabs.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', String(b === tab)));
      S.list.setAttribute('aria-labelledby', tab.id);
      S.list.classList.remove('log-swap');
      void S.list.offsetWidth;
      S.list.classList.add('log-swap');
      drawRows(true);
    });
    S.list.addEventListener('click', e => {
      const act = e.target.closest('[data-act]');
      if (!act) return;
      if (act.dataset.act === 'scan') { P.go('scan', S.meal, S.dateArg); return; }
      const row = act.closest('[data-id]');
      if (!row) return;
      if (act.dataset.act === 'open') openSheet(row.dataset.id, { push: S.route === 'add' });
      if (act.dataset.act === 'plus') plus(row.dataset.id);
    });
    drawRows(true);
    if (fitter) { fitter.disconnect(); fitter.observe(el.querySelector('.log-head')); }
    const list = S.list;
    if (document.fonts) document.fonts.ready.then(() => { if (S && S.list === list) fitRows(); });
  }

  // The rows of the shown tab or search. recompute = false keeps the order (a change while the list is open).
  function drawRows(recompute) {
    const doc = P.doc();
    const byId = new Map(doc.foods.map(f => [f.id, f]));
    const query = S.query.trim();
    if (recompute || !S.ids) {
      S.ids = query ? search(doc, S.meal, query) : S.tab === 'frequent' ? frequent(doc, S.meal, byId) : S.tab === 'recent' ? recent(doc, byId) : mine(doc);
    }
    const foods = S.ids.map(id => byId.get(id)).filter(Boolean);
    S.list.innerHTML = foods.length ? `<ul class="rows">${foods.map(f => row(doc, f)).join('')}</ul>` : empty(doc, query);
    fitRows();
  }

  function row(doc, food) {
    const u = usualFor(doc, food, S.meal);
    const amount = u ? amountText(u.amount) : food.per100 ? 'per 100 g' : '';
    const sub = [food.brand, amount].filter(Boolean).join(', ');
    // brand and amount in their own spans, so fitRows can shorten the brand alone; the text still reads "Brand, 350 g"
    const subHtml = food.brand && amount ? `<span class="b">${P.esc(food.brand)},</span> <span class="a">${P.esc(amount)}</span>`
      : amount ? `<span class="a">${P.esc(amount)}</span>` : P.esc(sub);
    const kcal = u ? P.fmt(u.totals.kcal) : food.per100 ? P.fmt(food.per100.kcal) : '';
    const name = [food.name, sub, kcal && `${kcal} kcal`].filter(Boolean).join(', ');
    const add = u ? `Add ${amountText(u.amount)} of ${food.name}` : `Choose an amount of ${food.name}`;
    return `<li class="fr log-row" data-id="${P.esc(food.id)}">`
      + `<button class="log-open" type="button" data-act="open" aria-label="${P.esc(name)}"><span class="log-food">${drawing(food, 32)}</span>`
      + `<span class="t"><span class="name">${P.esc(food.name)}</span><span class="sub">${subHtml}</span></span><span class="k">${kcal}</span></button>`
      + `<button class="log-plus" type="button" data-act="plus" aria-label="${P.esc(add)}">${P.icon('plus')}</button></li>`;
  }

  // The usual amount is what the + logs, so it never ends in an ellipsis. When brand and amount do not fit their
  // line, the brand gives way: shortened with its own ellipsis, or left out when less than MIN_BRAND would show
  // ("C…" says nothing). An amount longer than the line on its own moves the kcal up beside the name (log-long)
  // and takes the whole line; only an amount longer than that is cut. Measured after every draw, when the screen's
  // width or text size changes (fitter, on the header) and once the font has loaded; reads, then writes, per pass.
  const MIN_BRAND = 2.5;   // em of the subtitle's text
  const fitter = typeof ResizeObserver === 'function' ? new ResizeObserver(() => fitRows()) : null;
  function fitRows() {
    if (!S || !S.list || !S.list.isConnected) return;
    const rows = [...S.list.querySelectorAll('.log-open')].map(open => ({
      open, sub: open.querySelector('.sub'), b: open.querySelector('.sub .b'), a: open.querySelector('.sub .a'),
    })).filter(r => r.a);
    const reset = list => list.forEach(r => { if (r.b) { r.b.hidden = false; r.b.style.maxWidth = ''; } });
    const measure = list => list.map(r => {
      const s = r.sub.getBoundingClientRect(), a = r.a.getBoundingClientRect(), b = r.b && r.b.getBoundingClientRect();
      const aw = r.a.scrollWidth > r.a.clientWidth ? r.a.scrollWidth : a.width;   // its own width, even when the line caps it
      return { room: s.width, a: aw, b: b ? b.width : 0, gap: b ? a.left - b.right : 0, em: parseFloat(getComputedStyle(r.sub).fontSize) };
    });
    const place = (r, m) => {
      if (!r.b || m.b + m.gap + m.a <= m.room + 0.5) return;
      const left = Math.floor(m.room - m.gap - m.a - 0.5);
      if (left >= MIN_BRAND * m.em) r.b.style.maxWidth = `${left}px`;
      else r.b.hidden = true;
    };
    rows.forEach(r => r.open.classList.remove('log-long'));
    reset(rows);
    const long = [];
    measure(rows).forEach((m, i) => { if (m.a > m.room + 0.5) long.push(rows[i]); else place(rows[i], m); });
    if (!long.length) return;
    long.forEach(r => r.open.classList.add('log-long'));
    measure(long).forEach((m, i) => { if (m.a > m.room + 0.5) { if (long[i].b) long[i].b.hidden = true; } else place(long[i], m); });
  }

  function empty(doc, query) {
    const scan = `<button class="btn sec" type="button" data-act="scan">${P.icon('scan')}Scan a barcode</button>`;
    if (query) return `<div class="log-empty"><p class="note">No food matches “${P.esc(query)}”. Scan its barcode to add it.</p>${scan}</div>`;
    if (S.tab === 'frequent') return `<div class="log-empty"><p class="note">Nothing logged at ${mealWord(S.meal)} in the last ${WINDOW} days. Search, or look in Recent and My foods.</p></div>`;
    if (S.tab === 'recent') return '<div class="log-empty"><p class="note">Nothing logged yet. The foods you log show here, newest first.</p></div>';
    return `<div class="log-empty"><p class="note">No foods yet. Scan a product to add your first.</p>${scan}</div>`;
  }

  // ── logging ───────────────────────────────────────────────────────
  function newId(doc, date) {
    const taken = new Set(doc.entries.map(e => e.id));
    let id;
    do { id = `${date}-p${crypto.getRandomValues(new Uint32Array(1))[0].toString(36)}`; } while (taken.has(id));
    return id;
  }

  // Saves one entry; returns its id. Throws the core's sentence when nothing can be saved.
  function log(foodId, meal, date, amount, grams, totals) {
    let id;
    P.change(d => {
      id = newId(d, date);
      d.entries.push({ id, date, meal, foodId, amount, grams, totals });
    });
    return id;
  }

  function added(amount, meal, date, id) {
    const when = date === P.today() ? '' : ` on ${shortDay(date)}`;
    P.toast(`${amountText(amount)} added to ${mealWord(meal)}${when}`, { action: 'Undo', onAction: () => undo(id) });
  }

  function undo(id) {
    if (!P.doc().entries.some(e => e.id === id)) return;
    try {
      P.change(d => {
        d.entries = d.entries.filter(e => e.id !== id);
        (d.removed = d.removed || []).push({ id, at: new Date().toISOString() });
      });
    } catch (x) { P.toast(x.message); }
  }

  function plus(foodId) {
    const doc = P.doc();
    const food = doc.foods.find(f => f.id === foodId);
    if (!food) { P.toast('This food is no longer in your list.'); return; }
    const u = usualFor(doc, food, S.meal);
    if (!u) { openSheet(foodId, { push: S.route === 'add' }); return; }
    const meal = S.meal, date = dateOf();
    let id;
    try { id = log(foodId, meal, date, u.amount, u.grams, u.totals); } catch (x) { P.toast(x.message); return; }
    added(u.amount, meal, date, id);
  }

  // ── the gram sheet ────────────────────────────────────────────────
  function openSheet(foodId, { push }) {
    const doc = P.doc();
    const food = doc.foods.find(f => f.id === foodId);
    if (!food || !S) return;
    if (S.sheet) removeSheet(S.sheet);
    S.el.querySelectorAll('.log-layer').forEach(l => l.remove());   // one still sliding out
    if (push) history.pushState({ ...(history.state || {}), depth: depth() + 1, logSheet: foodId }, '', location.href);
    const sheet = buildSheet(doc, food);
    S.sheet = sheet;
    S.main.inert = true;
    S.el.appendChild(sheet.layer);
    sheet.form.focus({ preventScroll: true });
  }

  // Closing asks history first when the sheet has its own entry, so the back gesture and the scrim agree.
  function requestClose() {
    if (!S || !S.sheet) return;
    if (S.route === 'food') { P.back(); return; }
    if (history.state && history.state.logSheet === S.sheet.foodId) history.back();
    else closeSheet();
  }

  function closeSheet() {
    const sheet = S && S.sheet;
    if (!sheet) return;
    S.sheet = null;
    S.main.inert = false;
    sheet.layer.classList.add('log-out');
    setTimeout(() => sheet.layer.remove(), 220);
    const opener = [...S.list.querySelectorAll('.log-row')].find(r => r.dataset.id === sheet.foodId);
    if (opener) opener.querySelector('.log-open').focus({ preventScroll: true });
  }

  function removeSheet(sheet) { sheet.layer.remove(); if (S && S.sheet === sheet) { S.sheet = null; S.main.inert = false; } }

  function buildSheet(doc, food) {
    const m = measure(doc, food, S.meal);
    const grams = !m || m.kind === 'grams';
    const unit = grams ? 'g' : m.unit;
    let start = m ? startFor(food, m, S.meal) : '';
    let chips = m ? chipList(food, m, S.meal) : [];
    let touched = false;   // he typed or picked an amount: another meal radio keeps it
    const per = !m ? 'No grams or servings are known for this food.'
      : grams ? `${P.fmt(food.per100.kcal)} kcal per 100 g`
        : MEASURES.has(unit) ? `${P.fmt(servingTotals(m, 100).kcal)} kcal per 100 ${unit}` : `${P.fmt(servingTotals(m, 1).kcal)} kcal per ${unit}`;
    const fieldName = grams ? 'Grams' : MEASURES.has(unit) ? `Amount in ${unit}` : `Number of ${plural(unit, 2)}`;

    const layer = document.createElement('div');
    layer.className = 'log-layer';
    layer.innerHTML = `<button class="log-scrim" type="button" tabindex="-1" aria-label="Close"></button>
      <form class="log-sheet" role="dialog" aria-modal="true" aria-labelledby="log-sheet-name" tabindex="-1" novalidate>
        <div class="log-scroll">
          <span class="log-handle" aria-hidden="true"></span>
          <span class="log-hero">${drawing(food, 78)}</span>
          <h2 class="log-name" id="log-sheet-name">${P.esc(food.name)}</h2>
          <p class="log-per">${food.brand ? `${P.esc(food.brand)}, ` : ''}${per}</p>
          <div class="log-amt">
            <label class="log-g"><input name="amount" inputmode="decimal" autocomplete="off" enterkeyhint="done" aria-label="${P.esc(fieldName)}"
              value="${start}"><small data-test="unit">${P.esc(unit)}</small></label>
            <output class="disp log-k" aria-live="polite"><span data-test="portion-kcal"></span><small>kcal</small></output>
          </div>
          <p class="err log-err" role="alert" hidden></p>
          <div class="log-chips" role="group" aria-label="Usual amounts" hidden></div>
          <div class="log-portion" hidden><span class="eyebrow">This portion</span><div class="log-bars" aria-hidden="true"></div><div class="log-macros"></div></div>
          <button class="log-more" type="button" aria-expanded="false" aria-controls="log-nutr"${m ? '' : ' hidden'}>All nutrients${icon('down')}</button>
          <div class="log-nutr" id="log-nutr" hidden></div>
          <fieldset class="log-meals"><legend class="log-vh">Meal</legend>
            ${MEALS.map(k => `<label class="log-meal"><input type="radio" name="meal" value="${k}"${k === S.meal ? ' checked' : ''}><span>${LABEL[k]}</span></label>`).join('')}
          </fieldset>
        </div>
        <div class="log-foot"><button class="btn" type="submit"></button></div>
      </form>`;

    const form = layer.querySelector('form');
    const input = form.elements.amount;
    const kcalOut = form.querySelector('[data-test="portion-kcal"]');
    const unitOut = form.querySelector('[data-test="unit"]');
    const err = form.querySelector('.err');
    const submit = form.querySelector('[type="submit"]');
    const portion = form.querySelector('.log-portion');
    const more = form.querySelector('.log-more');
    const nutr = form.querySelector('.log-nutr');
    const chipBox = form.querySelector('.log-chips');
    const sheet = { foodId: food.id, layer, form, refresh: null, done: false };
    const meal = () => form.elements.meal.value;
    const read = () => readNumber(input.value, grams ? MAX_GRAMS : 1000, grams ? 1 : 2);

    function refresh() {
      const f = P.doc().foods.find(x => x.id === food.id) || food;
      const r = m ? read() : { error: 'none' };
      const n = r.value;
      const totals = n ? totalsFor(f, m, n) : null;
      kcalOut.textContent = totals ? P.fmt(totals.kcal) : '–';
      if (!grams && m) unitOut.textContent = plural(unit, n || 2);
      chipBox.querySelectorAll('.log-chip').forEach((el, i) => el.setAttribute('aria-pressed', String(n !== undefined && i === chips.findIndex(c => c.n === n))));
      submit.textContent = `Add to ${mealWord(meal())}`;
      portion.hidden = !m || !strip(portion, m ? totalsFor(f, m, n || 100) : {}, totals);
      if (!nutr.hidden && m) nutrients(nutr, f, m, totals);
    }
    sheet.refresh = refresh;

    // The chips belong to the meal the radio names, as Pantry.usualAmounts(foodId, meal) has them.
    function drawChips() {
      chipBox.hidden = !chips.length;
      chipBox.innerHTML = chips.map((c, i) => `<button class="log-chip" type="button" data-i="${i}" aria-pressed="false"
        aria-label="${P.esc(c.label + (c.count ? `, logged ${c.count} times` : ''))}">${P.esc(c.label)}${c.count ? `<em>${c.count}×</em>` : ''}</button>`).join('');
    }

    const fail = text => { err.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`; err.hidden = false; };
    const example = () => (grams ? 'Type the grams, for example 350.'
      : MEASURES.has(unit) ? `Type the ${unit}, for example ${start || 250}.` : `Type the number of ${plural(unit, 2)}, for example ${start || 1}.`);
    const say = r => ({
      empty: example(),
      nan: `“${r.text}” is not a number. ${example()}`,
      zero: `The amount must be more than 0. ${example()}`,
      big: grams ? `That is more than 10 kg. ${example()}` : `That is more than 1,000. ${example()}`,
    }[r.error]);

    layer.querySelector('.log-scrim').addEventListener('click', requestClose);
    input.addEventListener('focus', () => input.select());
    input.addEventListener('input', () => { touched = true; err.hidden = true; refresh(); });
    input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); input.blur(); } });
    form.addEventListener('change', e => {
      if (e.target.name !== 'meal') return;
      if (m) {
        chips = chipList(food, m, meal());
        drawChips();
        if (!touched) { start = startFor(food, m, meal()); input.value = String(start); err.hidden = true; }
      }
      refresh();
    });
    chipBox.addEventListener('click', e => {
      const chip = e.target.closest('.log-chip');
      if (!chip) return;
      touched = true;
      input.value = String(chips[Number(chip.dataset.i)].n);
      err.hidden = true;
      refresh();
    });
    more.addEventListener('click', () => {
      const open = nutr.hidden;
      nutr.hidden = !open;
      more.setAttribute('aria-expanded', String(open));
      more.innerHTML = `All nutrients${icon(open ? 'up' : 'down')}`;
      refresh();
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      if (sheet.done) return;   // logged; on its way to Today
      if (!m) { fail('This food has no grams or servings to log. Open it from Scan to add its label values.'); return; }
      const r = read();
      if (r.error) { fail(say(r)); input.focus(); return; }
      const f = P.doc().foods.find(x => x.id === food.id);
      if (!f) { fail('This food is no longer in your list.'); return; }
      const chip = chips.find(c => c.n === r.value);
      const amount = chip ? chip.amount : grams ? `${numText(r.value)} g` : `${numText(r.value)} ${plural(unit, r.value)}`;
      const when = meal(), date = dateOf(), dateArg = S.dateArg;
      let id;
      try { id = log(f.id, when, date, amount, grams ? r.value : null, totalsFor(f, m, r.value)); } catch (x) { fail(x.message); return; }
      sheet.done = true;
      S.sheet = null;
      toToday(food.id, dateArg, () => added(amount, when, date, id));
    });
    drawChips();
    refresh();
    return sheet;
  }

  // "Add to <meal>" returns with Pantry.go('today', date), and Back from Today then shows the meal's list, never this
  // sheet again armed for the food just logged: the sheet's own history entry is popped first (the popstate below
  // goes on to Today), and a food route's entry becomes the meal's list.
  function toToday(foodId, dateArg, then) {
    const go = () => { P.go('today', dateArg); then(); };
    const st = history.state || {};
    if (S.route === 'add' && st.logSheet === foodId) { S.afterPop = go; history.back(); return; }
    if (S.route === 'food') history.replaceState(st, '', `#/${['add', S.meal, dateArg].filter(a => a !== undefined).map(encodeURIComponent).join('/')}`);
    go();
  }

  // The amount the sheet starts at for a meal: his usual there, in the unit the sheet measures.
  function startFor(food, m, meal) {
    const u = P.usualAmounts(food.id, meal)[0];
    if (m.kind === 'grams') return u && isNum(u.grams) && u.grams > 0 ? u.grams : '';
    const a = u ? parseAmount(u.amount) : null;
    if (a && a.unit === m.unit && a.n > 0) return a.n;
    return m.serving ? m.servingN : '';
  }

  // His usual amounts for this food at that meal as chips, most often first; the same amount typed two ways is one chip.
  function chipList(food, m, meal) {
    const out = [];
    const put = (label, amount, n, count) => {
      const same = out.find(c => c.n === n);
      if (same) same.count += count; else out.push({ label: amountText(label), amount, n, count });
    };
    for (const u of P.usualAmounts(food.id, meal)) {
      if (m.kind === 'grams') { if (isNum(u.grams) && u.grams > 0) put(u.amount, u.amount, u.grams, u.count); continue; }
      const a = parseAmount(u.amount);
      if (a.unit === m.unit && a.n > 0) put(u.amount, u.amount, a.n, u.count);
    }
    if (m.kind === 'servings' && !m.last) {
      for (const s of food.servings) { const a = parseAmount(s.label); if (a.unit === m.unit && a.n > 0 && isNum(s.kcal)) put(s.label, s.label, a.n, 0); }
    }
    return out.slice(0, CHIPS);
  }

  // The portion's protein / carbs / fat as the B1 strip: width = share of their kcal. False when none is known.
  function strip(el, shape, totals) {
    const kc = MACROS.map(([k, , f]) => (isNum(shape[k]) ? shape[k] * f : null));
    const sum = kc.reduce((a, v) => a + (v || 0), 0);
    if (!MACROS.some(([k]) => isNum(shape[k]))) return false;
    el.querySelector('.log-bars').innerHTML = MACROS.map(([, label], i) => {
      const share = sum > 0 && kc[i] ? kc[i] / sum * 100 : 0;
      const bg = i % 2 ? 'var(--log-g3)' : 'var(--log-g1)', fg = i % 2 ? 'var(--ink)' : 'var(--canvas)';
      return `<span style="flex:${Math.max(share, 1)} 1 0;background:${bg};color:${fg}" title="${label} ${Math.round(share)}%">${share >= 12 ? `${Math.round(share)}%` : ''}</span>`;
    }).join('');
    el.querySelector('.log-macros').innerHTML = MACROS.map(([k, label]) => {
      const v = totals && isNum(totals[k]) ? `${P.fmt(totals[k], 1)} g` : '–';
      return `<span>${label} <b>${v}</b></span>`;
    }).join('');
    return true;
  }

  function nutrients(el, food, m, totals) {
    const shape = totalsFor(food, m, m.kind === 'grams' ? 100 : 1);
    const value = (k, unit) => {
      if (!totals || !isNum(totals[k])) return '–';
      const v = totals[k];
      return `${P.fmt(v, unit === 'g' || v < 10 ? 1 : 0)}${unit ? ` ${unit}` : ''}`;
    };
    const rows = [...MAIN, ...MORE.filter(([k]) => isNum(shape[k])),
      ...Object.keys(shape).filter(k => !SHOWN.has(k)).map(k => [k, k.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()).replace(/ (\w)/g, (s, c) => ` ${c.toLowerCase()}`), ''])];
    el.innerHTML = rows.map(([k, label, unit]) => `<div><span>${P.esc(label)}</span><b>${value(k, unit)}</b></div>`).join('');
  }

  // ── routes ────────────────────────────────────────────────────────
  function update() {
    if (!S) return;
    const day = S.el.querySelector('[data-test="log-day"]');
    if (day) day.textContent = P.dayLabel(dateOf());
    drawRows(false);
    if (S.sheet) {
      if (P.doc().foods.some(f => f.id === S.sheet.foodId)) S.sheet.refresh();
      else closeSheet();
    }
  }
  const leave = () => { S = null; if (fitter) fitter.disconnect(); };

  P.view('add', {
    render(el, mealArg, dateArg) {
      if (badArgs(el, mealArg, dateArg)) return;
      renderList(el, 'add', mealArg, dateArg);
      const want = history.state && history.state.logSheet;
      if (want && P.doc().foods.some(f => f.id === want)) openSheet(want, { push: false });
    },
    update, leave,
  });

  P.view('food', {
    render(el, id, mealArg, dateArg) {
      if (badArgs(el, mealArg, dateArg)) return;
      const meal = mealArg || P.mealNow();
      if (!id || !P.doc().foods.some(f => f.id === id)) {
        gone(el, LABEL[meal], '<b>This food is not in your list.</b> It may have been deleted, or the link is from before an import.', meal, dateArg);
        return;
      }
      renderList(el, 'food', mealArg, dateArg);
      openSheet(id, { push: false });
    },
    update, leave,
  });

  // The phone's back gesture over an open sheet pops the sheet's own history entry (same address): close it.
  window.addEventListener('popstate', () => {
    if (!S || S.route !== 'add') return;
    if (S.afterPop) { const next = S.afterPop; S.afterPop = null; next(); return; }   // a logged sheet's entry is gone: on to Today
    const want = history.state && history.state.logSheet;
    if (S.sheet && S.sheet.foodId !== want) closeSheet();
    else if (!S.sheet && want && P.doc().foods.some(f => f.id === want)) openSheet(want, { push: false });
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && S && S.sheet) { e.preventDefault(); requestClose(); } });
})();

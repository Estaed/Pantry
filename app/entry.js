/* Entry: edit, move or delete one logged entry ('#/entry/<id>'). The content and order of design/screens.html
   → 8 (drawing, name, meal and date, the amount in big type with its kcal, usual amounts, move chips, Delete and Save),
   drawn as its own screen (design/deviations.md).
   The amount is grams, or the count of servings for an entry logged without grams. A new amount scales the
   entry's own totals by new ÷ old; they are never recomputed from the food, so an imported MyNetDiary entry
   keeps MyNetDiary's values. An amount with no single number to scale ("a bowl") stays as logged and only the
   meal can change. Moving changes only the meal: id, date, amount and totals stay. Save writes only what he
   changed, so a change made elsewhere while the screen is open is kept, and says it in a toast ("Saved, 200 g") with
   the food's drawing and Undo, which puts the stored entry back exactly as it was. Delete removes
   the entry, appends { id, at } to doc.removed and offers Undo in a toast, which puts the same entry back at
   the same index and drops that line. Save and Delete return with Pantry.go('today', date). */
(() => {
  'use strict';
  const P = window.Pantry;
  const MEALS = [['breakfast', 'Breakfast'], ['lunch', 'Lunch'], ['dinner', 'Dinner'], ['snacks', 'Snacks']];
  const MEAL = Object.fromEntries(MEALS);
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  // The date as design 8 writes it under the name ('8 Aug'); an entry from another year also says its year.
  const shortDay = date => {
    const [y, m, d] = date.split('-').map(Number);
    return `${d} ${MON[m - 1]}${String(y) === P.today().slice(0, 4) ? '' : ` ${y}`}`;
  };
  const MAX = { g: 10000, n: 100 };
  const isNum = v => typeof v === 'number' && Number.isFinite(v);
  // The typo guard for a new amount: the unit's limit, or ten times the logged amount when that is more ("250 ml").
  const cap = (limit, base) => Math.max(limit, isNum(base) ? base * 10 : 0);

  P.css(`
    .entry-form { display: flex; flex-direction: column; flex: 1; }
    .entry-body { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px 20px 8px; text-align: center; }
    .entry-hero { width: 84px; height: 84px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); }
    .entry-hero svg { width: 78px; height: 78px; }
    .entry-name { margin: 0; max-width: 100%; font: 700 1.1875rem/1.3 var(--font-sans); overflow-wrap: anywhere; }
    .entry-meta { margin: -10px 0 0; max-width: 100%; font: 500 0.8125rem/1.4 var(--font-sans); color: var(--ink-muted); overflow-wrap: anywhere; }
    .entry-amt { display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline; gap: 4px 18px; max-width: 100%; margin-top: 4px; }
    /* the number and its unit share one underline and one text baseline (inline, not flex: an input's flex
       baseline sits off its text) */
    .entry-amt label { display: inline-block; max-width: 100%; padding: 0 4px 2px; border-bottom: 2px solid var(--primary); white-space: nowrap; }
    .entry-amt label:focus-within { box-shadow: inset 0 -1px 0 var(--primary); }
    .entry-amt input {
      display: inline-block; vertical-align: baseline; width: 5ch; padding: 0; border: 0; border-radius: 0;
      background: none; color: var(--ink); font-size: 2.75rem; line-height: 1.1; letter-spacing: -0.02em; text-align: right;
    }
    @supports (field-sizing: content) { .entry-amt input { width: auto; min-width: 2ch; field-sizing: content; } }
    .entry-amt input:focus { outline: none; }
    .entry-amt small { vertical-align: baseline; margin-left: 4px; font: 600 0.9375rem var(--font-sans); color: var(--ink-muted); letter-spacing: 0; }
    .entry-amt output { font-size: 1.75rem; line-height: 1.1; color: var(--ink-muted); white-space: nowrap; }
    .entry-amt .entry-fixed { max-width: 100%; font-size: 2rem; line-height: 1.15; color: var(--ink); overflow-wrap: anywhere; }
    .entry-err { display: flex; gap: 8px; align-items: center; justify-content: center; margin: 0; max-width: 100%; font: 600 0.8125rem/1.4 var(--font-sans); color: var(--danger); text-align: left; }
    .entry-err svg.i { width: 16px; height: 16px; }
    .entry-chips { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 8px; max-width: 100%; }
    .entry-lbl { font: 600 0.75rem/1.3 var(--font-sans); color: var(--ink-muted); }
    .entry-chip {
      min-height: 44px; max-width: 100%; padding: 0 14px; border: 1px solid var(--hairline-strong); border-radius: var(--r-chip);
      background: none; color: var(--ink); font: 600 0.875rem/1.2 var(--font-sans); overflow-wrap: anywhere;
      transition: background-color var(--fast), color var(--fast);
    }
    .entry-chip[aria-pressed="true"] { background: var(--action); color: var(--on-action); border-color: var(--action); }
    .entry-two .btn { flex: 1 1 0; min-width: 0; }
    .btn.entry-del, .btn.entry-del:active { background: transparent; color: var(--danger); box-shadow: inset 0 0 0 1px var(--danger); }
  `);

  // A number as typed: "500", "12.5", "12,5" and "1,000" (thousands, en-AU) read; anything else is NaN.
  function readNumber(text) {
    let t = String(text).replace(/\s+/g, '');
    t = /^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(t) ? t.replace(/,/g, '') : t.replace(',', '.');
    return /^-?(\d+\.?\d*|\.\d+)$/.test(t) ? Number(t) : NaN;
  }

  // Pantry.fmt's rounding, so the field, the chips and the check for a change all agree with what is shown.
  const round = (v, digits) => { const f = 10 ** digits; return Math.round(Number((v * f).toPrecision(12))) / f; };

  const VULGAR = { '¼': 1 / 4, '½': 1 / 2, '¾': 3 / 4, '⅓': 1 / 3, '⅔': 2 / 3, '⅛': 1 / 8, '⅜': 3 / 8, '⅝': 5 / 8, '⅞': 7 / 8 };
  // "1 servings" → { n: 1, unit: 'servings' }; "1 1/2 cups", "1½ cups", "1/2 cup", "1.5 slices" and "1,000 ml" read
  // their whole number. null when the amount does not start with a number, or the number runs on into more digits
  // or signs ("1-2 pieces"), so an amount is never scaled from part of its number.
  function parseAmount(amount) {
    const t = String(amount).trim();
    let m, n;
    if ((m = /^(\d+)\s+(\d+)\/(\d+)/.exec(t))) n = Number(m[1]) + Number(m[2]) / Number(m[3]);
    else if ((m = /^(\d+)\/(\d+)/.exec(t))) n = Number(m[1]) / Number(m[2]);
    else if ((m = /^(\d*)\s*([¼½¾⅓⅔⅛⅜⅝⅞])/.exec(t))) n = Number(m[1] || 0) + VULGAR[m[2]];
    else if ((m = /^(\d{1,3}(,\d{3})+(\.\d+)?|\d+([.,]\d+)?)/.exec(t))) n = readNumber(m[0]);
    else return null;
    const unit = t.slice(m[0].length).trim();
    return isNum(n) && !/^[\d/⁄.,+\-–¼-¾⅐-⅞]/.test(unit) ? { n, unit: unit || 'servings' } : null;
  }

  // What the big number edits: grams when the entry has them, else the count of its servings. digits: the decimals
  // the field shows and a typed amount keeps.
  function measure(e) {
    if (e.grams !== null) return { unit: 'g', base: e.grams, digits: 1, max: cap(MAX.g, e.grams) };
    const a = parseAmount(e.amount);
    return { unit: a ? a.unit : 'servings', base: a ? a.n : null, digits: 2, max: cap(MAX.n, a && a.n) };
  }

  // Every number in the entry's own totals × next ÷ base; anything else in totals stays as it is.
  function scale(totals, next, base) {
    const out = {};
    for (const [k, v] of Object.entries(totals)) out[k] = isNum(v) ? v * next / base : v;
    return out;
  }

  // His usual amounts at this meal (Pantry.usualAmounts, top three) in the entry's unit, then the entry's own.
  function chipsFor(e, m) {
    const out = [];
    const add = (value, amount) => {
      if (!(isNum(value) && value > 0)) return;
      const v = round(value, m.digits);   // what the field shows when the chip is tapped; exact is what is saved
      if (!out.some(c => c.value === v)) out.push({ value: v, exact: value, amount });
    };
    for (const u of P.usualAmounts(e.foodId, e.meal)) {
      if (out.length === 3) break;
      if (m.unit === 'g') { if (isNum(u.grams)) add(u.grams, u.amount); }
      else if (u.grams === null) { const a = parseAmount(u.amount); if (a && a.unit === m.unit) add(a.n, u.amount); }
    }
    add(m.base, e.amount);
    return out;
  }
  const isGramText = amount => /^\s*[\d.,]+\s*g\s*$/.test(amount);
  const chipLabel = (c, m) => (m.unit === 'g' && isGramText(c.amount) ? `${P.fmt(c.value, 1)} g` : c.amount);

  const header = (eyebrow, title) => `<header class="top back">`
    + `<button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>`
    + `<div><p class="eyebrow">${P.esc(eyebrow)}</p><h1 class="title">${P.esc(title)}</h1></div></header>`;

  let shown = null;   // { el, id, found, busy, drawn, untouched } while this screen is open

  function draw(el, id) {
    const doc = P.doc();
    const entry = id ? doc.entries.find(e => e.id === id) : undefined;
    shown = { el, id, found: Boolean(entry), busy: false, drawn: JSON.stringify(entry), untouched: () => true };
    if (!entry) {
      el.innerHTML = `${header('Edit entry', 'Not in your log')}
        <section class="sec"><p class="note">This entry is not in your log any more. It may have been deleted, here or on another device.</p></section>`;
      el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
      return;
    }

    const food = doc.foods.find(f => f.id === entry.foodId);
    const m = measure(entry);
    const fixed = !(isNum(m.base) && m.base > 0);    // nothing to scale from: only the meal can change
    const logged = typeof entry.amount === 'string' ? entry.amount.trim() : '';
    const start = fixed ? null : round(m.base, m.digits);   // the amount as the field shows it on opening
    const startText = fixed ? '' : P.fmt(m.base, m.digits);
    const chips = fixed ? [] : chipsFor(entry, m);
    const drawing = window.PantryDrawing ? window.PantryDrawing(food, 78) : '';
    const shownAmount = !fixed && m.unit === 'g' && !isGramText(entry.amount) ? `, ${entry.amount}` : '';
    const problem = P.problem();

    el.innerHTML = `${header('Your log', 'Edit entry')}
      ${problem ? `<div class="banner" role="alert">${P.icon('alert')}<div>${P.esc(problem)}</div></div>` : ''}
      <form class="entry-form" novalidate>
        <div class="entry-body">
          <div class="entry-hero">${drawing}</div>
          <h2 class="entry-name">${P.esc(food ? food.name : 'A food no longer in your list')}</h2>
          <p class="entry-meta">${MEAL[entry.meal]}, ${shortDay(entry.date)}${P.esc(shownAmount)}</p>
          <div class="entry-amt">
            ${fixed ? (logged ? `<span class="disp entry-fixed">${P.esc(logged)}</span>` : '')
              : `<label><input class="disp" name="amount" inputmode="decimal" autocomplete="off" enterkeyhint="done"
              aria-label="${m.unit === 'g' ? 'Grams' : P.esc(`Amount in ${m.unit}`)}" value="${P.esc(startText)}"><small>${P.esc(m.unit)}</small></label>`}
            <output class="disp" aria-live="polite"><span data-test="entry-kcal"></span><small> kcal</small></output>
          </div>
          <p class="entry-err" role="alert" hidden></p>
          ${fixed ? `<p class="note">${logged ? 'This amount cannot be scaled' : 'Logged without an amount'}, so only the meal can change.</p>` : ''}
          ${chips.length ? `<div class="entry-chips" role="group" aria-label="Usual amounts">${chips.map((c, i) =>
            `<button class="entry-chip" type="button" data-chip="${i}" aria-pressed="false">${P.esc(chipLabel(c, m))}</button>`).join('')}</div>` : ''}
          <div class="entry-chips" role="group" aria-label="Move to another meal"><span class="entry-lbl" aria-hidden="true">Move to</span>${MEALS
            .filter(([k]) => k !== entry.meal).map(([k, label]) =>
              `<button class="entry-chip" type="button" data-meal="${k}" aria-pressed="false" aria-label="Move to ${label.toLowerCase()}">${label}</button>`).join('')}</div>
        </div>
        <div class="bottom entry-two">
          <button class="btn entry-del" type="button" data-act="delete">Delete</button>
          <button class="btn" type="submit">Save</button>
        </div>
      </form>`;

    const form = el.querySelector('form');
    const input = form.elements.amount;
    const kcalOut = form.querySelector('[data-test="entry-kcal"]');
    const err = form.querySelector('.entry-err');
    let meal = entry.meal;

    // The typed amount, or the sentence that says what is wrong with it.
    const read = () => {
      const text = input.value.trim();
      const ask = m.unit === 'g' ? `Type the grams, for example ${P.fmt(m.base, 1)}.` : `Type the amount in ${m.unit}, for example ${P.fmt(m.base, 2)}.`;
      if (!text) return { error: ask };
      const v = readNumber(text);
      if (!Number.isFinite(v)) return { error: `"${text.slice(0, 12)}" is not a number. ${ask}` };
      const value = round(v, m.digits);
      if (value <= 0) return { error: `The amount has to be more than 0 ${m.unit}. To remove the entry, use Delete.` };
      if (value > m.max) return { error: `That is more than ${P.fmt(m.max)} ${m.unit}. Check the amount.` };
      return { value };
    };
    // The amount a typed value stands for: the logged one while the field still shows it, a usual amount's own
    // value when its chip is picked, else the value itself.
    const target = value => (value === start ? m.base : (chips.find(c => c.value === value) || { exact: value }).exact);
    const refresh = () => {
      if (fixed) kcalOut.textContent = P.fmt(entry.totals.kcal);
      else {
        const r = read();
        kcalOut.textContent = r.error ? '–' : P.fmt(entry.totals.kcal * target(r.value) / m.base);
        form.querySelectorAll('[data-chip]').forEach(b => b.setAttribute('aria-pressed', String(!r.error && chips[Number(b.dataset.chip)].value === r.value)));
      }
      form.querySelectorAll('[data-meal]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.meal === meal)));
    };
    const fail = text => { err.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`; err.hidden = false; };

    shown.untouched = () => meal === entry.meal && (fixed || input.value === startText);
    if (input) {
      input.addEventListener('focus', () => input.select());
      input.addEventListener('input', () => { err.hidden = true; refresh(); });
    }
    form.querySelectorAll('[data-chip]').forEach(b => b.addEventListener('click', () => {
      input.value = P.fmt(chips[Number(b.dataset.chip)].value, m.digits);
      err.hidden = true;
      refresh();
    }));
    form.querySelectorAll('[data-meal]').forEach(b => b.addEventListener('click', () => {
      meal = meal === b.dataset.meal ? entry.meal : b.dataset.meal;
      refresh();
    }));
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());

    form.addEventListener('submit', ev => {
      ev.preventDefault();
      let to = null, amount = null, said = null;   // the new amount, its text and the toast's words, when he changed it
      if (!fixed) {
        const r = read();
        if (r.error) { fail(r.error); input.focus(); return; }
        if (r.value !== start) {
          // The amount text he would recognise: a usual one with the same value, else the number and its unit.
          const chip = chips.find(c => c.value === r.value);
          to = target(r.value);
          amount = chip ? chip.amount : `${r.value} ${m.unit}`;
          said = chip ? chipLabel(chip, m) : `${P.fmt(r.value, m.digits)} ${m.unit}`;
        }
      }
      const moved = meal !== entry.meal;
      if (to !== null || moved) {
        shown.busy = true;
        let before = null;   // the stored entry as it was, for Undo
        try {
          // Only what he changed is written: a meal or an amount changed elsewhere since the screen opened stays.
          P.change(d => {
            const e = d.entries.find(x => x.id === entry.id);
            if (!e) throw new Error('This entry is not in your log any more, so it was not saved.');
            before = structuredClone(e);
            if (to !== null) {
              const now = measure(e);   // the stored entry's own amount, in case sync changed it meanwhile
              if (now.unit !== m.unit || !(isNum(now.base) && now.base > 0)) throw new Error('This entry changed on another device, so it was not saved. Open it again.');
              e.totals = scale(e.totals, to, now.base);
              e.amount = amount;
              if (e.grams !== null) e.grams = to;
            }
            if (moved) e.meal = meal;
          });
        } catch (x) { if (shown) shown.busy = false; fail(x.message); return; }
        // Raised before the return, so it lives through that screen change and not the next (Pantry.toast screens).
        const words = [said, moved ? `moved to ${MEAL[meal].toLowerCase()}` : null].filter(Boolean).join(', ');
        P.toast(`Saved, ${words}`, { action: 'Undo', drawing: art(food), onAction: () => unsave(before) });
      }
      P.go('today', entry.date);
    });

    form.querySelector('[data-act="delete"]').addEventListener('click', () => {
      let index = -1, removed = null;
      const at = new Date().toISOString();
      shown.busy = true;
      try {
        P.change(d => {
          index = d.entries.findIndex(x => x.id === entry.id);
          if (index < 0) throw new Error('This entry is not in your log any more.');
          removed = d.entries.splice(index, 1)[0];
          if (!Array.isArray(d.removed)) d.removed = [];
          d.removed.push({ id: entry.id, at });
        });
      } catch (x) { if (shown) shown.busy = false; fail(x.message); return; }
      P.haptic('delete');
      P.toast(`Deleted ${food ? food.name : 'the entry'}`, { action: 'Undo', drawing: art(food), onAction: () => undo(removed, index, at) });
      P.go('today', entry.date);
    });

    refresh();
  }

  // The food's drawing for a toast, read at the time (drawings.js loads after the features).
  const art = food => (window.PantryDrawing ? window.PantryDrawing(food, 32) : '');

  // Undo a save: the entry exactly as it was stored before it, in its place.
  function unsave(before) {
    P.haptic('undo');
    try {
      P.change(d => {
        const i = d.entries.findIndex(x => x.id === before.id);
        if (i < 0) throw new Error('This entry is not in your log any more, so it could not be put back.');
        d.entries[i] = structuredClone(before);
      });
    } catch (x) { P.toast(x.message); }
  }

  // Undo a delete: the same entry back at the same index, and its own removed line gone.
  function undo(entry, index, at) {
    P.haptic('undo');
    try {
      P.change(d => {
        if (Array.isArray(d.removed)) {
          const i = d.removed.findIndex(r => r.id === entry.id && r.at === at);
          if (i >= 0) d.removed.splice(i, 1);
          if (!d.removed.length) delete d.removed;
        }
        if (!d.entries.some(x => x.id === entry.id)) d.entries.splice(Math.min(index, d.entries.length), 0, structuredClone(entry));
      });
    } catch (x) { P.toast(x.message); }
  }

  P.view('entry', {
    render: draw,
    // Another tab or a sync pull removed (or brought back) the entry while it is open, or changed it before he
    // touched anything: redraw; else keep his typing (Save writes only what he changed).
    update(doc) {
      if (!shown || shown.busy) return;
      const now = doc.entries.find(e => e.id === shown.id);
      if (Boolean(now) !== shown.found || (now && shown.untouched() && JSON.stringify(now) !== shown.drawn)) draw(shown.el, shown.id);
    },
    leave() { shown = null; },
  });
})();

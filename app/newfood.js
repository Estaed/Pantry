/* New food ('#/newfood/<code>/<meal>/<date>', design/screens.html, 6. Found and 6b. From the label): what Pantry
   knows about a barcode that Scan did not find among his foods, and the way to make it one. Scan opens it, so the
   phone's back gesture returns there. Lookup order: his foods (the code was saved meanwhile: a way to its gram sheet),
   the store catalogue in the document (doc.catalogue, no network), Open Food Facts (skipped offline, and said so),
   then the label form. Found shows the product's name, store and values per 100 g, editable once; "This is my …"
   offers his foods with a matching name and attaches the barcode to the one he picks, so its history stays. Saving
   opens the gram sheet for the meal and day he came from ('food id meal date'). A barcode is never stored twice.
   Open Food Facts reports unknown values as 0, so only these are taken: energy-kcal_100g (else energy-kj_100g
   ÷ 4.184), proteins, carbohydrates, sugars, fat, saturated-fat, salt, fiber (_100g); a missing one stays absent,
   a 0 among them is kept. */
(() => {
  const P = window.Pantry;
  const OFF_URL = code => `https://world.openfoodfacts.org/api/v2/product/${code}.json?fields=product_name,brands,quantity,nutriments`;
  const OFF_FIELDS = [['proteins_100g', 'protein'], ['carbohydrates_100g', 'carbs'], ['sugars_100g', 'sugars'], ['fat_100g', 'fat'],
    ['saturated-fat_100g', 'satFat'], ['salt_100g', 'salt'], ['fiber_100g', 'fibre']];
  const OFF_WAIT_MS = 10000;
  const KJ_PER_KCAL = 4.184;
  const STORE = { coles: 'Coles', woolworths: 'Woolworths', off: 'Open Food Facts' };
  const MEALS = ['breakfast', 'lunch', 'dinner', 'snacks'];
  // The macros in the order every screen shows them: carbs, protein, fat (Pantry.MACROS). [key, label, unit, most per 100 g]
  const MACRO_LABEL = { carbs: 'Carbs', protein: 'Protein', fat: 'Fat' };
  const MACRO_FIELDS = P.MACROS.map(k => [k, MACRO_LABEL[k], 'g', 100]);
  // Found (design 6): the six values he checks, two across: energy and carbs, protein and fat, then sugars and saturated
  // fat (design 6 had protein first); a source's salt and fibre are kept as they came.
  const FOUND_FIELDS = [['kcal', 'Energy', 'kcal', 900], ...MACRO_FIELDS, ['sugars', 'Sugars', 'g', 100], ['satFat', 'Saturated fat', 'g', 100]];
  // From the label (design 6b): energy, carbs, protein and fat two across; sugars, salt and fibre are optional, one tap
  // away. Energy is typed in kJ or kcal, salt in g or as the mg of sodium an Australian panel prints (salt = sodium × 2.5).
  const LABEL_FIELDS = MACRO_FIELDS;
  // A unit switched with one tap where the field's unit sits: [value, unit shown, spoken, field label]
  const UNITS = {
    energyUnit: { key: 'energy', list: [['kJ', 'kJ', 'Energy in kJ'], ['kcal', 'kcal', 'Energy in kcal']] },
    saltUnit: { key: 'salt', list: [['g', 'g', 'Salt in g', 'Salt'], ['mg', 'mg', 'Sodium in mg', 'Sodium']] },
  };
  const CHEVRON = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>';
  const SWAP = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"/></svg>';
  const DOWN = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';

  const offCache = new Map();   // code -> { kind: 'found' | 'missing', product } for this session
  let shown = null;             // the shown screen: { el, code, meal, date, abort }

  P.css(`
    .newfood-form { display: flex; flex-direction: column; flex: 1; }
    .newfood-body { display: flex; flex-direction: column; gap: 14px; margin: 14px 20px 0; padding-bottom: 8px; }
    .newfood-src {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 12px 14px;
      background: var(--surface-1); border: 1px solid var(--hairline); border-radius: var(--r-card);
    }
    .newfood-art { width: 52px; height: 52px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); }
    .newfood-art svg { width: 42px; height: 42px; }
    .newfood-src .t { flex: 1 1 7rem; min-width: 0; }
    .newfood-src b { display: block; font: 700 0.9375rem/1.3 var(--font-sans); overflow-wrap: anywhere; }
    .newfood-src .t span { display: block; font: 500 0.8125rem/1.35 var(--font-sans); color: var(--ink-muted); }
    .newfood-tag {
      flex: none; margin-left: auto; display: inline-flex; align-items: center; min-height: 22px; padding: 1px 8px;
      border: 1px solid var(--hairline-strong); border-radius: var(--r-sm); font: 600 0.75rem/1.2 var(--font-sans); color: var(--ink-muted);
    }
    .newfood-picks .rows { margin: 0; }
    .newfood-picks .fr { min-height: 56px; }
    .newfood-dot { width: 40px; height: 40px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); }
    .newfood-dot svg { width: 32px; height: 32px; }
    .newfood-picks .fr > svg.i { width: 18px; height: 18px; color: var(--ink-muted); }
    /* the empty message row under the last line of fields adds one 6 px gap; the negative margin gives it back */
    .newfood-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 6px 12px; margin-bottom: -6px; }
    /* values stay two across down to 136 px each (a number and its unit fit), so a pack is checked at a glance */
    .newfood-grid.newfood-nums { grid-template-columns: repeat(auto-fit, minmax(min(100%, 136px), 1fr)); }
    .newfood-wide { grid-column: 1 / -1; }
    .newfood-field { display: flex; flex-direction: column; min-width: 0; }
    .newfood-field label { margin-bottom: 6px; font: 700 0.875rem/1.3 var(--font-sans); }
    /* in a grid a field takes three rows (label, box, message) and shares them with the field beside it: a label that
       wraps grows upward and a message opens below, so the boxes of one row stay level and keep their height */
    .newfood-grid > .newfood-field { display: grid; grid-row: span 3; grid-template-rows: subgrid; }
    .newfood-grid > .newfood-field > label { align-self: end; margin-bottom: 0; }
    .newfood-grid > .newfood-field > p { margin: 0 0 6px; }
    .newfood-in {
      min-width: 0; display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 14px;
      border-radius: var(--r-md); background: var(--surface-2);
    }
    .newfood-in:focus-within { box-shadow: inset 0 0 0 2px var(--primary); }
    .newfood-field.bad .newfood-in { box-shadow: inset 0 0 0 2px var(--danger); }
    .newfood-in input {
      flex: 1; min-width: 0; width: 100%; padding: 12px 0; border: 0; background: none; outline: none;
      font: 500 0.9375rem/1.3 var(--font-sans); color: var(--ink);
    }
    .newfood-in input::placeholder { color: var(--ink-muted); }
    .newfood-in small { flex: none; font: 600 0.8125rem/1.2 var(--font-sans); color: var(--ink-subtle); }
    /* the unit he switches with one tap sits where the unit is printed (6b: "0 kJ"); the whole 48 px height is the target */
    .newfood-unit {
      flex: none; align-self: stretch; display: flex; min-width: 44px; margin-right: -8px; padding: 7px 0;
      border: 0; background: none; color: var(--ink); cursor: pointer;
    }
    .newfood-unit span {
      display: flex; align-items: center; gap: 4px; padding: 0 8px; border-radius: var(--r-sm); background: var(--surface-3);
      font: 600 0.8125rem/1.2 var(--font-sans);
    }
    .newfood-unit b { font: inherit; }
    .newfood-unit svg.i { width: 14px; height: 14px; color: var(--ink-muted); }
    .newfood-form .btn.sec.newfood-more { margin: 0; }
    .newfood-help, .newfood-msg { margin: 6px 0 0; font: 500 0.75rem/1.4 var(--font-sans); color: var(--ink-muted); }
    .newfood-msg { display: flex; gap: 6px; align-items: flex-start; font-weight: 600; color: var(--danger); }
    .newfood-msg svg.i { width: 16px; height: 16px; margin-top: 1px; }
    .newfood-note { margin: 0; }
    .newfood-banner { margin: 0; }
    .newfood-banner > div { min-width: 0; overflow-wrap: anywhere; }
    /* base.css gives .sec (a section) a margin; here it is the secondary button, one step up from the banner's surface-2 */
    .newfood-banner .btn.sec { margin: 10px 0 0; min-height: 44px; background: var(--surface-3); }
    .newfood-sk { border-radius: var(--r-md); background: var(--surface-2); }
  `);

  // ── codes, numbers, words ──
  function validCode(code) {
    if (!/^(\d{8}|\d{13})$/.test(code || '')) return false;
    const d = [...code].map(Number);
    const check = d.pop();
    const sum = d.reverse().reduce((s, v, i) => s + v * (i % 2 ? 1 : 3), 0);
    return (10 - (sum % 10)) % 10 === check;
  }
  const sameCode = (a, b) => String(a).replace(/^0+/, '') === String(b).replace(/^0+/, '');
  const owner = (doc, code) => doc.foods.find(f => typeof f.barcode === 'string' && sameCode(f.barcode, code));

  // toPrecision(12) drops binary noise first (core rounds the same way).
  const round = (v, digits) => { const f = 10 ** digits; return Math.round(Number((v * f).toPrecision(12))) / f; };
  // whole kcal, as Found's summary line (P.fmt) and design 6 show it: one value, one number on the screen
  const digitsOf = key => (key === 'kcal' ? 0 : 2);
  const shownValue = (v, key) => (typeof v === 'number' && Number.isFinite(v) ? String(round(v, digitsOf(key))) : '');
  // A value from a source: a number, or a string that is one; anything else is unknown.
  function sourceNum(v) {
    if (typeof v === 'string' && v.trim() !== '') v = Number(v);
    return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : undefined;
  }
  // A typed value: '' is absent, a comma is a decimal point; null when it is not a number.
  function typedNum(text) {
    const t = String(text).trim().replace(/\s/g, '').replace(',', '.');
    if (!t) return undefined;
    const v = Number(t);
    return Number.isFinite(v) && v >= 0 ? v : null;
  }
  // '200g', '1 kg', '4 x 100 g' -> grams; volumes stay unknown (grams of a litre depend on what is in it).
  function packGrams(size) {
    const s = String(size || '').toLowerCase().replace(',', '.').trim();
    let m = s.match(/^(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(g|kg)\b/);
    if (m) return round(Number(m[1]) * Number(m[2]) * (m[3] === 'kg' ? 1000 : 1), 1);
    m = s.match(/^(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg)\b/);
    if (m) return round(Number(m[1]) * (m[2] === 'kg' ? 1000 : 1), 1);
    return undefined;
  }
  // The name for his list: the store's name without a trailing pack size and a leading brand; sentence case.
  function shortName(name, brand) {
    let n = String(name || '').trim().replace(/\s+\d+(?:[.,]\d+)?\s*(?:g|kg|ml|l|pack|pk)$/i, '').trim();
    const b = String(brand || '').trim();
    if (b && n.toLowerCase().startsWith(b.toLowerCase() + ' ')) n = n.slice(b.length).trim();
    if (n && n === n.toLowerCase()) n = n[0].toUpperCase() + n.slice(1);
    return n;
  }

  const STOP = new Set(['and', 'with', 'the', 'for', 'from', 'style', 'pack', 'fresh', 'free', 'classic', 'original', 'value']);
  const stem = w => (w.length > 3 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w);
  const words = text => String(text || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/).filter(w => w.length >= 3 && !/\d/.test(w) && !STOP.has(w)).map(stem);
  const alike = (a, b) => a === b || (a.length >= 4 && b.length >= 4 && (a.startsWith(b) || b.startsWith(a)));

  // "This is my …": his foods without a barcode whose names share at least half of the product's words
  // (its brand left out), the best match and then the most logged first.
  function matches(doc, product) {
    const brand = new Set(words(product.brand));
    const want = [...new Set(words(product.name).filter(w => !brand.has(w)))];
    if (!want.length) return [];
    const count = new Map();
    for (const e of doc.entries) count.set(e.foodId, (count.get(e.foodId) || 0) + 1);
    return doc.foods.filter(f => !f.barcode).map(f => {
      const have = words(f.name);
      return { food: f, hits: want.filter(w => have.some(h => alike(w, h))).length, logged: count.get(f.id) || 0 };
    }).filter(x => x.hits > 0 && x.hits * 2 >= want.length)
      .sort((a, b) => b.hits - a.hits || b.logged - a.logged || a.food.name.localeCompare(b.food.name)).slice(0, 3);
  }

  // ── sources ──
  function fromCatalogue(item) {
    const per100 = {};
    for (const [k, v] of Object.entries(item.per100 || {})) { const n = sourceNum(v); if (n !== undefined) per100[k] = n; }
    return { name: item.name, brand: item.brand, size: item.size, per100, store: item.store };
  }

  function fromOff(body) {
    const p = body && body.status === 1 && body.product;
    if (!p || typeof p !== 'object') return null;
    const n = p.nutriments && typeof p.nutriments === 'object' ? p.nutriments : {};
    const per100 = {};
    const kcal = sourceNum(n['energy-kcal_100g']);
    const kj = sourceNum(n['energy-kj_100g']);
    if (kcal !== undefined) per100.kcal = kcal;
    else if (kj !== undefined) per100.kcal = kj / KJ_PER_KCAL;
    for (const [from, to] of OFF_FIELDS) {
      const v = sourceNum(n[from]);
      if (v !== undefined) per100[to] = v;
    }
    const name = typeof p.product_name === 'string' ? p.product_name.trim() : '';
    const brand = typeof p.brands === 'string' ? p.brands.split(',')[0].trim() : '';
    return { name, brand, size: p.quantity, per100, store: 'off' };
  }

  async function askOff(code, signal) {
    let res;
    try { res = await fetch(OFF_URL(code), { signal, credentials: 'omit' }); } catch (e) {
      return { kind: 'down', why: signal.aborted ? 'did not answer in time' : 'could not be reached' };
    }
    if (res.status === 404) return { kind: 'missing' };
    if (!res.ok) return { kind: 'down', why: `answered with an error (${res.status})` };
    let body;
    try { body = await res.json(); } catch (e) { return { kind: 'down', why: 'sent an answer Pantry could not read' }; }
    if (body && body.status === 0) return { kind: 'missing' };
    const product = fromOff(body);
    return product ? { kind: 'found', product } : { kind: 'down', why: 'sent an answer Pantry could not read' };
  }

  // ── screen ──
  function header(eyebrow, title) {
    return `<header class="top back"><button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>`
      + `<div><p class="eyebrow">${P.esc(eyebrow)}</p><h1 class="title">${P.esc(title)}</h1></div></header>`;
  }
  const art = (food, size) => (window.PantryDrawing ? window.PantryDrawing(food, size) : '');
  function wireBack(el) { el.querySelector('[data-act="back"]').addEventListener('click', () => P.back()); }

  function render(el, code, meal, date) {
    leave();
    const me = shown = { el, code, meal: MEALS.includes(meal) ? meal : P.mealNow(), date: /^\d{4}-\d{2}-\d{2}$/.test(date || '') ? date : P.today(), abort: null };
    if (!validCode(code)) {
      el.innerHTML = `${header('Barcode', 'New food')}<div class="newfood-body"><div class="banner newfood-banner" role="alert">${P.icon('alert')}`
        + `<div>${P.esc(code ? `${code} is not a barcode Pantry can look up: the digits or the check digit are wrong.` : 'No barcode was given.')} Go back and scan it again.</div></div></div>`;
      wireBack(el);
      return;
    }
    lookup(me);
  }

  function lookup(me) {
    const doc = P.doc();
    const mine = owner(doc, me.code);
    if (mine) return saved(me, mine);
    const item = (doc.catalogue || []).find(c => sameCode(c.barcode, me.code));
    if (item) return found(me, fromCatalogue(item));
    const known = offCache.get(me.code);
    if (known) return known.kind === 'found' ? foundOrLabel(me, known.product) : label(me, { eyebrow: 'Not found in any catalogue' });
    if (navigator.onLine === false) {
      return label(me, { eyebrow: 'Offline', note: 'You are offline, so Open Food Facts was not checked. Type it from the label, or try again when you are online.', retry: true });
    }
    loading(me);
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), OFF_WAIT_MS);
    me.abort = () => { clearTimeout(timer); ctl.abort(); };
    askOff(me.code, ctl.signal).then(result => {
      clearTimeout(timer);
      if (shown !== me) return;
      me.abort = null;
      if (result.kind !== 'down') offCache.set(me.code, result);
      if (result.kind === 'found') foundOrLabel(me, result.product);
      else if (result.kind === 'missing') label(me, { eyebrow: 'Not found in any catalogue' });
      else label(me, { eyebrow: 'Open Food Facts did not answer', note: `Open Food Facts ${result.why}. Type it from the label, or try again.`, retry: true });
    });
  }

  // A product without energy cannot be logged by grams: its name helps, its values come from the label.
  function foundOrLabel(me, product) {
    if (product.per100.kcal !== undefined) return found(me, product);
    label(me, { eyebrow: 'Open Food Facts has no values for it', note: 'Open Food Facts knows its name but not its energy. Type the values from the label.', product });
  }

  function loading(me) {
    me.el.innerHTML = `${header(`Barcode ${me.code}`, 'New food')}
      <div class="newfood-body" aria-busy="true">
        <p class="note newfood-note" role="status">Looking in Open Food Facts.</p>
        <div class="newfood-src"><span class="newfood-art"></span><span class="t"><span class="newfood-sk" style="display:block;height:1rem;width:70%"></span>
          <span class="newfood-sk" style="display:block;height:0.8rem;width:45%;margin-top:8px"></span></span></div>
        <div class="newfood-grid">${'<div class="newfood-sk" style="height:76px"></div>'.repeat(4)}</div>
      </div>`;
    wireBack(me.el);
  }

  function saved(me, food) {
    const kcal = food.per100 ? `${P.fmt(food.per100.kcal)} kcal per 100 g` : 'Logged by servings';
    me.el.innerHTML = `${header(`Barcode ${me.code}`, 'In your foods')}
      <div class="newfood-body">
        <div class="newfood-src"><span class="newfood-art">${art(food, 42)}</span>
          <span class="t"><b>${P.esc(food.name)}</b><span>${P.esc((food.brand ? food.brand + ', ' : '') + kcal)}</span></span></div>
        <p class="note newfood-note">This barcode is already saved with this food.</p>
      </div>
      <div class="bottom"><button class="btn" type="button" data-act="grams">Choose grams</button></div>`;
    wireBack(me.el);
    me.el.querySelector('[data-act="grams"]').addEventListener('click', () => P.go('food', food.id, me.meal, me.date));
  }

  function field(key, label, value, unit, opts = {}) {
    const id = `newfood-${key}`;
    const input = `<input id="${id}" name="${key}" ${opts.text ? 'autocomplete="off" autocapitalize="sentences"' : 'inputmode="decimal" autocomplete="off"'}`
      + ` enterkeyhint="next" value="${P.esc(value)}"${opts.placeholder ? ` placeholder="${P.esc(opts.placeholder)}"` : ''}`
      + `${opts.required ? ' aria-required="true"' : ''} aria-describedby="${id}-msg">`;
    const tail = opts.units ? unitSwitch(opts.units) : unit ? `<small>${P.esc(unit)}</small>` : '';
    return `<div class="newfood-field${opts.wide ? ' newfood-wide' : ''}" data-field="${key}"><label for="${id}">${P.esc(label)}</label>`
      + `<div class="newfood-in">${input}${tail}</div>`
      + `<p class="newfood-help" id="${id}-msg"${opts.help ? '' : ' hidden'}>${opts.help ? P.esc(opts.help) : ''}</p></div>`;
  }

  // The unit's value rides in a hidden input of that name; the button shows it and switches to the other one.
  function unitSwitch(name) {
    const [now, next] = UNITS[name].list;
    return `<input type="hidden" name="${name}" value="${now[0]}"><button class="newfood-unit" type="button" data-unit="${name}"`
      + ` aria-label="${P.esc(`${now[2]}; switch to ${next[2]}`)}"><span><b>${P.esc(now[1])}</b>${SWAP}</span></button>`;
  }

  function switchUnit(form, name) {
    const { key, list } = UNITS[name];
    const input = form.elements[name];
    const at = (list.findIndex(u => u[0] === input.value) + 1) % list.length;
    const [value, unit, spoken, label] = list[at];
    input.value = value;
    const btn = form.querySelector(`[data-unit="${name}"]`);
    btn.querySelector('b').textContent = unit;
    btn.setAttribute('aria-label', `${spoken}; switch to ${list[(at + 1) % list.length][2]}`);
    if (label) form.querySelector(`label[for="newfood-${key}"]`).textContent = label;
  }

  // Design 6's order: the product, the six values, the pack size. "This is my …" (Task-04) sits under the product, so
  // a food he already has is seen before Save makes a second one; the name for his list comes last (v1 has no food
  // editing, so this is where a store's name becomes his).
  function found(me, product) {
    const store = STORE[product.store];
    const kcal = product.per100.kcal;
    const brand = typeof product.brand === 'string' ? product.brand.trim() : '';
    // the brand saved with the food is shown under its name, unless the store's name already carries it
    const byline = brand && !String(product.name || '').toLowerCase().includes(brand.toLowerCase()) ? `${brand}, ` : '';
    const picks = matches(P.doc(), product);
    const grams = packGrams(product.size);
    me.el.innerHTML = `${header(`Barcode ${me.code}`, 'New food')}
      <form class="newfood-form" novalidate>
        <div class="newfood-body">
          <div class="newfood-src"><span class="newfood-art">${art(product, 42)}</span>
            <span class="t"><b>${P.esc(product.name || 'A product with no name')}</b><span>${P.esc(byline)}${P.fmt(kcal)} kcal per 100 g</span></span>
            <span class="newfood-tag">${P.esc(store)}</span></div>
          ${picks.length ? `<section class="newfood-picks" aria-labelledby="newfood-picks-h"><h2 class="eyebrow" id="newfood-picks-h">This is my …</h2>
            <ul class="rows">${picks.map(({ food, logged }, i) => {
              const sub = [food.brand, logged ? `logged ${logged} ${logged === 1 ? 'time' : 'times'}` : ''].filter(Boolean).join(', ') || 'In your foods';
              return `<li><button class="fr" type="button" data-pick="${i}" aria-label="${P.esc(`This is my ${food.name}${food.brand ? ', ' + food.brand : ''}`)}">`
                + `<span class="newfood-dot">${art(food, 32)}</span><span class="t"><span class="name">${P.esc(food.name)}</span><span class="sub">${P.esc(sub)}</span></span>${CHEVRON}</button></li>`;
            }).join('')}</ul>
            <p class="newfood-help">Adds this barcode to that food, so its history and usual grams stay.</p></section>` : ''}
          <h2 class="eyebrow">Per 100 g</h2>
          <div class="newfood-grid newfood-nums">${FOUND_FIELDS.map(([k, l, u]) => field(k, l, shownValue(product.per100[k], k), u, { required: k === 'kcal' })).join('')}</div>
          ${field('pack', 'Pack size', grams === undefined ? '' : String(grams), 'g', { help: `From ${store === 'Open Food Facts' ? 'Open Food Facts' : "the store's label data"}. Check it once; it is saved to your foods.` })}
          ${field('name', 'Name in your foods', shortName(product.name, brand), '', { text: true, required: true })}
        </div>
        <div class="bottom"><button class="btn" type="submit">${P.icon('plus')}Save and choose grams</button></div>
      </form>`;
    wireBack(me.el);
    me.el.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => attach(me, picks[Number(b.dataset.pick)].food.id)));
    const form = me.el.querySelector('form');
    wireForm(form, FOUND_FIELDS);
    form.addEventListener('submit', e => {
      e.preventDefault();
      const values = read(form, FOUND_FIELDS, { kcal: 'Type the energy per 100 g, in kcal.' });
      if (!values) return;
      // The source's own numbers with his edits: a field left as shown keeps the unrounded source value (the box shows
      // 108 for 107.55…), a changed one takes what he typed, a cleared one goes.
      const per100 = { ...product.per100 };
      for (const [k] of FOUND_FIELDS) {
        if (form.elements[k].value.trim() === shownValue(product.per100[k], k)) continue;
        if (values[k] === undefined) delete per100[k]; else per100[k] = values[k];
      }
      create(me, { name: values.name, brand, per100: ordered(per100), pack: values.pack, source: product.store });
    });
  }

  function label(me, opts) {
    const product = opts.product || {};
    const grams = packGrams(product.size);
    me.el.innerHTML = `${header(opts.eyebrow, 'From the label')}
      <form class="newfood-form" novalidate>
        <div class="newfood-body">
          ${opts.note ? `<div class="banner newfood-banner" role="status">${P.icon('alert')}<div>${P.esc(opts.note)}`
            + `${opts.retry ? '<button class="btn sec" type="button" data-act="retry">Try Open Food Facts again</button>' : ''}</div></div>` : ''}
          ${field('name', 'Name', shortName(product.name, product.brand), '', { text: true, required: true, wide: true, placeholder: 'e.g. Greek yoghurt' })}
          <div class="newfood-grid">
            ${field('brand', 'Brand', product.brand || '', '', { text: true, placeholder: 'optional' })}
            ${field('pack', 'Pack size', grams === undefined ? '' : String(grams), 'g', { placeholder: 'optional' })}
          </div>
          <h2 class="eyebrow">Per 100 g, as printed</h2>
          <div class="newfood-grid newfood-nums">${field('energy', 'Energy (kJ or kcal)', '', '', { required: true, units: 'energyUnit' })}`
            + `${LABEL_FIELDS.map(([k, l, u]) => field(k, l, '', u)).join('')}</div>
          <p class="newfood-help">Sugars, salt and fibre are optional. kJ is turned into kcal.</p>
          <button class="btn sec newfood-more" type="button" aria-expanded="false" aria-controls="newfood-more">${DOWN}Add sugars, salt and fibre</button>
          <div class="newfood-grid newfood-nums" id="newfood-more" hidden>${field('sugars', 'Sugars', '', 'g')}`
            + `${field('salt', 'Salt', '', '', { units: 'saltUnit' })}${field('fibre', 'Fibre', '', 'g')}</div>
        </div>
        <div class="bottom"><button class="btn" type="submit">${P.icon('plus')}Save and choose grams</button></div>
      </form>`;
    wireBack(me.el);
    const retry = me.el.querySelector('[data-act="retry"]');
    if (retry) retry.addEventListener('click', () => lookup(me));
    const form = me.el.querySelector('form');
    const unit = name => form.elements[name].value;
    const sodium = () => unit('saltUnit') === 'mg';
    const fields = [['energy', 'Energy', () => unit('energyUnit'), () => (unit('energyUnit') === 'kJ' ? 3800 : 900)], ...LABEL_FIELDS,
      ['sugars', 'Sugars', 'g', 100], ['salt', () => (sodium() ? 'Sodium' : 'Salt'), () => unit('saltUnit'), () => (sodium() ? 40000 : 100)], ['fibre', 'Fibre', 'g', 100]];
    wireForm(form, fields);
    form.querySelectorAll('[data-unit]').forEach(btn => btn.addEventListener('click', () => {
      switchUnit(form, btn.dataset.unit);
      check(form, fields, UNITS[btn.dataset.unit].key);
    }));
    const more = form.querySelector('.newfood-more');
    more.addEventListener('click', () => {
      form.querySelector('#newfood-more').hidden = false;
      more.setAttribute('aria-expanded', 'true');
      more.hidden = true;
      form.elements.sugars.focus();
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      const values = read(form, fields, { energy: 'Type the energy per 100 g from the label.' });
      if (!values) return;
      const per100 = { kcal: round(unit('energyUnit') === 'kJ' ? values.energy / KJ_PER_KCAL : values.energy, 1) };
      for (const [k] of fields.slice(1)) {
        if (values[k] === undefined) continue;
        per100[k] = k === 'salt' && sodium() ? round(values[k] * 2.5 / 1000, 2) : values[k];   // salt = sodium × 2.5
      }
      create(me, { name: values.name, brand: values.brand, per100: ordered(per100), pack: values.pack, source: 'label' });
    });
    if (!opts.product) form.elements.name.focus({ preventScroll: true });
  }

  // ── form reading: say what is wrong in words under the field; the Save bar stays as small as it was ──
  const unitOf = u => (typeof u === 'function' ? u() : u);
  const maxOf = m => (typeof m === 'function' ? m() : m);

  function problem(form, fields, key) {
    const input = form.elements[key];
    if (key === 'pack') {
      const v = typedNum(input.value);
      if (v === null || v === 0 || (v !== undefined && v > 100000)) return 'Type the pack size in grams, for example 200, or leave it empty.';
      return null;
    }
    const f = fields.find(x => x[0] === key);
    if (!f) return null;
    const v = typedNum(input.value);
    const unit = unitOf(f[2]);
    const name = unitOf(f[1]);
    if (v === null) return `${name}: type a number, for example ${unit === 'mg' ? '380' : unit === 'kJ' ? '452' : '5.5'}.`;
    if (v !== undefined && v > maxOf(f[3])) {
      if (key === 'energy' || key === 'kcal') return `Energy above ${P.fmt(maxOf(f[3]))} ${unit} per 100 g is more than pure fat. Check the number${key === 'energy' ? ' and kJ or kcal' : ''}.`;
      return `${name} above ${P.fmt(maxOf(f[3]))} ${unit} per 100 g cannot be right. Check the number.`;
    }
    return null;
  }

  function mark(form, key, text) {
    const box = form.querySelector(`[data-field="${key}"]`);
    if (!box) return;
    const msg = box.querySelector(`#newfood-${key}-msg`);
    if (!('help' in msg.dataset)) msg.dataset.help = msg.hidden ? '' : msg.textContent;
    box.classList.toggle('bad', !!text);
    form.elements[key].setAttribute('aria-invalid', text ? 'true' : 'false');
    if (text) { msg.className = 'newfood-msg'; msg.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`; msg.hidden = false; }
    else { msg.className = 'newfood-help'; msg.textContent = msg.dataset.help; msg.hidden = !msg.dataset.help; }
  }

  function check(form, fields, key) {
    const text = problem(form, fields, key);
    mark(form, key, text);
    return text;
  }

  // Validate on leaving a field, not on every key; a fixed field clears its message as he types.
  function wireForm(form, fields) {
    for (const key of [...fields.map(f => f[0]), 'pack']) {
      const input = form.elements[key];
      if (!input || input.length) continue;
      input.addEventListener('blur', () => check(form, fields, key));
      input.addEventListener('input', () => { if (form.querySelector(`[data-field="${key}"].bad`)) check(form, fields, key); });
    }
    form.elements.name.addEventListener('input', () => mark(form, 'name', null));
  }

  function read(form, fields, need) {
    const errors = [];
    const name = form.elements.name.value.trim().replace(/\s+/g, ' ');
    if (!name) { mark(form, 'name', 'Type the name you will look for in your list.'); errors.push('name'); } else mark(form, 'name', null);
    const values = { name };
    if (form.elements.brand) values.brand = form.elements.brand.value.trim().replace(/\s+/g, ' ');
    for (const [key] of [...fields, ['pack']]) {
      if (check(form, fields, key)) { errors.push(key); continue; }
      values[key] = typedNum(form.elements[key].value);
    }
    for (const [key, text] of Object.entries(need)) {
      if (values[key] === undefined && !errors.includes(key)) { mark(form, key, text); errors.push(key); }
    }
    if (!errors.length) return values;
    // The first field with a message, in the form's order, comes to the middle of the screen, clear of the Save bar.
    const first = [...form.querySelectorAll('[data-field]')].find(b => errors.includes(b.dataset.field));
    first.scrollIntoView({ block: 'center' });
    form.elements[first.dataset.field].focus({ preventScroll: true });
    return null;
  }

  const ORDER = ['kcal', 'protein', 'carbs', 'fat', 'sugars', 'satFat', 'salt', 'fibre'];
  function ordered(per100) {
    const out = {};
    for (const k of ORDER) if (per100[k] !== undefined) out[k] = per100[k];
    for (const [k, v] of Object.entries(per100)) if (!(k in out)) out[k] = v;
    return out;
  }

  // ── saving ──
  function newId(doc) {
    const taken = new Set(doc.foods.map(f => f.id));
    let id;
    do { id = `f-${crypto.getRandomValues(new Uint32Array(2)).reduce((s, n) => s + n.toString(36), '')}`; } while (taken.has(id));
    return id;
  }

  function create(me, { name, brand, per100, pack, source }) {
    let id = null;
    try {
      P.change(d => {
        const mine = owner(d, me.code);
        if (mine) { id = mine.id; return; }   // saved meanwhile (another tab, a double tap): never twice
        id = newId(d);
        const food = { id, name };
        if (brand) food.brand = brand;
        food.barcode = me.code;
        food.per100 = per100;
        food.servings = pack ? [{ label: '1 pack', grams: pack, kcal: round(per100.kcal * pack / 100, 1) }] : [];
        food.source = source;
        d.foods.push(food);
      });
    } catch (x) {
      P.toast(x.message);
      return;
    }
    P.go('food', id, me.meal, me.date);
  }

  function attach(me, foodId) {
    try {
      P.change(d => {
        if (owner(d, me.code)) return;
        const food = d.foods.find(f => f.id === foodId);
        if (food) food.barcode = me.code;
      });
    } catch (x) {
      P.toast(x.message);
      return;
    }
    const mine = owner(P.doc(), me.code);
    P.go('food', mine ? mine.id : foodId, me.meal, me.date);
  }

  function leave() {
    if (shown && shown.abort) shown.abort();
    shown = null;
  }

  P.view('newfood', { render, leave });
})();

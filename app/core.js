/* Pantry core: the data document, storage, screens and the feature loader.
   The only file in app/ that touches localStorage. Features talk to everything through window.Pantry.

   Storage (localStorage)
     'pantry.v1'    the data document: { version: 1, foods: [], entries: [], settings: { targets } }.
                    Shapes: tasks/Task-00.md, Fixed. Seeded with the starter foods only while it is empty.
     'pantry.sync'  the sync feature's own object (repo, token, dirty flag, last sha). Never inside the document.

   Data
     Pantry.doc()                  the current document, deep-frozen: read it, never mutate it.
     Pantry.change(fn, opts)       fn(draft) edits a deep copy, or returns a whole new document. The result is
                                   checked, saved, marked dirty and announced; returns the new document. Throws and
                                   saves nothing when the shape is wrong, storage is full or Pantry.problem() is set.
                                   opts.dirty = false for a document that came from the data repo (sync pull, import).
     Pantry.subscribe(fn)          fn(doc, why) after every change ('change', 'storage' from another tab, 'day' when
                                   the calendar day turns); returns an unsubscribe function.
     Pantry.dirty()                true while there are changes the sync feature has not pushed.
     Pantry.markClean()            the sync feature calls it after a successful push.
     Pantry.syncState()            the 'pantry.sync' object (a copy).
     Pantry.setSyncState(patch)    merges patch into 'pantry.sync' and saves it.
     Pantry.problem()              null, or a plain sentence saying why the stored document cannot be used.
     Pantry.starter                the starter foods as [{ food, usual }]: usual = grams to offer before any entry.

   Days, numbers, text
     Pantry.today()                'YYYY-MM-DD' of the phone's local calendar day (Darwin for Tarik), never UTC.
     Pantry.dayLabel(date)         'Tuesday, 20 October' for a 'YYYY-MM-DD'.
     Pantry.totals(food, grams)    nutrient totals of grams of a food with per100; an unknown nutrient stays absent.
     Pantry.sum(entries)           the entries' totals added up, per nutrient present in any of them.
     Pantry.fmt(n, digits)         a number with thousands separators (en-AU), at most `digits` decimals (default 0).
     Pantry.esc(text)              text made safe for an HTML template.
     Pantry.icon(name)             a Lucide outline icon as inline SVG: back, plus, minus, scan, x, alert, check.

   Screens (hash routes '#/<name>/<arg>...'; '#/' is Today)
     Pantry.view(name, def)        registers a screen. def.render(root, ...args) fills a fresh <section>;
                                   def.update(doc) (optional) runs on every change while it is shown;
                                   def.leave() (optional) runs when another screen replaces it.
     Pantry.go(name, ...args)      opens a screen and adds a history entry, so the phone's back gesture returns.
     Pantry.back()                 one screen back; Today when there is nothing to go back to.
     Pantry.home()                 back to Today, dropping the screens opened since.
     Pantry.css(text)              adds a feature's styles to the page.

   Features
     app/registry.js lists every feature script, one line each. Core loads them in that order once the page is
     parsed, then opens the screen in the address. sw.js reads the same list, so a new feature is offline with no
     other edit. A feature never touches localStorage and never edits another feature or this file. */
(() => {
  'use strict';

  const KEY = 'pantry.v1';
  const SYNC_KEY = 'pantry.sync';
  const VERSION = 1;
  const MEALS = ['breakfast', 'lunch', 'dinner', 'snacks'];
  const SOURCES = ['mynetdiary', 'coles', 'woolworths', 'off', 'label'];
  const TARGETS = { kcal: 2200, proteinPct: 20, carbsPct: 45, fatPct: 35, salt: 5.8 };

  // Product values as MyNetDiary has them, per 100 g; ids are MyNetDiary foodIds, so an import replaces them.
  const STARTER = [
    { usual: 350, food: { id: 'v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao=', name: 'Chicken Breast Raw',
      per100: { kcal: 108.1, protein: 20.33, carbs: 0, fat: 3.0, sugars: 0, satFat: 0.54, salt: 0.43, fibre: 0 } } },
    { usual: 125, food: { id: 'v1.nWY1wUENSPOyu4Pt9ojJcGQKyXNwC+i8TqtlZmsYpNIdi2IepiE5wgTOo1g=', name: 'Classic Tzatziki Dip', brand: 'Coles',
      per100: { kcal: 90.0, protein: 4.75, carbs: 12.0, fat: 3.25, sugars: 7.25, satFat: 2.5, salt: 0.8, fibre: 2.5 } } },
    { usual: 100, food: { id: 'v1.d6DR1H5K+qWQUAWwc3j8qf3M2Hc3hKdn3YcTs5+OuZghSHwXFrx2D3cMe9c=', name: 'Indian Basmati Rice', brand: 'Coles',
      per100: { kcal: 360.0, protein: 8.4, carbs: 80.0, fat: 0.6, sugars: 0, satFat: 0.2, salt: 0, fibre: 2.0 } } },
    { usual: 5, food: { id: 'v1.aKW*42YP1j2TAk0bfGM*EM*zCxIsoQLSdlyVsH9Lzqk1scOD*H2WCHxRDw==', name: 'Original Spreadable Butter', brand: 'Western Star',
      per100: { kcal: 616.6, protein: 20.0, carbs: 20.0, fat: 60.0, sugars: 20.0, satFat: 28.0, salt: 1.2 } } },
    { usual: 500, food: { id: 'v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg=', name: 'Washed White Potato', brand: 'Woolworths',
      per100: { kcal: 59.0, protein: 2.27, carbs: 14.8, fat: 0.13, sugars: 0.67, satFat: 0.13, salt: 0.01, fibre: 1.87 } } },
  ].map(({ usual, food }) => ({ usual, food: { ...food, servings: [], source: 'mynetdiary' } }));

  const ICONS = {
    back: '<path d="m15 18-6-6 6-6"/>',
    plus: '<path d="M5 12h14M12 5v14"/>',
    minus: '<path d="M5 12h14"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M8 7v10M12 7v10M16 7v10"/>',
  };

  // ── document ──────────────────────────────────────────────────────
  const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const isNum = v => typeof v === 'number' && Number.isFinite(v);
  const fresh = () => ({ version: VERSION, foods: [], entries: [], settings: { targets: { ...TARGETS } } });

  // The shape every saved document must have; a feature bug fails here instead of corrupting the log.
  function check(doc) {
    if (!isObj(doc)) throw new Error('the document is not an object');
    if (doc.version !== VERSION) throw new Error(`version ${doc.version}, expected ${VERSION}`);
    if (!Array.isArray(doc.foods) || !Array.isArray(doc.entries) || !isObj(doc.settings)) throw new Error('foods, entries or settings missing');
    if (!isObj(doc.settings.targets) || !isNum(doc.settings.targets.kcal) || doc.settings.targets.kcal <= 0) throw new Error('settings.targets.kcal missing');
    const ids = new Set();
    for (const f of doc.foods) {
      if (!isObj(f) || typeof f.id !== 'string' || !f.id || typeof f.name !== 'string') throw new Error('a food without id or name');
      if (ids.has(f.id)) throw new Error(`food ${f.id} twice`);
      ids.add(f.id);
      if (!Array.isArray(f.servings)) throw new Error(`food ${f.id}: servings is not a list`);
      if (!SOURCES.includes(f.source)) throw new Error(`food ${f.id}: source ${f.source}`);
      if (f.per100 !== undefined && (!isObj(f.per100) || !isNum(f.per100.kcal))) throw new Error(`food ${f.id}: per100 without kcal`);
    }
    const entryIds = new Set();
    for (const e of doc.entries) {
      if (!isObj(e) || typeof e.id !== 'string' || !e.id) throw new Error('an entry without id');
      if (entryIds.has(e.id)) throw new Error(`entry ${e.id} twice`);
      entryIds.add(e.id);
      if (typeof e.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(e.date)) throw new Error(`entry ${e.id}: date ${e.date}`);
      if (!MEALS.includes(e.meal)) throw new Error(`entry ${e.id}: meal ${e.meal}`);
      if (typeof e.foodId !== 'string' || typeof e.amount !== 'string') throw new Error(`entry ${e.id}: foodId or amount`);
      if (e.grams !== null && !isNum(e.grams)) throw new Error(`entry ${e.id}: grams ${e.grams}`);
      if (!isObj(e.totals) || !isNum(e.totals.kcal)) throw new Error(`entry ${e.id}: totals.kcal`);
    }
    return doc;
  }

  function freeze(v) {
    if (v && typeof v === 'object' && !Object.isFrozen(v)) { Object.freeze(v); for (const k of Object.keys(v)) freeze(v[k]); }
    return v;
  }

  function seed(doc) {
    doc.foods = STARTER.map(s => structuredClone(s.food));
    return doc;
  }

  let problem = null;
  let doc = freeze(load());

  function load() {
    let raw;
    try { raw = localStorage.getItem(KEY); } catch (e) {
      problem = 'This browser blocks storage for Pantry, so nothing can be saved. Open Pantry from its home-screen icon or allow site data.';
      return seed(fresh());
    }
    if (raw === null) return firstWrite(seed(fresh()));
    let stored;
    try { stored = JSON.parse(raw); } catch (e) { stored = undefined; }
    if (isObj(stored) && isNum(stored.version) && stored.version > VERSION) {
      problem = 'The food log on this phone was saved by a newer Pantry. Reload to get the update; until then nothing is saved.';
      return seed(fresh());
    }
    try { check(stored); } catch (e) {
      // Keep the stored text untouched: refusing to save is better than writing over a log we could not read.
      problem = `The food log saved on this phone could not be read (${e.message}), so Pantry is not saving anything over it.`;
      console.error('Pantry: ' + problem);
      return seed(fresh());
    }
    if (stored.foods.length === 0 && stored.entries.length === 0) return firstWrite(seed(stored));
    return stored;
  }

  function firstWrite(next) {
    try { return write(next); } catch (e) { problem = e.message; return next; }
  }

  function write(next) {
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch (e) {
      throw new Error(e && e.name === 'QuotaExceededError'
        ? 'Could not save: the storage Pantry has on this phone is full.'
        : `Could not save on this phone (${e && e.message}).`);
    }
    return next;
  }

  function readSync() {
    try { const v = JSON.parse(localStorage.getItem(SYNC_KEY) || '{}'); return isObj(v) ? v : {}; } catch (e) { return {}; }
  }
  function writeSync(next) { localStorage.setItem(SYNC_KEY, JSON.stringify(next)); return next; }

  const subscribers = new Set();
  function announce(why) {
    applyTheme();
    for (const fn of [...subscribers]) {
      try { fn(doc, why); } catch (e) { console.error('Pantry: a subscriber failed', e); }
    }
    if (current && current.def.update) {
      try { current.def.update(doc); } catch (e) { console.error('Pantry: screen update failed', e); }
    }
  }

  function change(fn, opts = {}) {
    if (problem) throw new Error(problem);
    const draft = structuredClone(doc);
    const returned = fn(draft);
    const next = check(returned === undefined ? draft : returned);
    write(next);
    doc = freeze(next);
    if (opts.dirty !== false) {
      try { writeSync({ ...readSync(), dirty: true }); } catch (e) { console.error('Pantry: could not mark the change for sync', e); }
    }
    announce('change');
    return doc;
  }

  // Another tab of Pantry saved: take its document instead of overwriting it later.
  window.addEventListener('storage', e => {
    if (e.key !== KEY || e.newValue === null || problem) return;
    try { doc = freeze(check(JSON.parse(e.newValue))); announce('storage'); } catch (err) { console.error('Pantry: another tab saved an unreadable document', err); }
  });

  // ── days and numbers ──────────────────────────────────────────────
  const pad = n => String(n).padStart(2, '0');
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function dayLabel(date) {
    const [y, m, d] = date.split('-').map(Number);
    return `${DAYS[new Date(y, m - 1, d).getDay()]}, ${d} ${MONTHS[m - 1]}`;
  }

  // toPrecision(12) drops binary noise first, so 378.35 rounds to 378.4, not 378.3.
  const round = (v, digits) => { const f = 10 ** digits; return Math.round(Number((v * f).toPrecision(12))) / f; };
  function totals(food, grams) {
    const out = {};
    for (const [k, v] of Object.entries((food && food.per100) || {})) {
      if (isNum(v)) out[k] = round(v * grams / 100, k === 'kcal' ? 1 : 2);
    }
    return out;
  }
  function sum(entries) {
    const out = {};
    for (const e of entries) for (const [k, v] of Object.entries(e.totals || {})) if (isNum(v)) out[k] = (out[k] || 0) + v;
    return out;
  }
  const fmt = (n, digits = 0) => (round(n, digits) || 0).toLocaleString('en-AU', { maximumFractionDigits: digits });
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = name => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;

  // ── theme: follows the phone; settings.theme 'light' or 'dark' overrides when present ──
  const lightQuery = matchMedia('(prefers-color-scheme: light)');
  function applyTheme() {
    const pick = doc && doc.settings && doc.settings.theme;
    document.documentElement.dataset.theme = pick === 'light' || pick === 'dark' ? pick : (lightQuery.matches ? 'light' : 'dark');
  }
  lightQuery.addEventListener('change', applyTheme);
  applyTheme();

  // ── screens ───────────────────────────────────────────────────────
  const views = {};
  let current = null;   // { name, def, hash }
  let started = false;
  let shownDay = today();

  function parse() {
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
    return { name: parts[0] || 'today', args: parts.slice(1) };
  }

  function show() {
    const app = document.getElementById('app');
    const { name, args } = parse();
    const def = views[name] || views.today;
    if (current && current.def.leave) {
      try { current.def.leave(); } catch (e) { console.error('Pantry: leaving a screen failed', e); }
    }
    current = { name: views[name] ? name : 'today', def, hash: location.hash };
    shownDay = today();
    const root = document.createElement('section');
    root.className = 'screen';
    root.dataset.screen = current.name;
    app.replaceChildren(root);
    window.scrollTo(0, 0);
    if (!def) { root.innerHTML = '<p class="note">No screen is installed.</p>'; return; }
    try { def.render(root, ...args); } catch (e) {
      console.error('Pantry: screen failed', e);
      root.innerHTML = `<div class="banner" role="alert">${icon('alert')}<div><b>This screen failed to open.</b> ${esc(e.message)}</div></div>`;
    }
  }

  const depth = () => (history.state && history.state.depth) || 0;
  function go(name, ...args) {
    history.pushState({ depth: depth() + 1 }, '', '#/' + [name, ...args].map(encodeURIComponent).join('/'));
    show();
  }
  function toToday() { history.replaceState({ depth: 0 }, '', '#/'); show(); }
  function back() { if (depth() > 0) history.back(); else toToday(); }
  function home() { if (depth() > 0) history.go(-depth()); else toToday(); }
  const onNavigate = () => { if (started && (!current || location.hash !== current.hash)) show(); };
  window.addEventListener('popstate', onNavigate);
  window.addEventListener('hashchange', onNavigate);

  // A phone keeps the app open across midnight: when the day turns, the shown screen hears about it.
  function checkDay() { if (started && today() !== shownDay) { shownDay = today(); announce('day'); } }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') checkDay(); });
  setInterval(checkDay, 60000);

  function css(text) {
    const style = document.createElement('style');
    style.textContent = text;
    document.head.appendChild(style);
  }

  // ── features ──────────────────────────────────────────────────────
  function loadFeatures() {
    const list = self.PANTRY_FEATURES || [];
    return Promise.all(list.map(src => new Promise(resolve => {
      const s = document.createElement('script');
      s.src = src;
      s.async = false;   // run in registry order
      s.onload = resolve;
      s.onerror = () => { console.error('Pantry: feature failed to load: ' + src); resolve(); };
      document.head.appendChild(s);
    })));
  }

  window.Pantry = Object.freeze({
    doc: () => doc,
    change,
    subscribe(fn) { subscribers.add(fn); return () => subscribers.delete(fn); },
    dirty: () => readSync().dirty === true,
    markClean() { writeSync({ ...readSync(), dirty: false }); },
    syncState: () => readSync(),
    setSyncState(patch) { return writeSync({ ...readSync(), ...patch }); },
    problem: () => problem,
    starter: freeze(structuredClone(STARTER)),
    today, dayLabel, totals, sum, fmt, esc, icon,
    view(name, def) { views[name] = def; },
    go, back, home, css,
  });

  document.addEventListener('DOMContentLoaded', () => {
    loadFeatures().then(() => { started = true; show(); });
  });
  window.addEventListener('load', () => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' })
        .catch(e => console.warn('Pantry: offline support is not available here', e));
    }
  });
})();

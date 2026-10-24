/* Settings ('#/settings'): the targets (daily kcal, the macro split read and typed carbs, protein, fat, salt)
   edited in place; the theme, Dynamic, Light, Dark or System, picked in one tap (settings.theme, synced like the
   targets; app/core.js applies it at once and keeps Dynamic on Darwin's sun); sync with a private data repo
   (its state, the last sync, the repo named and the GitHub token pasted once and shown masked); the data on this phone
   (every day logged, "460 (+10)": MyNetDiary days plus days logged only in Pantry, and the foods). Drawn after
   design/screens.html → 9. Settings; its "Follow phone theme" toggle became the Theme group's four choices, second,
   so they show without scrolling. The sync itself is app/sync.js (window.PantrySync); this screen shows its state
   and hands it the token, which never enters the document.
   Test hooks: data-test="sync-pill", "sync-last", "sync-reason", "token-mask", "history", "history-days", "foods",
   "theme-help"; the theme choices are radios named Dynamic, Light, Dark and System. */
(() => {
  'use strict';

  const P = window.Pantry;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const IMPORTED = /^(\d{4}-\d{2}-\d{2})-\d+$/;          // tools/import_mynetdiary.py names entries <date>-<entryNo>
  const TOKEN = /^(github_pat_|ghp_)[A-Za-z0-9_]+$/;
  const REPO = /^[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9._-]{1,100}$/;   // owner/name as GitHub allows them
  const TARGETS = ['kcal', 'macro', 'salt'];
  // The macro split in the order every screen shows it (Pantry.MACROS): [key in settings.targets, label, kcal per gram].
  // Only the order shown and typed in follows it; the stored targets keep their shape.
  const SHARE = { carbs: ['carbsPct', 'Carbs', 4], protein: ['proteinPct', 'Protein', 4], fat: ['fatPct', 'Fat', 9] };
  const SHARES = P.MACROS.map(m => SHARE[m]);
  const THEMES = [['dynamic', 'Dynamic'], ['light', 'Light'], ['dark', 'Dark'], ['system', 'System']];
  const isNum = v => typeof v === 'number' && Number.isFinite(v);

  P.css(`
    .settings-body { padding: 14px 20px calc(32px + env(safe-area-inset-bottom)); }
    .settings-group + .settings-group { margin-top: 22px; }
    .settings-group > h2 { margin: 4px 0 0; }
    .settings-list { list-style: none; margin: 2px 0 0; padding: 0; }
    .settings-list > li { border-bottom: 1px solid var(--hairline); }
    .settings-row {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 4px 12px;
      min-height: 56px; padding: 8px 0; color: var(--ink); font: 600 0.9375rem/1.3 var(--font-sans);
    }
    button.settings-row {
      width: calc(100% + 16px); margin: 0 -8px; padding: 8px; border: 0; border-radius: var(--r-md);
      background: none; text-align: left; transition: background-color var(--fast);
    }
    button.settings-row:active, button.settings-row[aria-expanded="true"] { background: var(--surface-1); }
    .settings-t { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; }
    .settings-sub { display: block; font: 500 0.8125rem/1.35 var(--font-sans); color: var(--ink-muted); }
    .settings-mask { font-family: var(--font-figure); }
    .settings-v { margin-left: auto; font: 700 0.9375rem/1.3 var(--font-figure); text-align: right; white-space: nowrap; }
    .settings-v.light { font-weight: 600; }
    .settings-days { flex-wrap: nowrap; }   /* the count stays beside its name; the lines under the name wrap instead */
    .settings-pill {
      margin-left: auto; display: inline-flex; align-items: center; gap: 5px; min-height: 24px; padding: 2px 9px;
      border: 1px solid currentColor; border-radius: var(--r-pill); color: var(--ink-muted);
      font: 600 0.75rem/1.2 var(--font-sans); white-space: nowrap;
    }
    .settings-pill svg.i { width: 14px; height: 14px; }
    .settings-pill.bad { color: var(--danger); }
    .settings-ghost {
      margin-left: auto; min-height: 44px; padding: 0 4px; border: 0; background: none; color: var(--ink);
      font: 700 0.9375rem/1.2 var(--font-sans);
    }
    .settings-edit { padding: 4px 0 18px; }
    .settings-label { display: block; margin: 0 0 6px; font: 700 0.875rem/1.3 var(--font-sans); }
    .settings-next { margin-top: 12px; }
    .settings-input {
      display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 14px;
      border-radius: var(--r-md); background: var(--surface-2);
    }
    .settings-input:focus-within { box-shadow: inset 0 0 0 2px var(--primary); }
    .settings-input input {
      flex: 1; min-width: 0; width: 100%; padding: 10px 0; border: 0; background: none; color: var(--ink);
      font: 600 1rem/1.3 var(--font-figure);
    }
    .settings-input input:focus-visible { outline: none; }
    .settings-input input::placeholder { color: var(--ink-subtle); }
    .settings-input small { flex: none; font: 600 0.8125rem/1 var(--font-sans); color: var(--ink-subtle); }
    .settings-secret { -webkit-text-security: disc; }
    .settings-pair { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 12px; }
    .settings-pair + .settings-pair { margin-top: 8px; }
    .settings-pair label { flex: 1 1 auto; font: 700 0.875rem/1.3 var(--font-sans); }
    .settings-pair .settings-input { flex: 0 1 7.5rem; min-width: 0; }
    .settings-help { margin: 8px 0 0; font: 500 0.75rem/1.45 var(--font-sans); color: var(--ink-muted); }
    .settings-err { display: flex; gap: 8px; align-items: flex-start; margin: 8px 0 0; font: 600 0.8125rem/1.4 var(--font-sans); color: var(--danger); }
    .settings-err svg.i { width: 16px; height: 16px; margin-top: 1px; }
    .settings-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .settings-actions .btn { flex: 1 1 7rem; width: auto; margin: 0; }
    .settings-reason { display: flex; gap: 10px; align-items: flex-start; margin: 12px 0 0; font: 500 0.875rem/1.45 var(--font-sans); }
    .settings-reason svg.i { width: 18px; height: 18px; margin-top: 2px; color: var(--danger); }
    .settings-reason p { margin: 0; min-width: 0; overflow-wrap: anywhere; }
    /* the theme: one segmented control (base: surface-2, the choice in action), two by two where four do not fit */
    .settings-theme { container-type: inline-size; padding-top: 10px; }
    .settings-seg {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; padding: 3px;
      border-radius: var(--r-button); background: var(--surface-2);
    }
    @container (max-width: 18.5em) { .settings-seg { grid-template-columns: repeat(2, 1fr); } }
    .settings-seg label { position: relative; display: flex; min-width: 0; }
    .settings-seg input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
    .settings-seg span {
      flex: 1; display: flex; align-items: center; justify-content: center; min-height: 40px; padding: 4px 6px;
      border-radius: calc(var(--r-button) - 3px); color: var(--ink); font: 600 0.875rem/1.2 var(--font-sans);
      text-align: center; overflow-wrap: anywhere;   /* no colour transition: the pick and the page change together */
    }
    .settings-seg input:active + span { background: var(--surface-3); }
    .settings-seg input:checked + span { background: var(--action); color: var(--on-action); }
    .settings-seg input:focus-visible + span { outline: 2px solid var(--primary); outline-offset: 2px; }
  `);

  let root = null;
  let editing = null;      // 'kcal' | 'macro' | 'salt' | 'token' | null: the one editor that is open
  let ticker = 0;
  const parts = {};
  const shown = new WeakMap();

  // Repaint a part only when its markup changes, so a field being typed in keeps its text and focus.
  function paint(el, html) {
    if (shown.get(el) !== html) { el.innerHTML = html; shown.set(el, html); }
  }

  const fmt1 = v => (isNum(v) ? P.fmt(v, 1) : '–');
  const dateLabel = d => { const [y, m, day] = d.split('-').map(Number); return `${day} ${MON[m - 1]} ${y}`; };

  function ago(iso) {
    const t = iso ? Date.parse(iso) : NaN;
    if (!isNum(t)) return 'Never';
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return 'Just now';
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    const d = new Date(t);
    return `${d.getDate()} ${MON[d.getMonth()]}`;
  }

  // ── targets ───────────────────────────────────────────────────────
  function targetsHtml(t) {
    const rows = [
      ['kcal', 'Daily calories', '', isNum(t.kcal) ? `${P.fmt(t.kcal)} kcal` : '–'],
      ['macro', 'Macro split', SHARES.map(([, label], i) => (i ? label.toLowerCase() : label)).join(', '),
        `${SHARES.map(([key]) => fmt1(t[key])).join(' / ')}%`],
      ['salt', 'Salt', '', isNum(t.salt) ? `${P.fmt(t.salt, 2)} g` : '–'],
    ];
    return `<ul class="settings-list">${rows.map(([kind, name, sub, value]) => `<li>
      <button type="button" class="settings-row" data-act="edit" data-kind="${kind}" aria-expanded="${editing === kind}"${editing === kind ? ` aria-controls="settings-edit-${kind}"` : ''}>
        <span class="settings-t">${name}${sub ? `<span class="settings-sub">${sub}</span>` : ''}</span><span class="settings-v">${value}</span>
      </button>${editing === kind ? editorHtml(kind, t) : ''}</li>`).join('')}</ul>`;
  }

  const input = (name, value, mode, label, unit) => `<span class="settings-input"><input id="settings-in-${name}" name="${name}"
    inputmode="${mode}" autocomplete="off" enterkeyhint="done" value="${isNum(value) ? value : ''}"${label ? ` aria-label="${label}"` : ''}><small aria-hidden="true">${unit}</small></span>`;

  function formHtml(kind, fields, help, saveLabel = 'Save', cancel = true) {
    return `<div class="settings-edit" id="settings-edit-${kind}" data-form="${kind}">${fields}
      <p class="settings-help" data-help>${help}</p><p class="settings-err" data-err role="alert" hidden></p>
      <div class="settings-actions">${cancel ? '<button type="button" class="btn sec" data-act="cancel">Cancel</button>' : ''}<button type="button" class="btn" data-act="save">${saveLabel}</button></div></div>`;
  }

  function editorHtml(kind, t) {
    if (kind === 'kcal') return formHtml(kind, input('kcal', t.kcal, 'numeric', 'Daily calories', 'kcal'), 'Today counts down from this.');
    if (kind === 'salt') return formHtml(kind, input('salt', t.salt, 'decimal', 'Salt', 'g a day'), 'The salt limit for a day.');
    const pair = (name, label) => `<div class="settings-pair"><label for="settings-in-${name}">${label}</label>${input(name, t[name], 'decimal', '', '%')}</div>`;
    return formHtml(kind, SHARES.map(([key, label]) => pair(key, label)).join(''), macroLine(t.kcal, SHARES.map(([key]) => t[key])));
  }

  // shares: the three percentages in SHARES order.
  function macroLine(kcal, shares) {
    if (!shares.every(isNum)) return 'Shares of the day’s calories; together they make 100 %.';
    const sum = shares.reduce((a, b) => a + b, 0);
    if (Math.abs(sum - 100) > 0.05) return `Together ${P.fmt(sum, 1)} %; they have to make 100 %.`;
    return `At ${P.fmt(kcal)} kcal: ${SHARES.map(([, label, perGram], i) => `${P.fmt(kcal * shares[i] / 100 / perGram)} g ${label.toLowerCase()}`).join(', ')}.`;
  }

  // A typed number: thousands commas dropped from whole numbers, a decimal comma read as a point.
  function num(text, decimal) {
    let t = String(text).replace(/\s/g, '');
    t = decimal ? t.replace(',', '.') : t.replace(/,/g, '');
    return /^\d+(\.\d+)?$/.test(t) ? Number(t) : NaN;
  }

  const value = name => root.querySelector(`#settings-in-${name}`).value;

  // The rules are checked on the value that is stored, so a saved target always opens and saves again unchanged.
  function readTargets(kind) {
    if (kind === 'kcal') {
      const kcal = Math.round(num(value('kcal'), false));
      if (!(kcal >= 500 && kcal <= 10000)) return { error: 'Type the daily calories, between 500 and 10,000 kcal.' };
      return { patch: { kcal } };
    }
    if (kind === 'salt') {
      const salt = Math.round(num(value('salt'), true) * 100) / 100;
      if (!(salt > 0 && salt <= 50)) return { error: 'Type the grams of salt for a day, for example 5.8.' };
      return { patch: { salt } };
    }
    // The shares are kept as typed: rounding each one could break the 100 % they were just checked to make.
    const [p, c, f] = ['proteinPct', 'carbsPct', 'fatPct'].map(n => num(value(n), true));
    if (![p, c, f].every(v => v >= 0 && v <= 100)) return { error: 'Type each share as a number from 0 to 100.' };
    if (Math.abs(p + c + f - 100) > 0.05) return { error: `Together they make ${P.fmt(p + c + f, 1)} %; they have to make 100 %.` };
    return { patch: { proteinPct: p, carbsPct: c, fatPct: f } };
  }

  function formError(kind, text) {
    const form = root.querySelector(`[data-form="${kind}"]`);
    const err = form.querySelector('[data-err]');
    form.querySelector('[data-help]').hidden = true;
    err.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`;
    err.hidden = false;
  }

  function saveTargets(kind) {
    const { patch, error } = readTargets(kind);
    if (error) { formError(kind, error); return; }
    try {
      P.change(d => {
        // a change holds from today on; the days before keep the targets they had (P.targetsOn)
        const now = P.today(), log = d.settings.targetsLog;
        const kept = Array.isArray(log) && log.length ? log.filter(x => x.from < now)
          : [{ from: '2000-01-01', targets: { ...d.settings.targets } }];
        Object.assign(d.settings.targets, patch);
        d.settings.targetsLog = [...kept, { from: now, targets: { ...d.settings.targets } }];
      });
    } catch (e) { formError(kind, e.message); return; }
    close(`[data-kind="${kind}"]`);
  }

  // ── sync ──────────────────────────────────────────────────────────
  function statusHtml(s) {
    let pill = ['Synced', '', 'check'];   // grey: the app is grey + one orange (design/DESIGN.md, round 7)
    let sub = 'This phone';
    let reason = null;
    if (!s.configured) pill = ['Off', ''];
    else if (s.problem) { pill = ['Paused', 'bad', 'alert']; reason = s.problem; }
    else if (s.running) pill = ['Syncing', ''];
    else if (s.lastError) { pill = ['Failed', 'bad', 'alert']; sub = 'Changes are kept on this phone'; }
    else if (!s.online) { pill = ['Offline', '']; sub = 'Changes wait on this phone until it is online'; }
    else if (s.dirty || s.held) { pill = ['Waiting', '']; sub = 'Changes on this phone go up in a few seconds'; }
    if (s.lastError && !s.problem) reason = s.lastCause || s.lastError;
    const [word, tone, icon] = pill;
    return `<ul class="settings-list">
      <li class="settings-row"><span class="settings-t">GitHub data repo<span class="settings-sub">${s.configured ? `${P.esc(s.repo)}, private`
        : 'Not connected; the log stays on this phone'}</span></span>
        <span class="settings-pill ${tone}" data-test="sync-pill">${icon ? P.icon(icon) : ''}${word}</span></li>
      ${s.configured ? `<li class="settings-row"><span class="settings-t">Last sync<span class="settings-sub">${sub}</span></span>
        <span class="settings-v light" data-test="sync-last">${ago(s.lastSync)}</span></li>` : ''}</ul>
      ${reason ? `<div class="settings-reason" role="alert" data-test="sync-reason">${P.icon('alert')}<p>${P.esc(reason)}</p></div>
        ${s.running || s.problem ? '' : '<div class="settings-actions"><button type="button" class="btn sec" data-act="retry">Try again</button></div>'}` : ''}`;
  }

  // The repo and the token go in together; a connected phone's repo is filled in, so Replace can keep it.
  function tokenHtml(s) {
    if (!s.configured || editing === 'token') {
      return formHtml('token', `<label class="settings-label" for="settings-in-repo">Data repo</label>
        <span class="settings-input"><input id="settings-in-repo" name="repo" type="text" value="${s.configured ? P.esc(s.repo) : ''}"
          autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="next" placeholder="owner/pantry-data"></span>
        <label class="settings-label settings-next" for="settings-in-token">GitHub token</label>
        <span class="settings-input"><input id="settings-in-token" name="token" class="settings-secret" type="text"
          autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="go" placeholder="github_pat_…"></span>`,
      'A private repo of yours, and a fine-grained token for only that repo with Contents read and write. Paste it once; it stays on this phone and is never synced.',
      'Save and sync', s.configured);
    }
    return `<ul class="settings-list"><li class="settings-row"><span class="settings-t">GitHub token
      <span class="settings-sub settings-mask" data-test="token-mask">${P.esc(s.token)}</span></span>
      <button type="button" class="settings-ghost" data-act="replace">Replace</button></li></ul>`;
  }

  function saveToken() {
    const field = root.querySelector('#settings-in-token');
    const token = field.value.replace(/\s+/g, '');
    // the repo as owner/name; its github.com address works too
    const repo = value('repo').trim().replace(/^(https?:\/\/)?(www\.)?github\.com\//i, '').replace(/(\.git)?\/*$/i, '');
    if (!REPO.test(repo)) { formError('token', 'Type the data repo as owner/name, for example alex/pantry-data.'); return; }
    if (!token) { formError('token', 'Paste the token first.'); return; }
    if (!TOKEN.test(token)) { formError('token', 'This is not a GitHub token: a fine-grained one starts with github_pat_.'); return; }
    field.value = '';
    window.PantrySync.connect(token, repo);
    close('[data-act="replace"]');
  }

  // ── data ──────────────────────────────────────────────────────────
  // Every logged day: M from MyNetDiary (a day with an imported entry, even when Pantry logged more on it) plus P
  // logged only in Pantry, written "M (+P)" (Tarık: "460 (+10)"), "M" while P is 0, and "P" while M is 0 (no import).
  function dataHtml(doc) {
    const days = new Map();   // date -> true when MyNetDiary logged that day
    for (const e of doc.entries) {
      const m = IMPORTED.exec(e.id);
      days.set(e.date, days.get(e.date) === true || Boolean(m && m[1] === e.date));
    }
    const sorted = [...days.keys()].sort();
    const imported = [...days.values()].filter(Boolean).length, own = sorted.length - imported;
    const count = !imported ? P.fmt(own) : own ? `${P.fmt(imported)} (+${P.fmt(own)})` : P.fmt(imported);
    // Under the name, the count's key ("MyNetDiary (+ Pantry only)" for "464 (+2)"; none without MyNetDiary days) and
    // the range of days.
    const range = sorted.length ? `${dateLabel(sorted[0])} to ${dateLabel(sorted[sorted.length - 1])}` : '';
    const subs = !sorted.length ? ['None on this phone yet'] : !imported ? [range]
      : [own ? 'MyNetDiary (+ Pantry only)' : 'MyNetDiary', range];
    const groups = [['from MyNetDiary', ['mynetdiary']], ['scanned', ['coles', 'woolworths', 'off']], ['from labels', ['label']]]
      .map(([label, sources]) => [doc.foods.filter(f => sources.includes(f.source)).length, label]).filter(([n]) => n > 0);
    const foodsSub = !groups.length ? 'None yet' : groups.length === 1 ? `All ${groups[0][1]}` : groups.map(([n, l]) => `${P.fmt(n)} ${l}`).join(', ');
    return `<ul class="settings-list">
      <li class="settings-row settings-days" data-test="history"><span class="settings-t">Days logged${subs.map(s => `<span class="settings-sub">${s}</span>`).join('')}</span>
        <span class="settings-v" data-test="history-days">${count}</span></li>
      <li class="settings-row" data-test="foods"><span class="settings-t">Your foods<span class="settings-sub">${foodsSub}</span></span>
        <span class="settings-v">${P.fmt(doc.foods.length)}</span></li></ul>`;
  }

  // ── theme ─────────────────────────────────────────────────────────
  // The line under the choices says what the pick does. An absent or unknown settings.theme is System (app/core.js).
  const HELP = {
    dynamic: 'Light by day, dark from sunset to sunrise in Darwin.',
    light: 'Always light, whatever the phone is set to.',
    dark: 'Always dark, whatever the phone is set to.',
    system: 'Follows the phone’s light or dark mode.',
  };

  const themeHtml = () => `<div class="settings-seg" role="radiogroup" aria-labelledby="settings-h-theme">${THEMES.map(([value, label]) =>
    `<label><input type="radio" name="settings-theme" value="${value}"><span>${label}</span></label>`).join('')}</div>
    <p class="settings-help" data-test="theme-help"></p>`;

  // The choices are drawn once; a change only moves the mark, so the radio in use keeps its focus.
  function paintTheme() {
    const stored = P.doc().settings.theme;
    const pick = THEMES.some(([value]) => value === stored) ? stored : 'system';
    for (const radio of parts.theme.querySelectorAll('input')) radio.checked = radio.value === pick;
    const help = parts.theme.querySelector('[data-test="theme-help"]');
    if (help.textContent !== HELP[pick]) help.textContent = HELP[pick];
  }

  function onChange(e) {
    if (e.target.name !== 'settings-theme') return;
    const value = e.target.value;
    try { P.change(d => { d.settings.theme = value; }); } catch (err) { P.toast(err.message); paintTheme(); }
  }

  // ── screen ────────────────────────────────────────────────────────
  function refresh(full) {
    if (!root) return;
    const doc = P.doc();
    const sync = window.PantrySync;
    if (full || !TARGETS.includes(editing)) paint(parts.targets, targetsHtml(doc.settings.targets));
    if (sync) {
      const s = sync.status();
      paint(parts.status, statusHtml(s));
      paint(parts.token, tokenHtml(s));
    } else {
      paint(parts.status, '<p class="note">Sync is not installed in this version of Pantry.</p>');
    }
    paint(parts.data, dataHtml(doc));
    paintTheme();
  }

  function open(kind) {
    editing = editing === kind ? null : kind;
    refresh(true);
    const field = editing && root.querySelector(`[data-form="${editing}"] input`);
    if (field) { field.focus(); field.select(); }
  }

  function close(focusSelector) {
    editing = null;
    refresh(true);
    const back = focusSelector && root.querySelector(focusSelector);
    if (back) back.focus();
  }

  function save(kind) {
    if (kind === 'token') saveToken(); else if (TARGETS.includes(kind)) saveTargets(kind);
  }

  function onClick(e) {
    const btn = e.target.closest('[data-act]');
    if (!btn || !root.contains(btn)) return;
    const act = btn.dataset.act;
    const form = btn.closest('[data-form]');
    if (act === 'back') P.back();
    else if (act === 'edit') open(btn.dataset.kind);
    else if (act === 'replace') open('token');
    else if (act === 'cancel') close(form && form.dataset.form !== 'token' ? `[data-kind="${form.dataset.form}"]` : '[data-act="replace"]');
    else if (act === 'save' && form) save(form.dataset.form);
    else if (act === 'retry' && window.PantrySync) window.PantrySync.now();
  }

  function onKey(e) {
    const form = e.target.closest && e.target.closest('[data-form]');
    if (!form || e.target.tagName !== 'INPUT') return;
    if (e.key === 'Enter') { e.preventDefault(); save(form.dataset.form); }
    else if (e.key === 'Escape' && (form.dataset.form !== 'token' || editing === 'token')) {
      e.preventDefault();
      close(form.dataset.form !== 'token' ? `[data-kind="${form.dataset.form}"]` : '[data-act="replace"]');
    }
  }

  function onInput(e) {
    const form = e.target.closest && e.target.closest('[data-form="macro"]');
    if (!form) return;
    const help = form.querySelector('[data-help]');
    help.textContent = macroLine(P.doc().settings.targets.kcal, SHARES.map(([key]) => num(value(key), true)));
    help.hidden = false;
    form.querySelector('[data-err]').hidden = true;
  }

  const onSync = () => refresh();

  function render(el) {
    root = el;
    editing = null;
    el.innerHTML = `
      <header class="top back"><button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>
        <div><p class="eyebrow">Pantry</p><h1 class="title">Settings</h1></div></header>
      <div class="settings-body">
        <section class="settings-group" aria-labelledby="settings-h-targets"><h2 class="eyebrow" id="settings-h-targets">Targets</h2><div data-part="targets"></div></section>
        <section class="settings-group" aria-labelledby="settings-h-theme"><h2 class="eyebrow" id="settings-h-theme">Theme</h2><div class="settings-theme" data-part="theme">${themeHtml()}</div></section>
        <section class="settings-group" aria-labelledby="settings-h-sync"><h2 class="eyebrow" id="settings-h-sync">Sync</h2><div data-part="status"></div><div data-part="token"></div></section>
        <section class="settings-group" aria-labelledby="settings-h-data"><h2 class="eyebrow" id="settings-h-data">Data</h2><div data-part="data"></div></section>
      </div>`;
    for (const name of ['targets', 'status', 'token', 'data', 'theme']) parts[name] = el.querySelector(`[data-part="${name}"]`);
    el.addEventListener('click', onClick);
    el.addEventListener('keydown', onKey);
    el.addEventListener('input', onInput);
    el.addEventListener('change', onChange);
    window.addEventListener('pantrysync', onSync);
    clearInterval(ticker);
    ticker = setInterval(onSync, 30000);
    refresh(true);
  }

  function leave() {
    window.removeEventListener('pantrysync', onSync);
    clearInterval(ticker);
    root = null;
    editing = null;
  }

  P.view('settings', { render, update: () => refresh(), leave });
})();

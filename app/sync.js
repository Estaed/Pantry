/* Sync: keeps the phone's food log and the private GitHub data repo (Estaed/Pantry-Data, file pantry-data.json,
   default branch) in step through the GitHub Contents API. Ported from Calisthenics-App (config apart from the data,
   sha handling, dirty flag, single flight, retry); its whole-document replace is not ported: Pantry merges.

   When    a pull when the app opens, comes back to the foreground or back online; a push 10 s after the last change
           (never sooner, so an Undo inside a 4 s toast never meets a pushed tombstone); offline it waits, no banner.
           After a failure it tries again after 15 s, 30 s, 1, 2, then every 5 minutes.
   Merge   entries and foods by id. One only on one side is kept, unless its id is in doc.removed (the two removed
           lists are united, so a deletion on either side wins). An id on both sides: the phone's version when the
           phone changed that id since its last push that carried it, else the repo's. settings the same way, as one
           unit. catalogue comes from the repo. Other top-level keys: the repo's. Order: the repo's, then the
           phone's own at the end.
   Repo    GET with the object media type gives the sha, and the content up to 1 MB; above 1 MB the content is empty
           (the default media type answers the same) and the text comes from the raw media type. PUT sends the sha
           it read; 409 (or 422 for a PUT without a sha: the file appeared meanwhile) means the repo moved on, so it
           pulls, merges and pushes again, at most three rounds; it never writes without the current sha.
   State   Pantry.syncState(), the 'pantry.sync' object, never inside the document: token, sha (the repo version
           this phone holds in full), changed ({ entries: { id: n }, foods: { id: n }, settings: n }: what the
           phone changed, stamped with Pantry.changes(); a push carrying a stamp clears it), lastSync (ISO time of
           the last sync that ended well), lastError (a sentence for Today's banner, or null), lastCause (the plain
           reason for Settings, or null).
   API     window.PantrySync: now() runs a sync (single flight, never rejects); connect(token) stores the token and
           syncs; status() what Settings shows; merge(local, remote, changed) the pure merge; mask(token); REPO.
           Fires 'pantrysync' on window when its in-memory state (running, waiting, offline) changes. */
(() => {
  'use strict';

  const P = window.Pantry;
  const REPO = 'Estaed/Pantry-Data';
  const API = `https://api.github.com/repos/${REPO}`;
  const CONTENTS = `${API}/contents/pantry-data.json`;
  const HOLD_MS = 10250;   // 10 s and a margin: a browser timer can fire a few ms early by the system's clock
  const RETRY_MS = [15000, 30000, 60000, 120000, 300000];
  const ROUNDS = 3;
  const VERSION = 1;
  const PREFIX = 'Sync failed. Saved on this phone; it will try again.';

  let running = null;      // the promise of the sync in progress, reruns included
  let rerun = false;
  let held = false;        // true until HOLD_MS after the last change
  let holdTimer = 0;
  let retryTimer = 0;
  let failures = 0;
  let applying = null;     // Pantry.changes() while sync writes a merged document, so the subscriber skips that write
  let pendingSha = null;   // a repo version already merged here whose merge still has to be pushed

  const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const emit = () => window.dispatchEvent(new Event('pantrysync'));

  // Deep equality of JSON values; a key holding undefined counts as absent, as it does once saved.
  function same(a, b) {
    if (a === b) return true;
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false;
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    if (Array.isArray(a)) {
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) if (!same(a[i], b[i])) return false;
      return true;
    }
    const ka = Object.keys(a).filter(k => a[k] !== undefined);
    const kb = Object.keys(b).filter(k => b[k] !== undefined);
    if (ka.length !== kb.length) return false;
    for (const k of ka) if (!same(a[k], b[k])) return false;
    return true;
  }

  // ── merge ─────────────────────────────────────────────────────────
  function merge(local, remote, changed) {
    const mark = isObj(changed) ? changed : {};
    const removed = [];
    const gone = new Set();
    for (const r of [...(remote.removed || []), ...(local.removed || [])]) {
      if (isObj(r) && !gone.has(r.id)) { gone.add(r.id); removed.push(r); }
    }
    const pick = (mine, theirs, phoneChanged) => {
      const byId = new Map(mine.map(x => [x.id, x]));
      const seen = new Set();
      const out = [];
      for (const r of theirs) {
        seen.add(r && r.id);
        const l = r && byId.get(r.id);
        out.push(l !== undefined && Object.prototype.hasOwnProperty.call(phoneChanged, r.id) ? l : r);
      }
      for (const l of mine) if (!seen.has(l.id)) out.push(l);
      return out.filter(x => !(x && gone.has(x.id)));
    };
    const out = {
      ...local, ...remote, version: VERSION,
      foods: pick(local.foods, remote.foods, isObj(mark.foods) ? mark.foods : {}),
      entries: pick(local.entries, remote.entries, isObj(mark.entries) ? mark.entries : {}),
      settings: mark.settings !== undefined || !isObj(remote.settings) ? local.settings : remote.settings,
    };
    if (removed.length) out.removed = removed; else delete out.removed;
    if (remote.catalogue !== undefined) out.catalogue = remote.catalogue; else delete out.catalogue;
    return structuredClone(out);
  }

  // What the phone changed: diff the document before and after each change of its own.
  function diffIds(before, after) {
    const prev = new Map(before.map(x => [x.id, x]));
    const ids = [];
    for (const x of after) {
      const p = prev.get(x.id);
      if (p === undefined || !same(p, x)) ids.push(x.id);
      prev.delete(x.id);
    }
    for (const id of prev.keys()) ids.push(id);
    return ids;
  }

  // Marks not yet written to 'pantry.sync'. They are written right after the change's announcement (a microtask,
  // so other subscribers still hear 'change' before 'sync'); changed() reads them on top of the stored ones.
  let marks = null;

  function overlay(stored, extra) {
    const c = isObj(stored) ? stored : {};
    const out = { entries: { ...(isObj(c.entries) ? c.entries : {}) }, foods: { ...(isObj(c.foods) ? c.foods : {}) } };
    if (c.settings !== undefined) out.settings = c.settings;
    if (extra) {
      Object.assign(out.entries, extra.entries);
      Object.assign(out.foods, extra.foods);
      if (extra.settings !== undefined) out.settings = extra.settings;
    }
    return out;
  }
  const changed = () => overlay(P.syncState().changed, marks);

  function flush() {
    if (!marks) return;
    const next = changed();
    marks = null;
    P.setSyncState({ changed: next });
  }

  P.subscribe((doc, why, prev) => {
    if (why !== 'change' || !prev || (applying !== null && P.changes() === applying)) return;
    hold();
    const entries = diffIds(prev.entries, doc.entries);
    const foods = diffIds(prev.foods, doc.foods);
    const settings = !same(prev.settings, doc.settings);
    if (!entries.length && !foods.length && !settings) return;
    const stamp = P.changes();
    if (!marks) { marks = { entries: {}, foods: {} }; queueMicrotask(flush); }
    for (const id of entries) marks.entries[id] = stamp;
    for (const id of foods) marks.foods[id] = stamp;
    if (settings) marks.settings = stamp;
  });

  function prune(upTo) {
    flush();
    const c = changed();
    const keep = o => Object.fromEntries(Object.entries(o).filter(([, n]) => n > upTo));
    const out = { entries: keep(c.entries), foods: keep(c.foods) };
    if (c.settings > upTo) out.settings = c.settings;
    return out;
  }

  function hold() {
    held = true;
    clearTimeout(holdTimer);
    holdTimer = setTimeout(() => { held = false; emit(); now(); }, HOLD_MS);
    emit();
  }

  // ── GitHub ────────────────────────────────────────────────────────
  // A failure carries the plain cause; fix = the cure is in Settings (the token).
  function failure(cause, fix = false, extra = {}) {
    return Object.assign(new Error(cause), { syncCause: cause, fix }, extra);
  }

  function headers(token, accept, extra = {}) {
    return { Authorization: `Bearer ${token}`, Accept: accept, 'X-GitHub-Api-Version': '2022-11-28', ...extra };
  }

  async function call(url, init) {
    try {
      return await fetch(url, { cache: 'no-store', ...init });
    } catch (e) {
      throw failure('GitHub could not be reached', false, { network: true });
    }
  }

  function statusFailure(res, writing) {
    const limited = res.status === 429 || (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0');
    if (res.status === 401) return failure('The GitHub token may have expired', true);
    if (limited) return failure('GitHub is limiting requests for now');
    if (res.status === 403) return failure(`The GitHub token cannot ${writing ? 'write to' : 'read'} ${REPO}; it needs Contents read and write`, true);
    if (res.status === 404) return failure(`The GitHub token cannot see ${REPO}; check its repository access`, true);
    return failure(`GitHub answered ${res.status}`);
  }

  function decode(b64) {
    const bin = atob(String(b64).replace(/\s/g, ''));
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  }

  function encode(text) {
    const bytes = new TextEncoder().encode(text);
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  }

  async function json(res) {
    try { return await res.json(); } catch (e) { throw failure('GitHub sent an answer Pantry could not read'); }
  }

  // { exists: false } or { exists: true, sha, text }: text is null when the file is above 1 MB.
  async function readMeta(token) {
    const res = await call(CONTENTS, { headers: headers(token, 'application/vnd.github.object+json') });
    if (res.status === 404) {
      // A missing file, a missing repo and a token that cannot see the repo all answer 404: ask the repo.
      const repo = await call(API, { headers: headers(token, 'application/vnd.github+json') });
      if (repo.ok) return { exists: false };
      throw statusFailure(repo, false);
    }
    if (!res.ok) throw statusFailure(res, false);
    const meta = await json(res);
    if (!isObj(meta) || typeof meta.sha !== 'string' || !meta.sha) throw failure('GitHub sent an answer Pantry could not read');
    const inline = meta.encoding === 'base64' && typeof meta.content === 'string' ? decode(meta.content) : null;
    return { exists: true, sha: meta.sha, text: inline === '' && meta.size > 0 ? null : inline };
  }

  async function readRaw(token) {
    const res = await call(CONTENTS, { headers: headers(token, 'application/vnd.github.raw+json') });
    if (!res.ok) throw statusFailure(res, false);
    return res.text();
  }

  // The repo's document, or null for an empty file (nothing there to keep).
  function parse(text) {
    if (!text || !text.trim()) return null;
    let doc;
    try { doc = JSON.parse(text); } catch (e) { throw failure('The file in the data repo is not valid JSON; nothing was written over it'); }
    if (isObj(doc) && typeof doc.version === 'number' && doc.version > VERSION) {
      throw failure('The data repo was saved by a newer Pantry; reload Pantry to update');
    }
    if (!isObj(doc) || doc.version !== VERSION || !Array.isArray(doc.foods) || !Array.isArray(doc.entries)
      || (doc.removed !== undefined && !Array.isArray(doc.removed))) {
      throw failure('The file in the data repo is not a Pantry food log; nothing was written over it');
    }
    return doc;
  }

  function finish(patch) {
    failures = 0;
    clearTimeout(retryTimer);
    P.setSyncState({ ...patch, lastSync: new Date().toISOString(), lastError: null, lastCause: null });
  }

  async function push(token, sha) {
    if (held) return 'held';                       // the hold timer runs the sync again when it ends
    const upTo = P.changes();
    const body = { message: `Pantry sync ${new Date().toISOString()}`, content: encode(JSON.stringify(P.doc()) + '\n') };
    if (sha) body.sha = sha;
    const res = await call(CONTENTS, {
      method: 'PUT',
      headers: headers(token, 'application/vnd.github+json', { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
    // 409: the sha is stale; 422 without a sha: the file appeared since it was read as missing. Pull and merge again.
    if (res.status === 409 || (res.status === 422 && !sha)) throw failure('The data repo kept changing during the sync', false, { stale: true });
    if (res.status === 422) throw failure('GitHub refused the file (422)');
    if (!res.ok) throw statusFailure(res, true);
    const answer = await json(res);
    pendingSha = null;
    P.markClean(upTo);
    finish({ sha: answer && answer.content && answer.content.sha, changed: prune(upTo) });
    return 'pushed';
  }

  function apply(merged) {
    applying = P.changes();
    try {
      P.change(() => merged, { dirty: false });
    } catch (e) {
      throw failure(/^Could not save/.test(e.message) ? e.message.replace(/\.$/, '')
        : `The file in the data repo could not be used (${e.message}); nothing was written over it`);
    } finally {
      applying = null;
    }
  }

  async function attempt(token) {
    const remote = await readMeta(token);
    if (!remote.exists) return push(token, null);
    if (remote.sha === P.syncState().sha) {
      if (P.dirty()) return push(token, remote.sha);
      finish({});
      return 'same';
    }
    if (remote.sha === pendingSha) return push(token, remote.sha);
    const theirs = parse(remote.text === null ? await readRaw(token) : remote.text);
    if (theirs === null) { pendingSha = remote.sha; return push(token, remote.sha); }
    // From here to the push no await: the phone's document cannot change in between.
    const upTo = P.changes();
    const merged = merge(P.doc(), theirs, changed());
    if (!same(merged, P.doc())) apply(merged);
    if (same(merged, theirs)) {
      pendingSha = null;
      P.markClean(upTo);
      finish({ sha: remote.sha, changed: prune(upTo) });
      return 'pulled';
    }
    pendingSha = remote.sha;
    return push(token, remote.sha);
  }

  async function rounds(token) {
    for (let round = 1; ; round++) {
      try {
        return await attempt(token);
      } catch (e) {
        if (!e.stale || round >= ROUNDS) throw e;
      }
    }
  }

  function failed(e) {
    if (e && e.network && navigator.onLine === false) return;      // went offline mid-sync: wait for 'online'
    if (!(e && e.syncCause)) console.error('Pantry: sync failed unexpectedly', e);
    const cause = e && e.syncCause ? e.syncCause : `Something went wrong (${e && e.message})`;
    P.setSyncState({ lastError: `${PREFIX} ${cause}${e && e.fix ? ': Settings, Sync.' : '.'}`, lastCause: `${cause}.` });
    clearTimeout(retryTimer);
    retryTimer = setTimeout(now, RETRY_MS[Math.min(failures, RETRY_MS.length - 1)]);
    failures += 1;
  }

  async function loop() {
    do {
      rerun = false;
      const token = P.syncState().token;
      if (!token || P.problem() || navigator.onLine === false) break;
      try { await rounds(token); } catch (e) { failed(e); }
    } while (rerun);
  }

  function now() {
    if (!P.syncState().token || P.problem() || navigator.onLine === false) { emit(); return Promise.resolve(); }
    if (running) { rerun = true; return running; }
    running = loop().catch(e => console.error('Pantry: sync loop failed', e)).finally(() => { running = null; emit(); });
    emit();
    return running;
  }

  function connect(token) {
    failures = 0;
    clearTimeout(retryTimer);
    P.setSyncState({ token, lastError: null, lastCause: null });
    return now();
  }

  function mask(token) {
    if (!token) return '';
    const kind = /^(github_pat_|ghp_)/.exec(token);
    return `${kind ? kind[1] : ''}••••${token.slice(-4)}`;
  }

  function status() {
    const st = P.syncState();
    return {
      configured: Boolean(st.token), running: Boolean(running), held, online: navigator.onLine !== false,
      dirty: P.dirty(), lastSync: st.lastSync || null, lastError: st.lastError || null, lastCause: st.lastCause || null,
      token: mask(st.token), problem: P.problem(),
    };
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' || (P.dirty() && !held)) now();
  });
  window.addEventListener('online', () => { emit(); now(); });
  window.addEventListener('offline', emit);

  window.PantrySync = Object.freeze({ now, connect, status, merge, mask, REPO });
  now();
})();

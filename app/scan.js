/* Scan ('#/scan/<meal>/<date>', design/screens.html, 5. Scan): reads a pack's EAN-13 with the rear camera through
   the phone's built-in reader (BarcodeDetector), or takes the digits typed from the pack, then opens what Pantry knows
   about that code. One of his foods with that barcode opens its gram sheet ('food id meal date', no lookup); any other
   code opens New food ('newfood code meal date', app/newfood.js), which looks in the store catalogue, then Open Food
   Facts, then asks for the label. A missing meal is Pantry.mealNow(), a missing date today; both are passed on.
   A code is taken only when its check digit is right and the reader returned it twice, so a misread never starts a
   lookup. Leaving the screen by any route, or the app going to the background, stops every camera track.
   Scan's history entry remembers the code it handed on, so coming back to it (Back from what it opened) does not
   open the pack still in view again: that code is held, any other code opens, and "Open it again" reopens it.
   Gate hooks: data-test="scan-status" holds the status or the reason scanning cannot work; data-test="scan-code" holds
   the last code read; the close button is named "Back". */
(() => {
  const P = window.Pantry;
  const MEALS = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snacks: 'Snacks' };
  const ICON = {
    kbd: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    flash: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  };
  const icon = k => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[k]}</svg>`;

  let last = null;        // this session's last read: { code, seconds }
  let screen = null;      // the shown scan screen: { el, meal, date, held }; held = the read this entry handed on
  let run = null;         // the running camera: { stream, track, raf, t0, seen, found, ended, detector }

  P.css(`
    .scan-screen { background: var(--canvas); }
    .scan-cam {
      /* the camera area stays dark in both themes (design/screens.html, 5. Scan) */
      --cam: #0B0B0B; --cam-ink: #EEEEEE; --cam-muted: #ABABAB; --cam-veil: rgb(11 11 11 / 0.55);
      position: relative; flex: 1 0 260px; margin-bottom: -28px; overflow: hidden; background: var(--cam); color: var(--cam-ink);
    }
    .scan-cam video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .scan-bar { position: absolute; z-index: 1; left: 0; right: 0; top: 0; padding: 14px 8px; display: flex; justify-content: space-between; }
    .scan-bar .ibtn { color: var(--cam-ink); background: var(--cam-veil); border-radius: 50%; }
    .scan-bar .ibtn[aria-pressed="true"] { background: var(--cam-ink); color: var(--cam); }
    .scan-mid {
      position: absolute; inset: 72px 20px 48px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
    }
    .scan-finder { position: relative; width: min(260px, 100%); aspect-ratio: 26 / 15; flex: none; }
    .scan-finder i { position: absolute; width: 34px; height: 34px; border: 3px solid var(--cam-ink); }
    .scan-finder i:nth-of-type(1) { left: 0; top: 0; border-right: 0; border-bottom: 0; border-radius: 12px 0 0 0; }
    .scan-finder i:nth-of-type(2) { right: 0; top: 0; border-left: 0; border-bottom: 0; border-radius: 0 12px 0 0; }
    .scan-finder i:nth-of-type(3) { left: 0; bottom: 0; border-right: 0; border-top: 0; border-radius: 0 0 0 12px; }
    .scan-finder i:nth-of-type(4) { right: 0; bottom: 0; border-left: 0; border-top: 0; border-radius: 0 0 12px 0; }
    .scan-laser { position: absolute; left: 18px; right: 18px; top: 50%; height: 2px; border-radius: 2px; background: var(--chart-1); }
    .scan-hint {
      margin: 0; max-width: 100%; padding: 4px 12px; border-radius: var(--r-pill); background: var(--cam-veil);
      font: 600 0.9375rem/1.4 var(--font-sans); color: var(--cam-ink); text-align: center;
    }
    /* no camera (no reader, no permission): the screen becomes a plain page and says why */
    .scan-cam.scan-off { flex: none; margin-bottom: 0; overflow: visible; background: none; color: var(--ink); }
    .scan-off video, .scan-off .scan-finder { display: none; }
    .scan-off .scan-bar { position: static; padding: 18px 8px 0; }
    .scan-off .scan-bar .ibtn { color: var(--ink); background: none; }
    .scan-off .scan-mid { position: static; display: block; padding: 0 0 20px; }
    .scan-off .scan-hint { padding: 0; background: none; color: var(--ink-muted); font-weight: 500; text-align: left; margin: 0 20px; }
    .scan-off .scan-hint.banner { margin: 0 20px; padding: 12px 14px; background: var(--surface-2); color: var(--ink); border-radius: var(--r-card); }
    .scan-hint.banner > div { min-width: 0; overflow-wrap: anywhere; }   /* a long word ('BarcodeDetector') breaks at 240 px with large text */
    .scan-sheet {
      position: relative; z-index: 1; display: flex; flex-direction: column; gap: 10px;
      padding: 10px 20px calc(18px + env(safe-area-inset-bottom)); text-align: center;
      background: var(--surface-1); border-top: 1px solid var(--hairline-strong); border-radius: 28px 28px 0 0;
    }
    .scan-off + .scan-sheet { margin-top: auto; }
    .scan-handle { align-self: center; width: 36px; height: 4px; border-radius: 4px; background: var(--hairline-strong); }
    .scan-for { margin: 0; font: 700 1.0625rem/1.3 var(--font-sans); overflow-wrap: anywhere; }
    .scan-sheet .note, .scan-sheet .btn.sec { margin: 0; }   /* base.css gives .sec (a section) a margin; here it is the secondary button */
    .scan-last { margin: 0; font: 500 0.8125rem/1.4 var(--font-sans); color: var(--ink-muted); }
    .scan-last b { font: 700 0.8125rem/1.4 var(--font-figure); color: var(--ink); white-space: nowrap; }
    .scan-type { display: flex; flex-direction: column; gap: 10px; text-align: left; }
    .scan-type label { font: 700 0.875rem/1.3 var(--font-sans); }
    .scan-type input {
      width: 100%; min-height: 48px; padding: 12px 16px; border: 0; border-radius: var(--r-md); background: var(--surface-2);
      font: 600 1.0625rem/1.3 var(--font-figure); letter-spacing: 0.04em; color: var(--ink);
    }
    .scan-type input::placeholder { color: var(--ink-muted); letter-spacing: 0; font-weight: 500; }
    .scan-type input:focus { outline: none; box-shadow: inset 0 0 0 2px var(--primary); }
    .scan-type input[aria-invalid="true"] { box-shadow: inset 0 0 0 2px var(--danger); }
    .scan-err { display: flex; gap: 8px; align-items: flex-start; margin: 0; font: 600 0.8125rem/1.4 var(--font-sans); color: var(--danger); }
    .scan-err svg.i { width: 16px; height: 16px; margin-top: 1px; }
  `);

  // GS1 check digit (EAN-13, EAN-8, UPC-A): a misread or a mistyped digit fails here and is never looked up.
  function validCode(code) {
    if (!/^(\d{8}|\d{12}|\d{13})$/.test(code)) return false;
    const d = [...code].map(Number);
    const check = d.pop();
    const sum = d.reverse().reduce((s, v, i) => s + v * (i % 2 ? 1 : 3), 0);
    return (10 - (sum % 10)) % 10 === check;
  }
  // One product, however its code is written: GTINs are right-aligned, so leading zeros carry nothing.
  const sameCode = (a, b) => String(a).replace(/^0+/, '') === String(b).replace(/^0+/, '');
  const grouped = code => (code.length === 13 ? `${code[0]} ${code.slice(1, 7)} ${code.slice(7)}` : code);   // as printed under the bars

  function cameraProblem(e) {
    const name = e && e.name;
    if (name === 'NotAllowedError' || name === 'SecurityError') return 'Camera access is blocked for Pantry. Allow the camera in Chrome\'s site settings and open Scan again, or type the barcode.';
    if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'No camera was found on this phone. Type the barcode instead.';
    if (name === 'NotReadableError') return 'The camera is in use by another app. Close it and open Scan again, or type the barcode.';
    return `The camera did not start (${name || 'unknown error'}). Type the barcode instead.`;
  }

  function render(el, meal, date) {
    const m = MEALS[meal] ? meal : P.mealNow();
    const d = /^\d{4}-\d{2}-\d{2}$/.test(date || '') ? date : P.today();
    const st = history.state;
    const held = st && st.scanHanded && typeof st.scanHanded.code === 'string' ? st.scanHanded : null;
    screen = { el, meal: m, date: d, held };
    el.classList.add('scan-screen');
    const day = d === P.today() ? '' : `, ${P.dayLabel(d)}`;
    el.innerHTML = `
      <div class="scan-cam">
        <video playsinline muted aria-label="Camera"></video>
        <div class="scan-bar">
          <button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('x')}</button>
          <button class="ibtn" type="button" data-act="torch" aria-label="Torch" aria-pressed="false" hidden>${icon('flash')}</button>
        </div>
        <div class="scan-mid">
          <div class="scan-finder" aria-hidden="true"><i></i><i></i><i></i><i></i><span class="scan-laser"></span></div>
          <p class="scan-hint" role="status" data-test="scan-status">Starting the camera.</p>
        </div>
      </div>
      <div class="scan-sheet">
        <div class="scan-handle" aria-hidden="true"></div>
        <h1 class="scan-for">Scanning for ${MEALS[m]}${P.esc(day)}</h1>
        <p class="note">Looks in your foods, then Coles and Woolworths, then Open Food Facts.</p>
        <p class="scan-last" hidden>Last read <b data-test="scan-code"></b>. <span class="scan-took"></span></p>
        <button class="btn sec" type="button" data-act="again" hidden>Open it again</button>
        <button class="btn sec" type="button" data-act="type">${icon('kbd')}Type the barcode</button>
        <form class="scan-type" novalidate hidden>
          <label for="scan-digits">Barcode</label>
          <input id="scan-digits" name="digits" inputmode="numeric" autocomplete="off" enterkeyhint="search"
            placeholder="13 digits" aria-describedby="scan-err">
          <p class="scan-err" id="scan-err" role="alert" hidden></p>
          <button class="btn" type="submit">Look it up</button>
        </form>
      </div>`;
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    el.querySelector('[data-act="torch"]').addEventListener('click', torch);
    el.querySelector('[data-act="again"]').addEventListener('click', () => open(screen.held));
    el.querySelector('[data-act="type"]').addEventListener('click', () => openTyping(true));
    el.querySelector('.scan-type').addEventListener('submit', typed);
    el.querySelector('#scan-digits').addEventListener('input', e => { e.target.removeAttribute('aria-invalid'); el.querySelector('.scan-err').hidden = true; });
    showLast();
    start();
  }

  function say(text, bad) {
    const box = screen.el.querySelector('[data-test="scan-status"]');
    box.className = bad ? 'scan-hint banner' : 'scan-hint';
    box.setAttribute('role', bad ? 'alert' : 'status');
    box.innerHTML = bad ? `${P.icon('alert')}<div>${P.esc(text)}</div>` : P.esc(text);
    screen.el.querySelector('.scan-cam').classList.toggle('scan-off', !!bad);
    if (bad) openTyping(false);   // typing is the way left: the field is there, the keyboard waits for a tap
  }

  function showLast() {
    const read = screen.held || last;
    const box = screen.el.querySelector('.scan-last');
    box.hidden = !read;
    screen.el.querySelector('[data-act="again"]').hidden = !screen.held;
    if (!read) return;
    box.querySelector('[data-test="scan-code"]').textContent = grouped(read.code);
    box.querySelector('.scan-took').textContent = read.seconds === null ? 'Typed.' : `Read in ${read.seconds.toFixed(1)} s.`;
  }

  async function start() {
    const me = run = { stream: null, track: null, raf: 0, t0: 0, seen: null, found: false, ended: false, detector: null };
    if (typeof window.BarcodeDetector !== 'function') {
      return say('This browser has no built-in barcode reader: BarcodeDetector is missing, so Pantry cannot scan here. Type the barcode instead.', true);
    }
    let formats = null;
    try { formats = await window.BarcodeDetector.getSupportedFormats(); } catch (e) { formats = null; }
    if (me.ended) return;
    if (!Array.isArray(formats) || !formats.includes('ean_13')) {
      const known = Array.isArray(formats) && formats.length ? ` It reads ${formats.join(', ')}.` : '';
      return say(`This phone's barcode reader cannot read EAN-13, the barcode on food packs.${known} Type the barcode instead.`, true);
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return say('The camera only opens when Pantry runs from its https address. Type the barcode instead.', true);
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } } });
    } catch (e) {
      if (!me.ended) say(cameraProblem(e), true);
      return;
    }
    if (me.ended) { stream.getTracks().forEach(t => t.stop()); return; }   // left while the camera was starting
    me.stream = stream;
    me.track = stream.getVideoTracks()[0] || null;
    const video = screen.el.querySelector('video');
    video.srcObject = stream;
    try { await video.play(); } catch (e) { /* muted inline video plays without a gesture; frames arrive anyway */ }
    if (me.ended) return;
    try { me.detector = new window.BarcodeDetector({ formats: ['ean_13'] }); } catch (e) {
      return say(`The barcode reader did not start (${e.name || e.message}). Type the barcode instead.`, true);
    }
    offerTorch(me);
    look(me);
  }

  function look(me) {
    me.found = false;
    me.seen = null;
    me.t0 = performance.now();
    const held = screen.held && screen.held.code;   // the pack he came back from may still be in view
    say(held ? 'Point at another barcode' : 'Point at the barcode');
    const video = screen.el.querySelector('video');
    const tick = async () => {
      if (me.ended || me.found) return;
      if (video.readyState >= 2) {
        let codes = [];
        try { codes = await me.detector.detect(video); } catch (e) { codes = []; }   // a frame it could not take
        if (me.ended) return;
        const hit = codes.find(c => c.format === 'ean_13' && /^\d{13}$/.test(c.rawValue) && validCode(c.rawValue)
          && !(held && sameCode(c.rawValue, held)));
        if (hit) {
          if (me.seen === hit.rawValue) return found(me, hit.rawValue);
          me.seen = hit.rawValue;
        }
      }
      me.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  function found(me, code) {
    me.found = true;
    last = { code, seconds: (performance.now() - me.t0) / 1000 };
    if (navigator.vibrate) navigator.vibrate(40);
    showLast();
    open(last);
  }

  // His foods first: a barcode is never stored twice, so a saved product always opens the same food.
  // The read is stamped on this Scan's history entry first, so Back to it holds that code (render, look).
  function open(read) {
    const { code } = read;
    const { meal, date } = screen;
    try { history.replaceState({ ...(history.state || {}), scanHanded: { code, seconds: read.seconds } }, ''); } catch (e) { /* only the hold is lost */ }
    const food = P.doc().foods.find(f => typeof f.barcode === 'string' && sameCode(f.barcode, code));
    if (food) P.go('food', food.id, meal, date);
    else P.go('newfood', code, meal, date);
  }

  function openTyping(focus) {
    const form = screen.el.querySelector('.scan-type');
    screen.el.querySelector('[data-act="type"]').hidden = true;
    form.hidden = false;
    if (focus) form.elements.digits.focus();
  }

  function typed(e) {
    e.preventDefault();
    const input = e.target.elements.digits;
    const raw = input.value.replace(/[\s-]/g, '');
    const fail = text => {
      const err = screen.el.querySelector('.scan-err');
      err.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`;
      err.hidden = false;
      input.setAttribute('aria-invalid', 'true');
      input.focus();
    };
    if (!raw) return fail('Type the digits printed under the bars.');
    if (!/^\d+$/.test(raw)) return fail('A barcode is digits only. Type the numbers under the bars.');
    const code = raw.length === 12 ? '0' + raw : raw;   // a UPC-A is an EAN-13 with a leading 0
    if (code.length !== 13 && code.length !== 8) return fail(`A barcode has 13 digits (8 on small packs); this has ${raw.length}.`);
    if (!validCode(code)) return fail('These digits do not add up: the last one is a check digit. Compare them with the pack once more.');
    last = { code, seconds: null };
    open(last);
  }

  function offerTorch(me) {
    let caps = {};
    try { caps = (me.track && me.track.getCapabilities && me.track.getCapabilities()) || {}; } catch (e) { caps = {}; }
    const btn = screen.el.querySelector('[data-act="torch"]');
    btn.hidden = !caps.torch;
    btn.setAttribute('aria-pressed', 'false');
  }

  async function torch() {
    const me = run;
    if (!me || !me.track) return;
    const btn = screen.el.querySelector('[data-act="torch"]');
    const on = btn.getAttribute('aria-pressed') !== 'true';
    try {
      await me.track.applyConstraints({ advanced: [{ torch: on }] });
      if (run === me) btn.setAttribute('aria-pressed', String(on));
    } catch (e) { btn.hidden = true; }
  }

  function stop() {
    if (!run) return;
    run.ended = true;
    cancelAnimationFrame(run.raf);
    if (run.stream) run.stream.getTracks().forEach(t => t.stop());
    const video = screen && screen.el.querySelector('video');
    if (video) video.srcObject = null;
    run = null;
  }

  // The camera is never left on behind another app; it comes back when Pantry does.
  document.addEventListener('visibilitychange', () => {
    if (!screen) return;
    if (document.visibilityState === 'hidden') stop();
    else if (!run) start();
  });
  window.addEventListener('pagehide', stop);

  P.view('scan', { render, leave() { stop(); screen = null; } });
})();

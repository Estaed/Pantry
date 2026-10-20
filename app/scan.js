/* Scan: a probe of the phone's built-in barcode reader (BarcodeDetector) with the rear camera. It shows the
   EAN-13 it read and how long the read took, so real packs can be tried before the scan feature is built
   (wave 2: his foods, catalogue, Open Food Facts, label form). Leaving the screen, or the app going to the
   background, stops every camera track.
   Gate hooks: data-test="scan-status" holds the status or the reason scanning cannot work; data-test="scan-code"
   holds the code read. */
(() => {
  const P = window.Pantry;
  const reads = [];       // this session's reads, newest first: { code, seconds }
  let screen = null;      // the scan screen's root while it is shown
  let run = null;         // the running camera: { stream, raf, t0, found, ended }

  P.css(`
    .cam {
      --cam: #0B0B0B; /* the camera area stays dark in both themes (design/screens.html, scanner) */
      position: relative; margin: 16px 20px 0; aspect-ratio: 4 / 3; overflow: hidden;
      border-radius: var(--r-card); background: var(--cam);
    }
    .cam video { display: block; width: 100%; height: 100%; object-fit: cover; }
    .cam i { position: absolute; width: 28px; height: 28px; border: 3px solid #EEEEEE; }
    .cam i:nth-of-type(1) { left: 14%; top: 22%; border-right: 0; border-bottom: 0; border-radius: 10px 0 0 0; }
    .cam i:nth-of-type(2) { right: 14%; top: 22%; border-left: 0; border-bottom: 0; border-radius: 0 10px 0 0; }
    .cam i:nth-of-type(3) { left: 14%; bottom: 22%; border-right: 0; border-top: 0; border-radius: 0 0 0 10px; }
    .cam i:nth-of-type(4) { right: 14%; bottom: 22%; border-left: 0; border-top: 0; border-radius: 0 0 10px 0; }
    .scan-status.note { margin: 12px 20px 0; }
    .read { margin: 20px 20px 0; }
    .read .code { margin: 4px 0 0; font-size: 2rem; line-height: 1.1; letter-spacing: -0.01em; color: var(--primary-display); overflow-wrap: anywhere; }
    .read .note { margin-top: 4px; }
  `);

  // EAN-13 check digit: a misread that slips past the reader fails here and is not shown.
  function validEan13(code) {
    if (!/^\d{13}$/.test(code)) return false;
    const d = [...code].map(Number);
    const sum = d.slice(0, 12).reduce((s, v, i) => s + v * (i % 2 ? 3 : 1), 0);
    return (10 - (sum % 10)) % 10 === d[12];
  }
  const grouped = code => `${code[0]} ${code.slice(1, 7)} ${code.slice(7)}`;   // as printed under the bars

  function cameraProblem(e) {
    const name = e && e.name;
    if (name === 'NotAllowedError' || name === 'SecurityError') return 'Camera access is blocked for Pantry. Allow the camera in Chrome\'s site settings, then open Scan again.';
    if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'No camera was found on this phone.';
    if (name === 'NotReadableError') return 'The camera is in use by another app. Close it, then open Scan again.';
    return `The camera did not start (${name || 'unknown error'}).`;
  }

  function render(el) {
    screen = el;
    el.innerHTML = `
      <header class="top back"><button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>
        <div><p class="eyebrow">EAN-13 barcode</p><h1 class="title">Scan</h1></div></header>
      <div class="cam"><video playsinline muted aria-label="Camera"></video><i></i><i></i><i></i><i></i></div>
      <div class="scan-status note" role="status" data-test="scan-status">Starting the camera.</div>
      <div class="read" hidden><p class="eyebrow">Read</p><p class="code disp" data-test="scan-code"></p><p class="note took"></p></div>
      <section class="sec history" hidden><h2 class="eyebrow">Read this session</h2><ul class="rows"></ul></section>
      <div class="bottom"><button class="btn" type="button" data-act="again" hidden>${P.icon('scan')}Scan another</button></div>`;
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    el.querySelector('[data-act="again"]').addEventListener('click', again);
    showHistory();
    start();
  }

  function say(text, bad) {
    const box = screen.querySelector('[data-test="scan-status"]');
    box.className = bad ? 'scan-status banner' : 'scan-status note';
    box.setAttribute('role', bad ? 'alert' : 'status');
    box.innerHTML = bad ? `${P.icon('alert')}<div>${P.esc(text)}</div>` : P.esc(text);
    if (bad) screen.querySelector('.cam').hidden = true;
  }

  async function start() {
    const me = run = { stream: null, raf: 0, t0: 0, found: false, ended: false };
    if (typeof window.BarcodeDetector !== 'function') {
      return say('This browser has no built-in barcode reader: BarcodeDetector is missing, so Pantry cannot scan here. Scanning needs the fallback reader.', true);
    }
    let formats = null;
    try { formats = await window.BarcodeDetector.getSupportedFormats(); } catch (e) { formats = null; }
    if (me.ended) return;
    if (!Array.isArray(formats) || !formats.includes('ean_13')) {
      const known = Array.isArray(formats) && formats.length ? ` It reads ${formats.join(', ')}.` : '';
      return say(`This phone's barcode reader cannot read EAN-13, the barcode on food packs.${known} Scanning needs the fallback reader.`, true);
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return say('The camera only opens when Pantry runs from its https address.', true);
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
    const video = screen.querySelector('video');
    video.srcObject = stream;
    try { await video.play(); } catch (e) { /* muted inline video plays without a gesture; frames arrive anyway */ }
    if (me.ended) return;
    let detector;
    try { detector = new window.BarcodeDetector({ formats: ['ean_13'] }); } catch (e) {
      return say(`The barcode reader did not start (${e.name || e.message}). Scanning needs the fallback reader.`, true);
    }
    me.detector = detector;
    look(me);
  }

  function look(me) {
    me.found = false;
    me.t0 = performance.now();
    say('Point the camera at the barcode.');
    const video = screen.querySelector('video');
    const tick = async () => {
      if (me.ended || me.found) return;
      if (video.readyState >= 2) {
        let codes = [];
        try { codes = await me.detector.detect(video); } catch (e) { codes = []; }   // a frame it could not take
        if (me.ended) return;
        const hit = codes.find(c => c.format === 'ean_13' && validEan13(c.rawValue));
        if (hit) return found(me, hit.rawValue);
      }
      me.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  function found(me, code) {
    me.found = true;
    const seconds = (performance.now() - me.t0) / 1000;
    reads.unshift({ code, seconds });
    reads.length = Math.min(reads.length, 10);
    if (navigator.vibrate) navigator.vibrate(40);
    say('Check it against the digits under the bars.');
    const read = screen.querySelector('.read');
    read.querySelector('.code').textContent = grouped(code);
    read.querySelector('.took').textContent = `Read in ${seconds.toFixed(1)} s`;
    read.hidden = false;
    screen.querySelector('[data-act="again"]').hidden = false;
    showHistory();
  }

  function again() {
    if (!run || run.ended || !run.detector) return;
    screen.querySelector('.read').hidden = true;
    screen.querySelector('[data-act="again"]').hidden = true;
    look(run);
  }

  function showHistory() {
    const box = screen.querySelector('.history');
    box.hidden = reads.length < 2;
    box.querySelector('.rows').innerHTML = reads.map(r => `<li class="fr"><span class="t"><span class="name">${grouped(r.code)}</span></span>`
      + `<span class="k">${r.seconds.toFixed(1)} s</span></li>`).join('');
  }

  function stop() {
    if (!run) return;
    run.ended = true;
    cancelAnimationFrame(run.raf);
    if (run.stream) run.stream.getTracks().forEach(t => t.stop());
    const video = screen && screen.querySelector('video');
    if (video) video.srcObject = null;
    run = null;
  }

  // The camera is never left on behind another app; it comes back when Pantry does.
  document.addEventListener('visibilitychange', () => {
    if (!screen) return;
    if (document.visibilityState === 'hidden') stop();
    else if (!run) { screen.querySelector('.cam').hidden = false; start(); }
  });
  window.addEventListener('pagehide', stop);

  P.view('scan', { render, leave() { stop(); screen = null; } });
})();

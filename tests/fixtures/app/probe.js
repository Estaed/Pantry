/* A throwaway feature for the gate: tests/acceptance.py serves it as app/zz-probe.js and appends its line to
   app/registry.js, to prove a feature listed there is loaded online and offline with no other edit. */
(() => {
  const P = window.Pantry;
  P.view('probe', {
    render(el) { el.innerHTML = '<header class="top"><div><p class="eyebrow">Gate</p><h1 class="title" data-test="probe">Probe feature loaded</h1></div></header>'; },
  });
})();

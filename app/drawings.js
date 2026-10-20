/* Pantry food drawings (style C, design/DESIGN.md): flat shapes in the food's own colours, 48 x 48.
   PantryDrawing(food) returns inline SVG for a food, chosen by words in its name; foods with no match get
   the generic pack. Colour lives only inside these drawings; the screen around them stays grey + orange.
   Geometry is the one in design/screens.html. Add a drawing by adding an entry to DRAW and its words to WORDS. */
(() => {
  'use strict';
  // [kind, path, colour]: 'f' fills, 'l' strokes.
  const DRAW = {
    chicken: [['f', 'M9 31c-2-8 5-17 16-18 8-1 14 3 14 9 0 8-9 14-19 15-6 0-10-2-11-6z', '#F2B2A2'], ['l', 'M15 28c5-4 11-6 18-6M17 33c4-2 9-3 13-3', '#D98875']],
    grilled: [['f', 'M9 31c-2-8 5-17 16-18 8-1 14 3 14 9 0 8-9 14-19 15-6 0-10-2-11-6z', '#C98A55'], ['l', 'M14 30l16-12M18 34l16-12', '#7A4A26']],
    dip: [['f', 'M6 25h36c0 9-8 15-18 15S6 34 6 25z', '#4F86B8'], ['f', 'M9 25c2-6 8-9 15-9s13 3 15 9z', '#F4F1E8'], ['f', 'M17 20.5a1.6 1.6 0 1 0 0.1 0zM25 18.5a1.6 1.6 0 1 0 0.1 0zM31 21a1.6 1.6 0 1 0 0.1 0z', '#6E9E4A']],
    rice: [['f', 'M6 26h36c0 8-8 14-18 14S6 34 6 26z', '#B9B2A6'], ['f', 'M9 26c1-8 7-12 15-12s14 4 15 12z', '#FBF8F0'], ['l', 'M16 21l3-1M23 18h3M29 21l3 1M20 24h3', '#D8CFBA']],
    butter: [['f', 'M5 34h38l-4 5H9z', '#CFCFCF'], ['f', 'M11 21l19-5 8 6v10l-19 5-8-6z', '#F5D664'], ['l', 'M11 21l8 6 19-5M19 27v10', '#D9B43C']],
    potato: [['f', 'M7 27c0-8 8-14 18-14s16 5 16 12-8 12-18 12S7 34 7 27z', '#D6A468'], ['f', 'M16 23.5a1.4 1.4 0 1 0 0.1 0zM28 21a1.4 1.4 0 1 0 0.1 0zM31 30a1.4 1.4 0 1 0 0.1 0zM20 31a1.2 1.2 0 1 0 0.1 0z', '#8A5A2B']],
    pizza: [['f', 'M11 19c8-4 18-4 26 0L24 42z', '#F2C65A'], ['f', 'M8 14c10-5 22-5 32 0l-3 5c-8-4-18-4-26 0z', '#D49A4C'], ['f', 'M20 22.5a2.6 2.6 0 1 0 0.1 0zM28.5 22a2.4 2.4 0 1 0 0.1 0zM24 29.5a2.4 2.4 0 1 0 0.1 0z', '#C84A31']],
    tin: [['f', 'M9 22v12c0 3 7 5 15 5s15-2 15-5V22', '#B6BCC2'], ['f', 'M9 27c0 3 7 5 15 5s15-2 15-5v5c0 3-7 5-15 5S9 35 9 32z', '#2F6DB5'], ['f', 'M9 22c0-3 7-5 15-5s15 2 15 5-7 5-15 5-15-2-15-5z', '#DDE2E6']],
    eggs: [['f', 'M17 40c-6 0-9-5-9-11s4-15 9-15 9 9 9 15-3 11-9 11z', '#F1E2CD'], ['f', 'M31 40c-5 0-8-4-8-9s4-12 8-12 8 7 8 12-3 9-8 9z', '#E3C9A6']],
    sandwich: [['f', 'M7 34L24 11l17 23z', '#E8C38A'], ['f', 'M10 30h28l-2 4H12z', '#8B4A3A'], ['f', 'M9 28h30l-1 2H10z', '#7FAE52']],
    bread: [['f', 'M8 22c0-6 7-9 16-9s16 3 16 9c0 2-2 3-3 3v12H11V25c-1 0-3-1-3-3z', '#C98B4A'], ['f', 'M17 19a1.2 1.2 0 1 0 0.1 0zM24 17a1.2 1.2 0 1 0 0.1 0zM30 20a1.2 1.2 0 1 0 0.1 0zM21 23a1.2 1.2 0 1 0 0.1 0zM28 24a1.2 1.2 0 1 0 0.1 0z', '#5C3D22']],
    plate: [['f', 'M24 6a18 18 0 1 0 0.1 0z', '#E6E6E6'], ['f', 'M24 12a12 12 0 1 0 0.1 0z', '#F4F4F4'], ['l', 'M4 10v9M7 10v9M4 19c0 2 1.5 3 1.5 3v18M44 10c-3 1-4 5-4 10h3v20', '#9E9E9E']],
    pack: [['f', 'M8 16l16-7 16 7v18l-16 7-16-7z', '#D9C3A0'], ['f', 'M8 16l16 7 16-7-16-7z', '#EAD9BD'], ['l', 'M24 23v18', '#B89B6E']],
  };

  // First match wins, so the more specific words come first.
  const WORDS = [
    ['grilled', /grilled|roast chicken|royale/],
    ['chicken', /chicken/],
    ['dip', /tzatziki|dip|hummus|yoghurt|yogurt/],
    ['rice', /rice/],
    ['butter', /butter|margarine/],
    ['potato', /potato|chips|fries/],
    ['pizza', /pizza/],
    ['tin', /tuna|salmon|tin|can\b/],
    ['eggs', /egg/],
    ['sandwich', /sandwich|burger|whopper|wrap/],
    ['bread', /bread|loaf|toast|croissant/],
  ];

  function kind(food) {
    const name = `${(food && food.name) || ''} ${(food && food.brand) || ''}`.toLowerCase();
    const hit = WORDS.find(([, re]) => re.test(name));
    return hit ? hit[0] : 'pack';
  }

  function svg(key, size) {
    const shapes = DRAW[key] || DRAW.pack;
    const body = shapes.map(([t, d, c]) => t === 'l'
      ? `<path d="${d}" fill="none" stroke="${c}" stroke-width="1.75" stroke-linecap="round"/>`
      : `<path d="${d}" fill="${c}"/>`).join('');
    return `<svg class="drawing" viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">${body}</svg>`;
  }

  // window.Pantry is frozen, so the drawings are their own global:
  // PantryDrawing(food, size = 32) for a food; PantryDrawing.named('plate', size) for a fixed one.
  const draw = (food, size = 32) => svg(kind(food), size);
  draw.named = (key, size = 32) => svg(key, size);
  draw.kind = kind;
  window.PantryDrawing = Object.freeze(draw);
})();

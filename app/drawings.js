/* Pantry food drawings (style C, design/DESIGN.md): flat shapes in the food's own colours, 48 x 48.
   PantryDrawing(food) returns inline SVG for a food, chosen by words in its name and brand; foods with no
   match get the generic pack. Colour lives only inside these drawings; the screen around them stays grey +
   orange. Geometry is the one in design/screens.html. Add a drawing by adding an entry to DRAW and its words
   to WORDS; a word names the food itself, never a catch-all. */
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
    salad: [['f', 'M7 28c0-9 7-16 17-16s17 7 17 16c0 7-7 12-17 12S7 35 7 28z', '#8DBF5A'], ['f', 'M12 27c0-6 5-11 12-11s12 5 12 11c0 5-5 9-12 9s-12-4-12-9z', '#CFE6A4'], ['l', 'M24 16v20M24 25c-4-1-7-4-8-7M24 25c4-1 7-4 8-7M24 32c-4-1-7-3-9-6M24 32c4-1 7-3 9-6', '#6E9E4A']],
    banana: [['f', 'M8 13c-1 14 9 25 23 25 4 0 7-1 9-3-1-2-3-2-5-2-11 0-19-8-22-19-1-2-3-3-5-1z', '#F5D35C'], ['f', 'M6.6 10.4l3.6-1.2 1.4 4-3.6 1.2z', '#7A5A2A'], ['l', 'M12 18c2 8 9 15 19 16', '#D9AE33'], ['f', 'M38.5 33.4a1.8 1.8 0 1 0 0.1 0z', '#7A5A2A']],
    pasta: [['f', 'M22.8 42.6L40.8 28.6A4.6 2.5 52.1 0 0 35.2 21.4L17.2 35.4A4.6 2.5 52.1 0 0 22.8 42.6z', '#E9C066'], ['f', 'M40.8 28.6A4.6 2.5 52.1 1 0 35.2 21.4A4.6 2.5 52.1 1 0 40.8 28.6z', '#D9AA4A'], ['f', 'M39.6 27A2.5 1.4 52.1 1 0 36.4 23A2.5 1.4 52.1 1 0 39.6 27z', '#A87A26'], ['l', 'M19.9 36.4L34.8 24.9M22.5 39.7L37.3 28.2', '#C99A3C'], ['f', 'M11.3 34.3L28.3 17.3A4.6 2.5 45 0 0 21.7 10.7L4.7 27.7A4.6 2.5 45 0 0 11.3 34.3z', '#F2CF7A'], ['f', 'M28.3 17.3A4.6 2.5 45 1 0 21.7 10.7A4.6 2.5 45 1 0 28.3 17.3z', '#D9AA4A'], ['f', 'M26.8 15.8A2.5 1.4 45 1 0 23.2 12.2A2.5 1.4 45 1 0 26.8 15.8z', '#A87A26'], ['l', 'M7.6 28.5L21.8 14.3M10.5 31.4L24.7 17.2', '#C99A3C']],
    milk: [['f', 'M14 19h20v21H14z', '#E6EDF3'], ['f', 'M14 19l4-8h12l4 8z', '#DDE3E9'], ['f', 'M18 7h12v4H18z', '#C9D1D9'], ['f', 'M14 27h20v7H14z', '#4F86B8'], ['l', 'M24 11l-2 8', '#B9C3CC']],
    powder: [['f', 'M12 18h24v19c0 2-2 4-4 4H16c-2 0-4-2-4-4z', '#7A8DA3'], ['f', 'M11 12h26v6H11z', '#4A586A'], ['f', 'M12 23h24v10H12z', '#F4F1E8'], ['l', 'M18 28h12', '#C84A31']],
    pills: [['f', 'M13.5 29.5l14-14a5 5 0 0 0-7-7l-14 14a5 5 0 0 0 7 7z', '#F1E2CD'], ['f', 'M20.5 22.5l7-7a5 5 0 0 0-7-7l-7 7z', '#E4A23C'], ['f', 'M33 22a8 8 0 1 0 0.1 0z', '#DCD8CE'], ['l', 'M27.5 35.5l11-11', '#A9A496']],
    cereal: [['f', 'M6 26h36c0 8-8 14-18 14S6 34 6 26z', '#9FB3C8'], ['f', 'M9 26c1-4 7-7 15-7s14 3 15 7z', '#FBF8F0'], ['f', 'M13 22l5-4 5 2-2 5zM24 18l6-1 2 5-6 2zM31 23l4-3 4 3-4 3zM19 25l4-1 2 2h-6z', '#E5A93F'], ['l', 'M15 21.5l4.5-1.5M26 19.5l3.5 1M32.5 23l3 1', '#B97E25']],
    cheese: [['f', 'M6 26h36v12H6z', '#F2C94C'], ['f', 'M6 26l26-13 10 13z', '#F7DD7A'], ['f', 'M14 32a2.2 2.2 0 1 0 0.1 0zM26 30a2.8 2.8 0 1 0 0.1 0zM36 34a1.7 1.7 0 1 0 0.1 0zM27 20.5a1.6 1.6 0 1 0 0.1 0z', '#D9A92E']],
    steak: [['f', 'M7 27c0-9 8-15 18-15s17 5 17 13-7 13-18 13S7 34 7 27z', '#F3E1CF'], ['f', 'M10 27c0-7 7-12 15-12s14 4 14 10-6 11-15 11-14-3-14-9z', '#B5493C'], ['l', 'M16 24c3-2 7-2 10 0M19 30c3 1 7 1 10-1M28 20c2 0 4 1 5 3', '#DE8E7E']],
    wrap: [['f', 'M8 30L25 13l12 12L20 42c-4 3-15-8-12-12z', '#E8C98E'], ['f', 'M31 11a8.5 8.5 0 1 0 0.1 0z', '#F3DDAE'], ['f', 'M31 13.5a6 6 0 1 0 0.1 0z', '#7FAE52'], ['f', 'M29 18a2 2 0 1 0 0.1 0zM34 21a1.8 1.8 0 1 0 0.1 0z', '#C84A31'], ['f', 'M14 33a1.3 1.3 0 1 0 0.1 0zM19 30a1.1 1.1 0 1 0 0.1 0zM21 36a1.2 1.2 0 1 0 0.1 0z', '#C9964F']],
    plate: [['f', 'M24 6a18 18 0 1 0 0.1 0z', '#E6E6E6'], ['f', 'M24 12a12 12 0 1 0 0.1 0z', '#F4F4F4'], ['l', 'M4 10v9M7 10v9M4 19c0 2 1.5 3 1.5 3v18M44 10c-3 1-4 5-4 10h3v20', '#9E9E9E']],
    pack: [['f', 'M8 16l16-7 16 7v18l-16 7-16-7z', '#D9C3A0'], ['f', 'M8 16l16 7 16-7-16-7z', '#EAD9BD'], ['l', 'M24 23v18', '#B89B6E']],
  };

  // First match wins: a dish comes before what it is made of ("Chicken Sandwich" is a sandwich, "Meat Beef
  // Sandwich Steak" a steak, "Tuna Sandwich Style" a tin), a supplement before any food word.
  const WORDS = [
    ['pills', /magnesium|glycinate|\btablets?\b|capsule|multivitamin|fish oil/],
    ['powder', /\bwhey\b|creatine|protein powder|casein/],
    ['milk', /\bmilk\b/],
    ['cereal', /corn ?flakes|cereal|muesli|granola|porridge|\boats\b|weet-?bix|bran flakes/],
    ['steak', /steak|scotch fillet|porterhouse|\brump\b|sirloin|t-bone/],
    ['pizza', /pizza/],
    ['grilled', /grilled|roast chicken|royale/],
    ['wrap', /\bwraps?\b|tortilla|souvlaki|kebab|burrito/],
    ['sandwich', /sandwich(?!\w* style)|burger|whopper|big ?mac/],
    ['chicken', /chicken/],
    ['dip', /tzatziki|\bdip\b|hummus|yoghurt|yogurt/],
    ['pasta', /penne|pasta|spaghetti|fusilli|macaroni|rigatoni|lasagne/],
    ['rice', /\brice\b/],
    ['butter', /\bbutter\b|margarine/],
    ['potato', /potato|chips|fries/],
    ['tin', /tuna|salmon|\btin\b|can\b/],
    ['eggs', /\beggs?\b/],
    ['bread', /\bbread\b|loaf|toast|croissant|sourdough/],
    ['cheese', /\bcheese\b|mozzarella|cheddar|parmesan|feta|halloumi/],
    ['salad', /iceberg|lettuce|salad|coleslaw/],
    ['banana', /banana/],
  ];

  function kind(food) {
    const name = `${(food && food.name) || ''} ${(food && food.brand) || ''}`.toLowerCase();
    const hit = WORDS.find(([, re]) => re.test(name));
    return hit ? hit[0] : 'pack';
  }

  function shapes(key) {
    return (DRAW[key] || DRAW.pack).map(([t, d, c]) => t === 'l'
      ? `<path d="${d}" fill="none" stroke="${c}" stroke-width="1.75" stroke-linecap="round"/>`
      : `<path d="${d}" fill="${c}"/>`).join('');
  }

  function svg(key, size) {
    return `<svg class="drawing" viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">${shapes(key)}</svg>`;
  }

  // Several foods in one drawing (a toast after logging a meal): the first two or three on grey discs that overlap,
  // left to right and then below, each disc ringed in the surface it stands on so the overlap reads. [x, y, disc]
  const SPOTS = { 2: [[0, 3, 30], [18, 15, 30]], 3: [[0, 2, 27], [21, 2, 27], [10.5, 20, 27]] };
  function group(foods, size) {
    const list = [...(foods || [])].slice(0, 3);
    if (list.length < 2) return svg(kind(list[0]), size);
    const body = list.map((food, i) => {
      const [x, y, d] = SPOTS[list.length][i], r = d / 2, art = d * 0.8, inset = (d - art) / 2;
      return `<circle cx="${x + r}" cy="${y + r}" r="${r - 0.75}" style="fill:var(--surface-2);stroke:var(--surface-3);stroke-width:1.5"/>`
        + `<svg x="${x + inset}" y="${y + inset}" width="${art}" height="${art}" viewBox="0 0 48 48">${shapes(kind(food))}</svg>`;
    }).join('');
    return `<svg class="drawing" viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">${body}</svg>`;
  }

  // window.Pantry is frozen, so the drawings are their own global:
  // PantryDrawing(food, size = 32) for a food; PantryDrawing.named('plate', size) for a fixed one;
  // PantryDrawing.group(foods, size) for several at once; PantryDrawing.kind(food) the key a food gets;
  // PantryDrawing.keys every key.
  const draw = (food, size = 32) => svg(kind(food), size);
  draw.named = (key, size = 32) => svg(key, size);
  draw.group = (foods, size = 32) => group(foods, size);
  draw.kind = kind;
  draw.keys = Object.freeze(Object.keys(DRAW));
  window.PantryDrawing = Object.freeze(draw);
})();

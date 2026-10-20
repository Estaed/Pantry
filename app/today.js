/* Today: kcal left of the day's budget and what was eaten today. The thin Task-00 version; the full Today
   (day strip, meal corners, ring, macro strip) replaces it in wave 2.
   Gate hook: the element with data-test="kcal-left" holds the number of kcal left (or over). */
(() => {
  const P = window.Pantry;
  const MEAL = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snacks: 'Snacks' };

  P.css(`
    .answer { margin: 40px 20px 8px; text-align: center; }
    .answer .left { margin: 0; font-size: 3rem; line-height: 1; letter-spacing: -0.03em; color: var(--primary-display); }
    .answer .lbl { margin: 6px 0 0; font: 600 0.75rem/1.3 var(--font-sans); color: var(--ink-muted); }
    .answer .tot { margin: 6px 0 0; font: 600 0.75rem/1.3 var(--font-figure); color: var(--ink-subtle); }
    .answer .tot b { color: var(--ink); font-weight: 700; }
  `);

  let root = null;

  function render(el) {
    root = el;
    const doc = P.doc();
    const date = P.today();
    const foods = new Map(doc.foods.map(f => [f.id, f]));
    const entries = doc.entries.filter(e => e.date === date).reverse();
    const budget = doc.settings.targets.kcal;
    const eaten = Math.round(P.sum(entries).kcal || 0);
    const left = Math.round(budget - eaten);
    const problem = P.problem();

    const rows = entries.map(e => {
      const food = foods.get(e.foodId);
      return `<li class="fr"><span class="t"><span class="name">${P.esc(food ? food.name : 'A food no longer in your list')}</span>`
        + `<span class="sub">${MEAL[e.meal]}, ${P.esc(e.amount)}</span></span><span class="k">${P.fmt(e.totals.kcal)}</span></li>`;
    }).join('');

    el.innerHTML = `
      <header class="top"><div><p class="eyebrow">${P.dayLabel(date)}</p><h1 class="title">Today</h1></div></header>
      ${problem ? `<div class="banner" role="alert">${P.icon('alert')}<div>${P.esc(problem)}</div></div>` : ''}
      <section class="answer" aria-label="Calories today">
        <p class="left disp" data-test="kcal-left">${P.fmt(Math.abs(left))}</p>
        <p class="lbl">${left < 0 ? 'kcal over' : 'kcal left'}</p>
        <p class="tot"><b>${P.fmt(eaten)}</b> / ${P.fmt(budget)}</p>
      </section>
      <section class="sec">
        <h2 class="eyebrow">Eaten today</h2>
        ${rows ? `<ul class="rows">${rows}</ul>` : `<p class="note">Nothing logged yet today. Add a food and kcal left counts down from ${P.fmt(budget)}.</p>`}
      </section>
      <div class="bottom">
        <button class="btn" type="button" data-act="add">${P.icon('plus')}Add food</button>
        <button class="ibtn box" type="button" data-act="scan" aria-label="Scan a barcode">${P.icon('scan')}</button>
      </div>`;
    el.querySelector('[data-act="add"]').addEventListener('click', () => P.go('add'));
    el.querySelector('[data-act="scan"]').addEventListener('click', () => P.go('scan'));
  }

  P.view('today', { render, update() { if (root) render(root); } });
})();

/* Log: the food list ('#/add') and the gram step ('#/add/<foodId>'), which saves one entry with its nutrient
   totals fixed at log time. The thin Task-00 version; the meal list and gram sheet replace it in wave 2.
   Foods logged only by servings (no per100) wait for that wave and are not listed here. */
(() => {
  const P = window.Pantry;
  const MEALS = [['breakfast', 'Breakfast'], ['lunch', 'Lunch'], ['dinner', 'Dinner'], ['snacks', 'Snacks']];
  const mealNow = () => { const h = new Date().getHours(); return h < 11 ? 'breakfast' : h < 16 ? 'lunch' : h < 21 ? 'dinner' : 'snacks'; };

  P.css(`
    .fr .add { width: 40px; height: 40px; flex: none; display: grid; place-items: center; border-radius: 50%; border: 1.5px solid var(--hairline-strong); }
    .fr .add svg.i { width: 18px; height: 18px; }
    .gram { display: flex; flex-direction: column; flex: 1; }
    .gram .per { margin: 6px 20px 0; font: 500 0.8125rem/1.4 var(--font-sans); color: var(--ink-muted); }
    .amt { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; margin: 28px 20px 0; }
    .amt label { display: flex; align-items: baseline; gap: 4px; }
    .amt input {
      width: 4.6ch; padding: 0 2px 2px; border: 0; border-bottom: 2px solid var(--primary); border-radius: 0; background: none;
      font-size: 2.75rem; line-height: 1.1; letter-spacing: -0.02em; text-align: right; color: var(--ink);
    }
    @supports (field-sizing: content) { .amt input { width: auto; min-width: 2ch; field-sizing: content; } }
    .amt input:focus { outline: none; border-bottom-width: 3px; }
    .amt small { font: 600 0.9375rem var(--font-sans); color: var(--ink-muted); letter-spacing: 0; }
    .amt output { font-size: 1.75rem; line-height: 1.1; color: var(--ink-muted); white-space: nowrap; }
    .gram .err { display: flex; gap: 8px; align-items: center; margin: 10px 20px 0; font: 600 0.8125rem/1.4 var(--font-sans); color: var(--danger); }
    .gram .err svg.i { width: 16px; height: 16px; }
    .meals { margin: 28px 20px 0; padding: 0; border: 0; min-width: 0; }
    .meals legend { padding: 0; margin-bottom: 8px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { position: relative; }
    .chip input { position: absolute; opacity: 0; inset: 0; margin: 0; }
    .chip span {
      display: inline-flex; align-items: center; min-height: 44px; padding: 0 14px; border-radius: var(--r-chip);
      border: 1px solid var(--hairline-strong); font: 600 0.875rem/1.2 var(--font-sans); cursor: pointer;
    }
    .chip input:checked + span { background: var(--action); color: var(--on-action); border-color: var(--action); }
    .chip input:focus-visible + span { outline: 2px solid var(--primary); outline-offset: 2px; }
  `);

  function header(title, eyebrow) {
    return `<header class="top back"><button class="ibtn" type="button" data-act="back" aria-label="Back">${P.icon('back')}</button>`
      + `<div><p class="eyebrow">${P.esc(eyebrow)}</p><h1 class="title">${P.esc(title)}</h1></div></header>`;
  }

  // Grams of the last time this food was logged; before that, the starter food's usual amount.
  function usualGrams(doc, food) {
    for (let i = doc.entries.length - 1; i >= 0; i--) {
      const e = doc.entries[i];
      if (e.foodId === food.id && e.grams) return e.grams;
    }
    const starter = P.starter.find(s => s.food.id === food.id);
    return starter ? starter.usual : 100;
  }

  function list(el) {
    const doc = P.doc();
    const count = new Map();
    for (const e of doc.entries) count.set(e.foodId, (count.get(e.foodId) || 0) + 1);
    const foods = doc.foods.filter(f => f.per100).sort((a, b) => (count.get(b.id) || 0) - (count.get(a.id) || 0));
    const rows = foods.map((f, i) => {
      const g = usualGrams(doc, f);
      const kcal = P.fmt(P.totals(f, g).kcal);
      const sub = `${f.brand ? f.brand + ', ' : ''}${g} g`;
      return `<li><button class="fr" type="button" data-i="${i}" aria-label="${P.esc(`${f.name}, ${sub}, ${kcal} kcal`)}">`
        + `<span class="t"><span class="name">${P.esc(f.name)}</span><span class="sub">${P.esc(sub)}</span></span>`
        + `<span class="k">${kcal}</span><span class="add" aria-hidden="true">${P.icon('plus')}</span></button></li>`;
    }).join('');
    el.innerHTML = `${header('Add food', P.dayLabel(P.today()))}
      <section class="sec">${rows ? `<ul class="rows">${rows}</ul>` : '<p class="note">No foods with values per 100 g yet.</p>'}</section>`;
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    el.querySelectorAll('[data-i]').forEach(b => b.addEventListener('click', () => P.go('add', foods[Number(b.dataset.i)].id)));
  }

  function newId(doc, date) {
    const taken = new Set(doc.entries.map(e => e.id));
    let id;
    do { id = `${date}-p${crypto.getRandomValues(new Uint32Array(1))[0].toString(36)}`; } while (taken.has(id));
    return id;
  }

  const readGrams = text => {
    const v = Number(String(text).trim().replace(',', '.'));
    return Number.isFinite(v) && v > 0 && v <= 10000 ? Math.round(v * 10) / 10 : null;
  };

  function gram(el, id) {
    const doc = P.doc();
    const food = doc.foods.find(f => f.id === id && f.per100);
    if (!food) {
      el.innerHTML = `${header('Add food', P.dayLabel(P.today()))}<p class="note sec">This food is not in your list.</p>`;
      el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
      return;
    }
    const meal = mealNow();
    el.innerHTML = `${header(food.name, P.dayLabel(P.today()))}
      <form class="gram" novalidate>
        <p class="per">${food.brand ? P.esc(food.brand) + ', ' : ''}${P.fmt(food.per100.kcal, 1)} kcal per 100 g</p>
        <div class="amt">
          <label><input class="disp" name="grams" inputmode="decimal" autocomplete="off" enterkeyhint="done" aria-label="Grams"
            value="${usualGrams(doc, food)}"><small>g</small></label>
          <output class="disp" aria-live="polite"><span data-test="portion-kcal"></span><small> kcal</small></output>
        </div>
        <p class="err" role="alert" hidden></p>
        <fieldset class="meals"><legend class="eyebrow">Meal</legend><div class="chips">
          ${MEALS.map(([k, label]) => `<label class="chip"><input type="radio" name="meal" value="${k}"${k === meal ? ' checked' : ''}><span>${label}</span></label>`).join('')}
        </div></fieldset>
        <div class="bottom"><button class="btn" type="submit"></button></div>
      </form>`;

    const form = el.querySelector('form');
    const input = form.elements.grams;
    const kcalOut = form.querySelector('[data-test="portion-kcal"]');
    const err = form.querySelector('.err');
    const submit = form.querySelector('[type="submit"]');
    const chosenMeal = () => form.elements.meal.value;
    const refresh = () => {
      const g = readGrams(input.value);
      kcalOut.textContent = g === null ? '–' : P.fmt(P.totals(food, g).kcal);
      submit.textContent = `Add to ${MEALS.find(m => m[0] === chosenMeal())[1].toLowerCase()}`;
    };
    const fail = text => { err.innerHTML = `${P.icon('alert')}<span>${P.esc(text)}</span>`; err.hidden = false; };

    input.addEventListener('focus', () => input.select());
    input.addEventListener('input', () => { err.hidden = true; refresh(); });
    form.addEventListener('change', refresh);
    el.querySelector('[data-act="back"]').addEventListener('click', () => P.back());
    form.addEventListener('submit', e => {
      e.preventDefault();
      const grams = readGrams(input.value);
      if (grams === null) { fail('Type the grams, for example 350.'); input.focus(); return; }
      try {
        P.change(d => {
          const date = P.today();
          d.entries.push({ id: newId(d, date), date, meal: chosenMeal(), foodId: food.id, amount: `${grams} g`, grams, totals: P.totals(food, grams) });
        });
      } catch (x) { fail(x.message); return; }
      P.home();
    });
    refresh();
  }

  P.view('add', { render(el, id) { if (id) gram(el, id); else list(el); } });
})();

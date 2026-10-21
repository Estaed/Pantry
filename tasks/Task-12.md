# Task-12: Today reads at a glance: whole ring, eaten by meal, red when over
> **Execution:** agent `ultracode`
> *Why:* after a day on the phone Tarık found the ring's empty slots confusing, the macro bars' colours meaningless, the eaten list hard to scan and edit, and the violet over tone not alarming enough.

**Lane**
- OWNS: `app/today.js`, `app/base.css`, `tests/test_today.py`
- MUST NOT TOUCH: `app/core.js`, `index.html`, `app/log.js`, `app/entry.js`, `app/settings.js`, `app/scan.js`, `app/newfood.js`, `app/drawings.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_today.py`)
- DEPENDS ON: none

## Goal
Tarık glances at Today on his Galaxy S24 (360 px, text 1.0, installed app in Samsung Internet) several times a day.

- **The ring keeps no slot for a meal not yet logged.** The track is one whole ring; each logged meal takes its
  room (its share of the budget) and the rest stays one continuous track, so the empty part reads as "left", not as
  meals. Tarık, 2026-10-21: "diğer öğünler eklenmediği sürece bar tam dursun, eklendiklerinde yer kaplasınlar".
  This replaces round 5's fixed quarters (design/DESIGN.md → Taste record, 2026-10-21). Over budget keeps working.
- **Over is red.** The over tone becomes the base `danger` token in place of `chart-5` violet, everywhere Task-09
  used it (Tarık picked C of four tones on the real 19 Oct screen, 2026-10-21). Within stays grey.
- **The macro bars mean something.** The three bars share one grey (with gaps, so they do not merge); how far each
  macro's share is from its target share is drawn on the screen, readable at a glance (not only in an attribute);
  red keeps its meaning: a macro turns the over tone only when its grams pass its daily target grams, as today, since
  shares always add up to 100 % and one is nearly always past its target share. Today carbs are black, protein grey
  and fat black, which says nothing, and fat at 48 % against a 35 % target shows no sign.
- **What he ate, by meal.** "Eaten today" becomes one page per meal (Breakfast, Lunch, Dinner, Snacks), each with
  its kcal; he swipes sideways between them and can tap a meal's name to jump; it opens on the meal he is most
  likely to look at (the builder decides and says why: the current meal, or the last one logged; on a past day the
  first meal with entries), and keeps the page he was on when he comes back from Edit entry or a delete. The floating
  + adds to the meal page shown. The meal pages swipe only inside the eaten section, so the strip scroll, the ring
  swipe, the toast swipe and the phone's edge-back gesture stay as they are. Each entry still opens Edit entry.
  Taking one out goes through `Pantry.removeEntry` (Undo included), is easy to find without instructions, never
  happens by accident and does not fight the sideways swipe. Tarık, 2026-10-21: "alttaki listeyi eaten today değil de breakfast lunch
  diye bölelim kaydırarak diğerlerine gidelim"; "lunch'a patates ekledim ama geri silemiyorum, buldum da zor buldum".
- **Nothing hides under the floating + and Scan:** the last row scrolls clear of them, and Scan floats like the +
  (today it is a flat grey tile pasted over the rows).
- **Small things:** no scrollbar line at the right edge of the page (seen on the phone); each meal's letter shows
  once: the corner badge stays, the ring's letter goes (arcs no longer face their corners, a small arc cannot hold
  one). Arcs sit end to end in meal order from the top, clockwise; logging lunch after dinner moves dinner's arc.

## Why
Today is the screen he opens most; each of these made him stop and think (or hunt) on his first day with the app.

## Acceptance
- [ ] With only breakfast logged, the ring shows one breakfast arc and one unbroken track for the rest (no gap or slot for lunch, dinner or snacks); with breakfast and dinner logged, two arcs and one track; arcs never overlap; over budget still fills the ring and turns it red.
- [ ] Every element Task-09 drew in the over tone now uses `--danger`; none uses `--chart-5`.
- [ ] The three macro bars share one grey; a macro whose grams pass its target grams is in the over tone and no other is; each bar's distance from its target share is drawn as a visible mark a test can locate (the builder names it).
- [ ] The eaten section has one page per meal with its kcal; a sideways swipe moves one meal; tapping a meal's name opens its page; an empty meal's page says so and offers Add for that meal; a row opens `entry <id>`.
- [ ] An entry can be removed from its meal page in at most two deliberate steps through `Pantry.removeEntry` (a `doc.removed` line; Undo restores it deep-equal and drops that line); a sideways swipe meant to change meal never removes anything; back from Edit entry, and after a delete, the same meal page shows.
- [ ] An empty meal page's Add is named "Add to <meal>" (never "Add food…" or "Scan a barcode": the gate finds those by substring); no placeholder is a `.fr` row.
- [ ] With the page scrolled to its end, no row's text or kcal lies under the + or Scan; Scan has the same elevation as the +.
- [ ] At 360 × 780, text 1.0, light and dark: no horizontal scroll, no console errors.
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: the ring's empty part reads as "left"; red and its light tints read as over at a glance; the macro bars show which macro is off; swiping between meals feels natural; taking a food out is obvious; no scrollbar line at the right edge.

`app/base.css` is shared with the meal list, New food and Settings: change it only for the page scrollbar; the
shared `.fr`, `.bottom` and `#toast` rules stay as they are (Today's own needs go in `app/today.js`).
Gate hooks: `tests/test_shell.py` check_scroll needs Today for 8 Aug (16 synthetic snacks) to scroll 400 px, and its
copy check compares screen copies element for element; if the meal pages change either, name the exact change
under seams_missing and the orchestrator moves those old-look steps at integration.

## Out of scope
- The meal list and gram sheet (Task-11), the theme setting (Task-13), the day strip's scrolling (done 2026-10-21).

Fixed: the gate hooks listed at the top of `tests/acceptance.py` (`data-test="kcal-left"`, "Add food", "Scan a barcode", rows `.fr` with `.name`/`.sub`).

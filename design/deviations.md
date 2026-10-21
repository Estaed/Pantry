# Deliberate breaks from Tarik Base v6

- **Food drawings carry natural colours** (base: one saturated hue). Tarık picked style C on
  2026-10-20: a food is recognised fastest by its colour. The colour stays inside the drawing;
  chrome, charts and text keep grey + one orange.
- **Budget status colour change** (base: one saturated hue). Tarık, 2026-10-21: over budget was hard to
  see; MyNetDiary's colour change was the example, in Pantry's own tones, not its literal green and red.
  Only within/over uses it; orange stays the action accent.
- **Looping wave in the day strip** (base: nothing loops except a loading skeleton). Tarık asked for
  a wave in each day's fill (2026-10-20). Kept slow and low, and stopped under reduced motion.
- **Edit an entry is its own screen in v1** (design *8* draws a sheet over the day). Routes replace the
  screen, so a sheet over Today would need Today to host it; the screen keeps the sheet's content and
  order. Revisit after v1 if the day behind it is missed.

## Departures from the prototype, wave 3 (2026-10-21; builders' proposals, Tarık keeps or drops)
- **Over tone is the base `chart-5` violet**: ring, corner swatches, kcal-left number, the day's tank and any
  macro bar past its target. The warm status tokens sit within ΔE 0.05–0.08 of the orange accent and would
  read as it. Today's own strip cell shows over too, and over wins over the shown day's orange fill.
- **Today**: a past day has a "Today" action left of the gear; tapping a strip day switches in place (the
  strip moves only when the shown day leaves it); the whole ring area takes the day swipe.
- **Meal list**: "In dinner: 2 foods, 1,422 kcal" under the title; a food's drawing is its tick (filled
  circle with a check when ticked); a grey check badge on a food already in that meal; a sticky "Add N to
  <meal>" bar with a clear button; the + turns into a check for the 4 s its toast shows; a "Same as
  yesterday's <meal>" row naming its foods.
- **Gram sheet**: chips without use counts, plus a "<grams> pack" chip when the food has a pack; the amount
  opens focused and selected, Enter logs.
- **Macro order carbs, protein, fat** on Today, the gram sheet, New food and Settings (Blueprint 2026-10-21).
- **Toasts**: Edit entry's Save shows "Saved, <amount>" with the food's drawing and Undo, as Delete does; a
  + names the food ("350 g of Chicken Breast Raw added to dinner"), several foods get a combined drawing.
- **Settings data row**: "Days logged / MyNetDiary (+ Pantry only) / <range> / 464 (+2)".
- **Today's Add is a floating + at the bottom right** (base: a full-width primary button in the thumb zone), Scan
  beside it, as in MyNetDiary (Tarık, 2026-10-21: "mynetdiarydeki gibi sağda +"). A 56 px ink square with the
  floating shadow; its name stays "Add food to <meal>".
- **The day strip follows the finger** with the weeks before and after at its sides, and glides on a week when
  let go past 40 px (Tarık, 2026-10-21: the strip had no "akıcılık").
- **Screen motion** follows Tarik Base v6 → Motion (push in from the right, back reverses, Today crossfades);
  the prototype is static.

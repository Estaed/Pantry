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
- **Over tone** (wave 3 had `chart-5` violet; superseded in wave 4, below): ring, corner swatches, kcal-left
  number, the day's tank and any macro bar past its target. Today's own strip cell shows over too, and over wins
  over the shown day's orange fill.
- **Today**: a past day has a "Today" action left of the gear; tapping a strip day switches in place (the
  strip moves only when the shown day leaves it); the whole ring area takes the day swipe.
- **Meal list**: "In dinner: 2 foods, 1,422 kcal" under the title; a food's drawing is its tick (filled
  circle with a check when ticked; replaced in wave 4 by a long press); a grey check badge on a food already in that meal; a sticky "Add N to
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
- **The day strip scrolls freely, day by day** (the prototype shows one fixed week): the browser's own sideways
  scroll with a snap on each day, about three months loaded and more as he reaches the start (Tarık, 2026-10-21:
  "mynetdiarydeki gibi ... gün gün akıcı bir şekilde kaydırmak istiyorum").
- **Screen motion** follows Tarik Base v6 → Motion (push in from the right, back reverses, Today crossfades);
  the prototype is static.

## Departures from the prototype, wave 4 (2026-10-21; from Tarık's first day on the phone)
- **Over is the base `danger` red** (Tarık picked C of four tones on the real 19 Oct screen). Past the budget the
  ring runs on as a second lap from 12 o'clock, as in MyNetDiary: the first lap and the badges go to light
  tints of the red (badge letters in ink), the second lap carries the strong red, deeper the more he is over
  (75 % of `danger` just over, full from 25 % over); the kcal number stays full `danger` for contrast.
- **Ring is one arc for the day** (design: a quarter per meal), as in MyNetDiary: eaten / budget from 12 o'clock in
  ink, the rest one track; over, a closed first lap in the light over tint under the second lap. Corner badges dark
  when the meal has entries, light when empty; no letters on the ring.
- **Macro strip**: one grey for the three bars; red only past target grams (a deviation mark under each bar was
  tried and removed the same day: "gereksiz gibi").
- **Eaten by meal**: a tab per meal (name over kcal) over one page per meal in a sideways snap pager; a trash at
  each row's end, then Delete (red outline) with Undo; an empty meal says so and offers "Add to <meal>". The +
  and Scan add to the meal shown; Scan floats like the +. The pages are as tall as the longest meal, so a swipe
  never changes height under the thumb. No page scrollbar on any screen.
- **Meal list opens on the meal**: a first tab named after it ("Lunch") listing its entries with a − then
  "Remove" (ink pill) on each; Frequent opens when the meal is empty. A tap on a food opens its gram sheet and
  never ticks or logs; only + logs; ticking several starts with a long press. "Same as yesterday's <meal>" sits on
  Frequent and only its + copies. The list keeps its tab in history.
- **Gram sheet opens without the keyboard**: a tap on the amount focuses and selects it (it seemed tied to Samsung
  Internet's dead back key); a quick second tap on the rising sheet is held for 350 ms.
- **Settings has a Theme group of four choices, second** (design *9* has a "Follow phone theme" toggle as the
  Data list's last row): Dynamic (dark from Darwin's sunset to sunrise), Light, Dark and System in one segmented
  control, two by two where four do not fit, with a line saying what the pick does; after Targets so it shows
  without scrolling (Tarık, 2026-10-21: "ayarlara ekle dinamik, açık, kapalı, sistem").

## Departures from the prototype, after wave 4 (2026-10-23; Tarık)
- **No first-launch screen** (design: the empty plate with "Import MyNetDiary history"): the app opens straight
  on Today at 0 eaten; the history comes in through sync in Settings, whose empty "Days logged" row says so
  (Tarık: "en basta direkt 0 acsin").
- **The day strip runs two days past today** (design: it ends at the shown day): tomorrow and the day after show
  empty with no difference label, open from a tap or a ring swipe, and take entries like any day (Tarık: "bazen
  ben yarin ne yiyecegimi de koyuyorum").

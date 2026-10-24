# Pantry design layer

Overrides on Tarik Base v6 (`D:/TarikOS/.brain/skills/tasarim/references/DESIGN.md`); everything
not named here follows the base.

- **Illustration tier: `spot`.** Every food in a list or sheet carries a small drawing (Tarık,
  2026-10-20: "illüstrasyondan kaçınma", "yazıdan çok görsellik"). Drawings are inline SVG, one
  geometry per food, so the app stays light and offline. Style **C, flat natural colours** (Tarık, 2026-10-20, over A thin line and B flat greys):
  the food keeps its own colours inside its drawing; the screen around it stays grey and orange
  (`deviations.md`).
- **Layout direction: open.** Tarık on v2 (2026-10-20): "blok blok değil, daha harmony içinde",
  "benzer ama biraz daha özgür". Six whole directions in `design/yonler.html` (D1 Akış, D2 Tabak,
  D3 Şerit, D4 Katman, D5 Izgara, D6 Gösterge); he picks parts.
- **Text size target: 1.0** (base: support 200 % without clipping). Tarık, 2026-10-21: "yazı boyutu
  1.0 olsun 2 gereksiz". Text stays in rem, so a larger phone setting still scales, but layouts are
  judged at 1.0 only.
- **Budget status colour change** (base: one saturated hue). The screen changes colour when the day goes
  over budget (ring, kcal-left number, macro bars, day strip), as MyNetDiary does, but in this design
  language, not its literal green and red (Tarık, 2026-10-21: "bize bir renk daha lazım", then "tasarıma
  uygun bir şey yapsın, direkt birebir yeşil kırmızı olmasın, o renk değişiminden bahsettim"). Within
  reads calm, over is unmistakable; tones come from the base tokens. Orange stays the action accent.
- **Macro order: carbs, protein, fat** on every screen (Tarık, 2026-10-21; `Pantry.MACROS`).
- **The prototype is a starting point.** A change that makes daily use faster or more comfortable may
  depart from `design/screens.html` (Tarık, 2026-10-21); it goes in `deviations.md`. The rules above
  and the base still bind.

## Taste record (Pantry)
- 2026-10-20, round 3 (`design/yonler.html`): liked D2 Tabak, D6 Gösterge and D1 Akış ("orijinale
  benzer"); passed on D3 Şerit, D4 Katman, D5 Izgara. Read across (hypothesis): one round measuring
  object (ring, plate, dial) as the centre of the screen, standing on the open canvas, no boxes.
  Round 4 (`design/yonler-2.html`) varies that family.
- 2026-10-20, round 4 (`design/yonler-2.html`): kept V3's meals in the four corners ("köşelerde olma
  olayını sevdim"); rejected every weekly display tried (bars, small plates, dots, bowls: "hiçbirinde
  haftalık gösterge sevmedim"), so the main screen carries no week. Wants total kcal visible, and
  MyNetDiary's three side-by-side macro bars that change with the day ("hangisi daha fazla ise o
  üstü"), improved, possibly with V8's macro ring. Round 5 (`design/yonler-3.html`).
- 2026-10-20, round 5 (`design/yonler-3.html`): picked A3 (each meal owns the quarter facing its
  corner) but with no outer overflow line: a meal past its quarter runs on into the next one, in its
  own tone, the way A2's segments share one ring ("birbirlerinin alanlarına girsinler"); picked B1
  (one row, each macro's width = its share of today's kcal). The week is not dropped: he used
  MyNetDiary's strip to see past overages and to jump to a day by tapping or swiping. Round 6
  (`design/yonler-4.html`) draws day navigation that also shows overage.
- 2026-10-20, round 6 (`design/yonler-4.html`): picked W3, the date strip with each day's
  difference to budget ("şimdilik o olsun"). The meal tones in the ring and the macro strip read
  poorly ("okunabilirliği biraz zor"); round 7 (`design/yonler-5.html`) tries three colour treatments.
- 2026-10-20, round 7 (`design/yonler-5.html`): rejected all three; the validated chart hues (blue,
  teal, amber, violet) look garish, for the whole app ("renkli olan cırtlak duruyor for rest of the
  app"): the app stays grey + one orange, the only other colour lives inside the food drawings.
  Build on R2 (greys and patterns). The W3 day cells get a translucent fill showing how full each day
  is, with a wave animation (his ask; details Eko's). UI language: English (Tarık).
- 2026-10-20, round 8 (`design/yonler-6.html`): picked G3 ("şimdilik"): meals alternate dark and
  light grey on the ring with their initial (B, L, D, S) on each segment; macro values inside the
  bars. The waving day strip stays.
- 2026-10-21, over tone (`.tmp/taste-over/`, the real Today on 19 Oct): picked C, the base `danger` red, over
  violet (now), raspberry and blue ("mor o kadar uyarıcı değil", "C güzel bence"). Read across (hypothesis): for a
  warning he wants the plain warning colour, though he refused literal green-for-within; within stays grey.
- 2026-10-21, after a day on the phone: the ring keeps no slot for a meal not yet logged (the track stays whole and
  a meal takes room once logged; this ends A3's fixed quarters); the eaten list splits by meal; a meal's list opens
  on what is already in that meal; light, dark, system and dynamic (dark after sunset) themes in Settings.
- 2026-10-21, evening, on the phone: the ring becomes one arc for the day like MyNetDiary's ("o durum barındaki
  öğünleri kaldıralım sadece 1 tane bar olsun mynetdiary gibi"), ending round 8's G3 alternating meal arcs; the macro
  deviation marks go ("ne işe yarıyor anlamadım, gereksiz gibi"). Read across (hypothesis): on Today he wants one
  reading per element, the MyNetDiary one he knows; detail that needs decoding is cut.
- 2026-10-24, app icon round 1 (`D:/Projects/Calisthenics-App/design/icons.html`): torn between P11 Barcode (scan
  corners with an orange scan line) and P15 Plate, kcal left (plate with an orange arc); the current jar was passed
  over. Read (hypothesis): as in the Calisthenics pick, orange shows the app's own act (scanning, kcal used), not an
  object. Round 2 (`D:/Projects/Calisthenics-App/design/icons-2.html`) derives 10 from those two.
- 2026-10-24, app icon final: P27 Plate and fork (plate and fork in ink, kcal as an orange arc), over the scan family
  (P11, P21-P24, P29, P30) and the other plate variants. Source `icons/icon.svg`, rendered to the PNGs.

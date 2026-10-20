# Pantry: comfort, motion and quality of life for wave 3 (2026-10-21)

Research input for `plan-wave`, not a decision. Tarık asked what to add so Pantry feels high quality and
comfortable several times a day ("neler eklenmeli uygulamaya, daha nasıl kaliteli ve rahat hissettirir",
"animasyon eksikliği var"), and said a better daily flow may depart from the prototype.

**How this was checked.** I served the repo at `127.0.0.1:8150` and drove it with Python Playwright 1.62
(headless Chromium 151) at 360×780, DPR 3, `is_mobile`, `has_touch`, normal text size. The data was
`tests/fixtures/mynetdiary-slice.json` through `tools/import_mynetdiary.py`, with the clock set to Tue 20 Oct
19:30 so Today has entries and dinner is the suggested meal. The walk covered: Today → Dinner corner → list
→ gram sheet → chip → Add → back gesture → + on a row → tabs → search → edit an entry → Save → Delete →
past days from the strip → strip swipe → Settings. For timings I built a synthetic document in code the size
of his real log (464 days, 2,784 entries, 1,081 KB, made from the fixture's entries) and ran it with
4× CPU throttling. 4× is a rough stand-in for a mid-range Android phone (not verified against his phone).
Screens and scripts are in `D:/Projects/.scratch/pantry-qol/`, outside the repo. Nothing here was checked
on the `terra_nt` emulator or his phone.

Design language read first: Tarik Base v6 (`tasarim/references/DESIGN.md` → *Motion*, *Feedback*, `tokens.css`
motion tokens, `assets/motion/tarik-motion.js`), plus `design/DESIGN.md` and `design/deviations.md`.

## What the walk showed

| # | Seen | Where |
|---|---|---|
| F1 | **Every screen change is a hard cut.** `show()` in `app/core.js` replaces the screen, and `document.getAnimations()` is empty after a route change. Only three things move today: the gram sheet slides up (320 ms), the tab list fades, and the day strip slides in after a swipe (200 ms). | `core.js` `show()`; walk step 2 |
| F2 | **Toasts pop in and out with no motion, and they outlive the screen they belong to.** "1000 g added to dinner · Undo", fired by a + on the meal list, was still showing on *Edit entry* for the potato and after its Save. Its Undo would have removed the + entry, not the edit he had just made. | screens `09-entry`, `11-after-save` |
| F3 | **Save on Edit entry gives no confirmation and no Undo.** Only Delete calls `P.toast` in `entry.js`. | `entry.js` |
| F4 | **Tapping a day in the strip pushes a history entry and moves the strip under his finger.** The strip re-anchors on the tapped day. Taps on Mon 19, then Fri 17, then Wed 14 moved it 13–19 → 11–17 → 8–14, so the day he tapped jumps to the right edge. History depth reached 7, so the back gesture then walks through every day he looked at. A past day has no way back to Today except swiping the strip or pressing back over and over. | `today.js` `onClick` (`P.go('today', day)`), `render` (`stripEnd = null`); screen `13-past-day` |
| F5 | **The gram sheet shows a drag handle that does not drag.** A 300 px drag down from the handle left the sheet open. `log.js` has no pointer handling on the sheet, so it closes only by scrim tap, back gesture or Escape. | walk step 3 |
| F6 | **Logging a second food in the same meal is slow, and the list never shows the meal.** *Add* on the sheet returns to Today, so the next food costs another corner tap. The **+** path stays on the list, but nothing there says what is already in dinner or what it adds up to. After a +, the row looks exactly as before: its class is unchanged and only the toast confirms. | `log.js` `toToday`, `plus` |
| F7 | **Feedback waits for the save.** With his log's size, one save took 110–155 ms at 4× throttle: `structuredClone` 34 ms, `JSON.stringify` 12 ms, `localStorage.setItem` 10 ms, and the rest is the redraw. The toast and any change on screen arrive only after that. Not measured on the phone. | `perf.py`, `perf2.py` |
| F8 | **Typed grams cost an extra tap (inferred).** Enter in the grams field only blurs it (`log.js` keydown handler), and `index.html`'s viewport meta has no `interactive-widget`. Since Chrome 108 the keyboard resizes only the visual viewport, so the fixed sheet's *Add* button sits under the keyboard: he taps Done, then Add. Inferred from code plus Chrome's docs; not seen on the phone. | `log.js`, `index.html` |
| F9 | **Today snaps after every change.** It is redrawn with `innerHTML`, so after a log or an Undo the kcal number, the ring arc, the corner kcal, the macro bars and the day's tank all jump. The base says a changed number swaps, and a chart animates when its data changes. | `today.js` `draw()` |
| F10 | **Only scanning vibrates** (40 ms in `scan.js`). Logging, Undo and Delete are silent. | `scan.js` |
| F11 | **Every route scrolls to the top** (`window.scrollTo(0, 0)` in `show()`). Back from editing the eighth entry of a long day lands at the top of Today. Found by reading the code; the fixture's days were short. | `core.js` |
| F12 | **Spike: a View Transition around a route change works**, with transition types supported. During a running transition, taps land on `<html>` and not on buttons: a tap at 250 ms into a 1 s transition hit `HTML` twice. So a transition blocks the known "second tap on Delete lands on Today's Add" bug while it runs, but it also swallows fast taps he means. Keep transitions short and still add the router guard. | `vt2.py` |

Reached the target already: a frequent food at its usual amount takes Today → corner → **+** (2 taps,
then back), which meets the ≤ 3-tap acceptance. The sheet opens on his usual amount with chips. Delete has Undo.

## 1. Ranked improvements

Ranked by comfort per effort for someone who logs 4–8 times a day. Effort: **S** is under half an agent
task, **M** is about one task, **L** is several.

| Rank | Improvement (one line) | Why | Effort | Files | Departs from prototype? |
|---|---|---|---|---|---|
| 1 | **Screen transitions**: wrap `show()` in `document.startViewTransition`; push slides 24 px from the right, back reverses, everything else crossfades. | F1. Supported since Chrome 111, transition types since 125 ([Chrome docs, updated 2024-09-25](https://developer.chrome.com/docs/web-platform/view-transitions/same-document)). Chrome for Android listed as supported ([caniuse, read 2026-10-21](https://caniuse.com/view-transitions)). Skip our own transition when `popstate.hasUAVisualTransition` is true, so it never doubles a browser swipe animation ([MDN, modified 2025-07-03, "Baseline 2026"](https://developer.mozilla.org/en-US/docs/Web/API/PopStateEvent/hasUAVisualTransition)). Spike passed (F12). | S | `app/core.js` (direction from `history.state.depth`), `app/base.css` (the `::view-transition-*` rules) | No: it applies the base's *Push to a detail screen* pattern, which the static prototype cannot show. |
| 2 | **Toast done right**: rises in and fades out, carries the food's drawing, belongs to the action that made it (survives only the navigation that action caused), and Edit Save gets "Saved, 200 g · Undo". | F2, F3. The base *Toast* pattern (rise 8 px, `base` in, `fast` out). Design 4 draws the food in the toast (left open in the wave 2 report). | S | `app/core.js` (`toast` opts: `drawing`, `follow`), `app/base.css`, `app/entry.js`, `app/log.js` | Closer to the prototype (design 4). |
| 3 | **Feedback before the save, plus haptics**: on +, the icon turns into a check and the phone gives a 10 ms pulse in the same frame; the save runs on the next frame. Undo and Delete get their own short pulse. | F7, F10. `navigator.vibrate` needs sticky user activation in Chrome, which a tap provides ([MDN, read 2026-10-21](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/vibrate); Chrome shipped the restriction by [2022-04](https://lists.w3.org/Archives/Public/public-device-apis-log/2022Apr/0010.html)). Not verified: whether his phone's system vibration setting mutes it. | S | `app/core.js` (`Pantry.haptic(kind)`), `app/log.js`, `app/entry.js` | No. |
| 4 | **The meal list shows the meal**: one line under the title ("In dinner: 2 foods, 1,422 kcal") whose number swaps on each +, and a small check with a count on rows already logged at this meal today. | F6. MacroFactor keeps a "minified Plate" visible while adding, so a whole meal is logged without leaving search, and resets the interface after each add ([MacroFactor, updated 2024-09-25](https://macrofactor.com/new-food-logger/)). | S | `app/log.js` | Yes: design 2 has no summary line or row checks. |
| 5 | **"Same as yesterday's dinner"**: a row at the top of the meal list when yesterday's same meal had entries. One tap logs them all with their amounts and log-time totals; Undo removes all. | His own MyNetDiary recording shows "Copy From Yesterday's Lunch" in the meal menu (`notes.md`, 2026-10-20). MyNetDiary copies the foods and amounts of yesterday's meal with one "Same" click ([help page, © 2026, read 2026-10-21](https://mynetdiary.com/helpFoodEntry.html)). Cronometer has "Copy Yesterday's Group" ([help article](https://support.cronometer.com/hc/en-us/articles/360018695932-Mobile-Copy-Paste), read through a search summary on 2026-10-21; the page refused a direct fetch). A per-meal "copy yesterday" topped a 10,000-user survey in a MyFitnessPal design case study ([Behance](https://www.behance.net/gallery/34917723/MyFitnessPal-Smart-Copy); date and rollout not verified). He eats the same staples every day (`notes.md`: butter 316×, tuna 225×). | M | `app/log.js` | Yes: a new row not in design 2. |
| 6 | **Day strip that stays put**: tapping a day switches in place (`history.replaceState`, so at most one history entry for "a past day") and the strip does not move. A past day gets a *Today* ghost action in the top bar. A swipe follows the finger and settles on the next week. | F4. | M | `app/today.js` | Yes: design 7 has no Today action. |
| 7 | **Today shows what changed**: when he comes back after logging, the meal's arc grows from its old end, the corner kcal and the macro bars move to their new values, the day's tank fills, and the orange kcal-left number swaps last. Undo plays the same in reverse. | F9. These are the base patterns *A number changes* and *Bars appear or change*, with "the orange lands last". `numberSwap`, `resize` and `barsIn` already exist in `tarik-motion.js`. | M | `app/today.js`, `tarik-motion.js` copied unchanged to the root (base *Platform mapping*), `index.html`, `sw.js` shell list | No. |
| 8 | **Enter logs, and Add stays above the keyboard**: Enter in a valid grams field submits. Add `interactive-widget=resizes-content` to the viewport meta so the sheet's foot rises with the keyboard. | F8. `interactive-widget` exists in Chrome 108+, and omitting it means `resizes-visual` ([Chrome blog](https://developer.chrome.com/blog/viewport-resize-behavior), read 2026-10-21). Needs a check on the phone: the setting resizes every screen when the keyboard opens. | S | `index.html`, `app/log.js`, `app/entry.js`, `app/newfood.js` (same field) | No. |
| 9 | **Drag the gram sheet down to close**: the sheet follows the finger from the handle or header, and from the body when its scroll is at the top. Release past 30 % of its height, or flicked fast, closes it; otherwise it settles back with no overshoot. | F5: the handle promises a gesture the sheet does not have. The base's `ease-standard` is meant for "sheet drag". | M | `app/log.js` | No (the handle is in design 3). |
| 10 | **Router polish**: ignore a second navigation within 350 ms (the wave 2 leftover: two taps on Delete), and restore Today's scroll when coming back. | F11, F12, wave 2 report "Left for the next wave". | S | `app/core.js` | No. |
| 11 | **Home-screen shortcuts**: long-press the icon for "Log food" (`./#/add`) and "Scan" (`./#/scan`). | Shortcuts need a WebAPK install on Android and are best effort: the OS decides how many show ([web.dev](https://web.dev/articles/app-shortcuts), read 2026-10-21; [MDN, modified 2025-11-30](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/shortcuts)). Chrome checks the manifest about daily, so they reach an installed app within a day or two of a launch ([web.dev](https://web.dev/articles/manifest-updates); [Chrome blog](https://developer.chrome.com/blog/webapk-update-frequency)). | S | `manifest.json`, 96 px shortcut icons in `icons/` | No. |
| 12 | **"All nutrients" opens smoothly**: height to `auto` with `interpolate-size: allow-keywords`; older Chrome falls back to instant. | Chrome 129+ ([Chrome docs](https://developer.chrome.com/docs/css-ui/animate-to-height-auto), read 2026-10-21). | S | `app/log.js` | No. |
| 13 | **New and removed rows move**: a logged entry rises into *Eaten today*; a deleted one collapses, and Undo brings it back. Toasts can enter with `@starting-style`. | `@starting-style` in Chrome 117 ([web.dev](https://web.dev/blog/baseline-entry-animations), read 2026-10-21). | S | `app/today.js`, `app/base.css` | No. |
| 14 | **Stay in the meal after Add** (the sheet's Add returns to the list, not Today; Today comes with the back gesture or a *Done*). | F6. MacroFactor's "speed mode" returns to search after each add ([MacroFactor, updated 2024-09-25](https://macrofactor.com/new-food-logger/)). A typical dinner of his is 3–5 lines (chicken, rice, butter, tzatziki). | S | `app/log.js` | **Changes the Blueprint seam** "Saving … returns with `Pantry.go('today', date)`": Tarık's call. |
| 15 | Swipe an eaten row left to delete, with Undo. | Cronometer swipes diary rows for actions (help article above). Saves two taps on a rare action, with risk of accidental deletes. | M | `app/today.js` | Yes. |
| 16 | Copy a past day's meal to today (a menu on a past day's corner). | Cronometer's "Copy to Today" (help article above); MacroFactor's "paste to today" ([help](https://help.macrofactorapp.com/en/articles/95-copy-and-paste), read through a search summary on 2026-10-21). | M | `app/today.js`, `app/log.js` | Yes. |
| 17 | Quick-add kcal for eating out (a name and kcal, no food). | His history logs restaurant meals as single items (`notes.md`). The Blueprint leaves eating out out of v1. | M | `app/log.js` | Yes, and touches *Not in v1*. |
| 18 | Cold-start entrance (title, ring, strip, rows in sequence) only on the first launch of the day, never on returns. | The base's *Screen opens (first visit)* and *Splash → first screen*. | S | `app/today.js` | No. |
| 19 | A cheaper save (stop deep-cloning the whole 1 MB document on each change). | F7. Only if #3 is not enough on the phone; it touches the data path (risk). | M | `app/core.js` | No. |
| 20 | Over budget reads "+526" (the strip's sign) instead of only the word "over". | A small consistency point: the number and colour are the same in both states. | S | `app/today.js` | Slightly. |

Not recommended: a ripple effect on press (not in the base; the existing `:active` fill is enough), pull to
refresh (sync is automatic), a custom offline banner or update prompt. The service worker is already network
first with `skipWaiting`, so a release shows on the next launch with no prompt (`sw.js`).

## 2. Motion spec for Pantry

Built on Tarik Base v6 *Motion*: `--dur-fast` 120 ms, `--dur-base` 200 ms, `--dur-slow` 320 ms,
`--dur-chart` 600 ms, `--stagger` 40 ms, `--ease-enter` `cubic-bezier(0.22,1,0.36,1)`, `--ease-exit`
`cubic-bezier(0.4,0,1,1)`, `--ease-standard` `cubic-bezier(0.2,0,0,1)`, rise 8 px. Use the tokens by name,
and compose the pieces from `tarik-motion.js`, copied unchanged.

| Moment | Motion | Duration, easing |
|---|---|---|
| Push (Today → list, → Edit entry, → Settings, → Scan) | View Transition: the old page fades out; the new one fades in while sliding 24 px from the right. `#toast` gets `view-transition-name: toast` so it does not slide with the page. | old `fast` `ease-exit`; new `slow` `ease-enter` |
| Back (button or gesture) | Reverse: the new page comes from 24 px left. Skipped when `hasUAVisualTransition` is true, because Chrome already animated the swipe. | `base`, `ease-exit` out, `ease-enter` in |
| Save or Delete → Today | Crossfade only (not a push): he is returning home. | `base` |
| Today ↔ a past day (strip tap) | No slide. The strip stays; the selected outline moves. The content below the strip crossfades. | `fast` |
| Strip swipe | Follows the finger 1:1 (direct manipulation, not animation). On release it settles on the week with no overshoot. | `base`, `ease-standard` |
| Gram sheet open / close | Exists: scrim fade, sheet slides up; closing is shorter and accelerates. | `slow` `ease-enter` / `base` `ease-exit` |
| Sheet drag | Follows the finger; the scrim's opacity follows the distance. Release: close from where it is, or settle back. | remaining distance at `base` `ease-exit` / `base` `ease-standard` |
| + on a row | Press: the circle fills `surface-3` (exists). In the same frame the + swaps to a check (`swapText`-style fade) with a 10 ms pulse; the save follows. The check stays while the toast shows. | `fast` |
| Meal summary line on the list | The kcal swaps (`numberSwap`): the old value leaves upward, the new one rises. | `fast` out, `base` in |
| Toast | Rises 8 px and fades in; fades out; a replacement crossfades. | `base` in, `fast` out, 4 s on screen |
| Today after a change | Order: the arc segment grows from its old end (`stroke-dashoffset`), the macro bars resize, the day's tank fill rises, the corner kcal swaps, and the **orange kcal-left swaps last** (+120 ms after the greys). | arc and bars `chart` `ease-enter`; number swaps `fast`/`base` |
| New eaten row / deleted row | Rises 8 px with a fade / height collapses and fades. | `base` / `base` height, `fast` fade |
| Tab switch (Frequent, Recent, My foods) | Exists: the list crossfades; the underline changes colour and does not slide. | `fast` |
| Chips, meal radios | Background colour (exists). | `fast` |
| All nutrients | Height to `auto` (Chrome 129+), else instant. | `base`, `ease-standard` |
| Cold start (first launch of the day) | Title, ring, strip, then rows rise, 40 ms apart; the orange number last. | `base` per item, `slow` for the ring |

**Never animates:** the kcal shown while he types grams (it must keep up with the keys); search
results filtering; scrolling; a return to Today that changed nothing; error text; the eye-check screens
under test. Numbers never count up. Nothing loops except the day-strip wave (an existing deviation) and a
skeleton. No bounce, spring or ripple. Nothing travels more than 24 px.

**Reduced motion:** every slide becomes an opacity fade of the same length. The View Transition keeps only
its crossfade, and `tokens.css` already zeroes `--rise`. The wave stops (exists). A drag still follows the
finger, but the release fades rather than slides. Haptics stay, since they are not motion.

**Rules I would bend or add, and why:**
- *Added, not broken:* haptic pulses (10 ms log, 10 ms Undo, 20 ms delete, the existing 40 ms scan). The base
  says nothing about haptics. Write them into `design/DESIGN.md` as a Pantry motion note.
- *Read narrowly:* the base's screen-open sequence is for the **first visit**. Pantry returns to Today 20+
  times a day, so a staggered entrance on each return would delay reading the number. Keep it to cold start.
- *One judgment call:* the base pairs a push with `slow` (320 ms). F12 showed that taps are swallowed while a
  transition runs. If 320 ms feels sticky on the phone, drop the push to `base` (200 ms); that is a token
  value change, not a rule change.

## 3. Wave 3 picks

**Top picks (8), the most comfort per effort.** About 5 S and 3 M:

1. Screen transitions, with the double-tap guard and scroll restore folded in (#1 + #10), S.
2. Toast done right, with Saved · Undo on Edit (#2), S.
3. Feedback before the save, plus haptics (#3), S.
4. The meal list shows the meal (#4), S.
5. Same as yesterday's meal (#5), M.
6. A day strip that stays put, with a Today action (#6), M.
7. Today shows what changed (#7), M.
8. Enter logs, and Add stays above the keyboard (#8), S.

**Decision for Tarık before planning:** stay in the meal after Add (#14). It changes a Blueprint seam,
costs S, and goes well with pick 4.

**Later (not wave 3):** drag-to-dismiss the sheet (#9; first see whether the back gesture and scrim are
enough in a real week), home-screen shortcuts (#11), All nutrients height animation (#12), row enter and
leave motion (#13), swipe to delete (#15), copy a past meal to today (#16), quick-add kcal (#17), the
cold-start entrance (#18), a cheaper save (#19, only if the phone still lags after pick 3), and "+526"
(#20).

`docs/TASKS_INDEX.md` already drafts wave 3 as the catalogue, the history upload, deploy and a week of real
use. These picks fit before that week, so the week tests the finished feel. Each one still needs its 360 px
check on the emulator or phone (AGENTS.md); headless Chromium cannot show text boosting, the keyboard or
vibration.

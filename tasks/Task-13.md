# Task-13: Light, dark, system or dynamic theme, chosen in Settings
> **Execution:** agent `ultracode`
> *Why:* Tarık wants to pick the theme himself, including one that goes dark when the evening comes.

**Lane**
- OWNS: `app/core.js` (theme only), `app/settings.js`, `index.html`, `manifest.json` (theme colours only), `tests/test_theme.py`
- MUST NOT TOUCH: `app/today.js`, `app/log.js`, `app/base.css`, `app/entry.js`, `app/scan.js`, `app/newfood.js`, `app/drawings.js`, `app/sync.js`, `app/registry.js`, `tests/acceptance.py`, `sw.js`, every other test file
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_theme.py`)
- DEPENDS ON: none

## Goal
In Settings, Tarık chooses the theme: **Dynamic** (light by day, dark from sunset to sunrise), **Light**, **Dark** or
**System** (follows the phone). Tarık, 2026-10-21: "açık karanlık mod da ekle manuel değiştirilebilecek, ayarlara
ekle dinamik, açık, kapalı, sistem şeklinde ayarlar olsun (dinamik şu anki akşam oldu mu kararıyor)". The choice
applies at once, survives a restart, and follows him to his other device through sync like his other settings.
Dynamic switches by itself at sunset and sunrise while the app is open, and is right the moment the app opens or
comes back from the background (a phone freezes a background page). A new document starts on System, as today.
Sync merges settings as one object, so a theme changed on one device while targets change on another keeps the later
of the two whole objects; that is accepted.
Sunset and sunrise are those of where he lives (Darwin, NT) unless the builder finds a way that needs no permission
prompt and is better; the builder says which and why. The browser's own colours (status bar, the theme colour) follow
the chosen theme, not only the page.

## Why
He uses the app morning to night; a bright screen at night and a dark one in the sun both cost comfort.

## Acceptance
- [ ] Settings shows the four choices with the current one marked; picking one changes `<html data-theme>` at once and stores it in `settings.theme` (`dynamic`, `light`, `dark`, `system`); an older document without `settings.theme` opens as System, unchanged.
- [ ] Dynamic: with an injected clock, a moment before Darwin's sunset is light and a moment after is dark, both when the app opens then, when the clock crosses sunset with the app open, and when the page becomes visible again after the clock crossed it; the same at sunrise. Tests never wait on real time.
- [ ] The computed sunset and sunrise match a published table for Darwin (name the source in the test) within 3 minutes on at least four dates across the year, computed in absolute time.
- [ ] System follows `prefers-color-scheme` live, as today.
- [ ] The theme-color the browser actually uses follows the chosen theme: with Light picked on a phone set to dark (and the reverse), no `<meta name="theme-color">` whose media matches says the other theme's colour.
- [ ] A synced document with a different `settings.theme` applies it without a reload.
- [ ] At 360 × 780, text 1.0, Settings in light and dark: no horizontal scroll, no console errors; the theme control also fits where `tests/test_sync.py` already checks Settings (150 % text, 240 px).
- [ ] Each test added fails once when the behaviour it protects is broken (shown in the report, restored).
- [ ] (eye) On Tarık's phone: the choice is easy to find in Settings and the switch is immediate; the status bar follows it; Light is not darkened by Samsung Internet's own dark mode; Dynamic is dark after sunset.

## Out of scope
- New colours or a redesign of either theme; Today and the meal list (Task-11, Task-12).

Fixed: `settings.theme` values `dynamic` | `light` | `dark` | `system`; the Pantry API names in the header of `app/core.js` stay.

# Changelog

All notable changes to Pantry are written here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the numbers follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):

- **0.y.z** until v1 (the Blueprint's "Done when" holds); **1.0.0** is v1.
- **MINOR** (0.2.0, 1.1.0): one wave of features. **PATCH** (0.2.1): fixes and small changes between waves.
- **MAJOR** (2.0.0): a change that breaks what exists (the stored data needs a migration, a command or API changes).
- The release string a deploy needs (a service worker cache, a package version) is this file's newest version.

Each wave adds its lines under *Unreleased* as it lands; the closing wave turns *Unreleased* into the new version
with the date. What later versions will bring lives in `notes.md` → *Backlog* and `docs/TASKS_INDEX.md`.

Versions before 0.5.0 were numbered afterwards, from the git history; the service worker cache went `pantry-v1` to
`pantry-v13` then.

## [Unreleased]

## [0.5.0] - 2026-10-25

### Added
- A food without a barcode can be added by hand, and "by hand" is offered under search matches too.
- The sync repository is a setting, with texts for a stranger; README and MIT licence (the site is public).
- App icon: plate and fork (P27).

### Changed
- Today's ring draws one arc, as MyNetDiary does, with no macro marks.
- First launch opens on Today at 0; the day strip shows two days ahead.
- A past day keeps the targets it had.
- The version comes from this file; the service worker cache is `pantry-v<version>`.

## [0.4.0] - 2026-10-21

### Added
- A meal's list opens on that meal; a tap opens a food, + logs, the keyboard comes only from the amount (Task-11).
- Today at a glance: the whole ring, macro bars against target, eaten by meal with easy delete, red when over (Task-12).
- Light, dark, system or dynamic theme in Settings (Task-13).

## [0.3.0] - 2026-10-21

### Added
- Screens that move, a forgiving router, Edit Save with Undo, Settings day count and macro order (Task-07).
- Logging the MyNetDiary way: tick several foods, yesterday's meal, instant feedback on + (Task-08).
- Today in colour and motion: over budget at a glance, swipe the ring between days (Task-09).
- Barcode catalogue from Tarık's Coles and Woolworths purchases (Task-10).

## [0.2.0] - 2026-10-21

### Added
- Today in full: day strip, meals in the corners, the ring, macro strip, eaten list (Task-02).
- Meal list and gram sheet: frequent foods, usual grams, one-tap add (Task-03).
- Scan and new product: his foods, the store catalogue, Open Food Facts, a label form (Task-04).
- Edit, move and delete an entry (Task-05).
- Sync with the private data repository, and settings (Task-06).

## [0.1.0] - 2026-10-20

### Added
- The thinnest path: PWA shell, data document, log a food, kcal left, a camera scan probe, the gate (Task-00).
- Import of the 464-day MyNetDiary history (Task-01).

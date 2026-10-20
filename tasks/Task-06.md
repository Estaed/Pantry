# Task-06: Sync with the private data repo, and settings
> **Execution:** agent `ultracode`
> *Why:* one lost phone must not lose the log, and the 464 imported days reach the phone through this.

**Lane**
- OWNS: `app/sync.js`, `app/settings.js`, `tests/test_sync.py`
- MUST NOT TOUCH: `app/core.js`, `app/registry.js`, `app/base.css`, `tests/acceptance.py`, `index.html`, `sw.js`, `tools/`, and every other `app/*.js`
- GATE: `python tests/acceptance.py` (from repo root; it runs `tests/test_sync.py`)
- DEPENDS ON: none

## Goal
Tarık opens Settings (`design/screens.html` → *9. Settings*): his targets (daily kcal, the macro split,
salt) editable; Sync with the GitHub data repo `Estaed/Pantry-Data` (file `pantry-data.json`, a
fine-grained token he pastes once, kept only under `pantry.sync`, shown masked), its status ("Synced
2 min ago", or what failed); and Data (MyNetDiary history range and counts, his foods).

Sync runs by itself: it pulls when the app opens or comes back to the foreground, pushes a short
while after a change, and works offline by waiting. It merges, never overwrites: entries and foods
are matched by id; one only on one side is kept, unless its id is in the other side's `doc.removed`;
for an id on both sides, the phone's version wins when the phone changed that id since the last
pull (track the changed ids by diffing `prev` and `doc` in a subscriber, kept in `syncState`),
otherwise the repo's; `settings` the same way as one unit; `catalogue` comes from the repo; `removed` lists are united. The first sync on a
phone that has the starter foods and a few entries, against a repo holding the imported history,
ends with all 2,722 imported entries plus the phone's own, and the starter foods replaced by the
imported versions of the same ids. When it fails, sync sets `lastError` (a sentence: "Sync failed. Saved on this phone; it will try
again." and the likely cause) with `Pantry.setSyncState`; Today draws the banner (Task-02); nothing
is lost. Pushes wait at least 10 s after the last change; `Pantry.markClean(upTo)` gets the counter
read when the push started.

Port the working pieces of `D:/Projects/Calisthenics-App/index.html` (`getSyncConfig` to
`scheduleSync`, around lines 3373 to 3640: config apart from the data, `sha` handling, dirty flag,
retry) instead of inventing them; its merge is a whole-document replace, which Pantry must not do.
GitHub Contents API (checked 2026-10-20): above 1 MB, GET returns the content only with the raw media
type (`application/vnd.github.raw+json`), and the object media type gives the `sha` with empty content;
the imported document is already 1,067 KB (1,092,625 bytes), so the first sync takes the large path;
handle both sides of 1 MB.

## Why
v1's data lives on one phone until this exists; it is also the only way the imported history and
the store catalogue reach the phone.

## Acceptance
- [ ] Against a mocked GitHub API (as Calisthenics-App's `tests/acceptance.py` mocks it), a remote built with `tools/import_mynetdiary.py` from `tests/fixtures/mynetdiary-slice.json` (9 entries, 7 foods) merged into a phone with the starter foods and two own entries ends with 11 entries, no duplicate ids, and the overlapping starter (potato) deep-equal to the remote food; when `D:/Projects/Pantry/references/mynetdiary-history-2026-10-20.json` exists, the same with the full history gives 2,722 + 2 entries (skip says so when absent).
- [ ] An edit made while a push is in flight survives: the phone stays dirty and the next pull keeps the edit.
- [ ] An entry deleted on the phone (in `doc.removed`) stays deleted after a pull from a repo that still has it; an entry deleted in the repo's `removed` disappears from the phone after a pull.
- [ ] A change made while offline is pushed once back online, with the `sha` it read; a 409 or `sha` mismatch makes it pull, merge and push again, never overwrite.
- [ ] A remote file above 1 MB is read through the raw media type and its `sha` through the object media type; the mock answers the default media type above 1 MB the way GitHub does (no content) and serves both sizes; that answer is never shown as a token problem.
- [ ] A bad or expired token (401/403/404) shows the banner on Today and a plain reason in Settings; the local document is untouched and still marked dirty.
- [ ] The token never appears in the document, in `pantry-data.json` or in any URL; only under `pantry.sync`.
- [ ] Changing targets in Settings updates Today's numbers (the kcal budget and macro targets) and is synced; a later pull with the repo's old targets does not undo it.
- [ ] At 360 × 780 with text at 150 % and at 240 px: Settings has no horizontal scroll, no console errors, dark and light both render.
- [ ] The tests fail when the merge is replaced by a whole-document replace, and when `doc.removed` is ignored (shown once each, restored).
- [ ] (eye) On `terra_nt` at 360 dp: Settings matches `design/screens.html` → *9. Settings* (without the theme row: the theme follows the phone in v1). After deploy, Tarık pastes his token and the phone shows his 464 days.

## Out of scope
- Uploading the imported history to the repo: the main loop does it once with `tools/import_mynetdiary.py` output before Tarık's first sync.
- Creating the token: Tarık makes a fine-grained token for `Estaed/Pantry-Data` (Contents read and write) himself.
- The catalogue tool (wave 3).

Fixed:
- Routes, `doc.removed`, `doc.catalogue`, test layout: Blueprint → *Screens and seams*.
- Use `Pantry.change(fn, { dirty: false })` for a document that came from the repo, `Pantry.markClean()` after a push, `Pantry.syncState()`/`setSyncState()` for the token and the last `sha` (`app/core.js` header).
- `app/sync.js` and `app/settings.js` are new scripts: list their two `PANTRY_FEATURES.push(...)` lines in the report for the orchestrator to append to `app/registry.js`.
- This path can lose data: the review runs spec and code lenses as well as the screen lens.

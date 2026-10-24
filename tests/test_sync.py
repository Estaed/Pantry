"""Checks for Task-06: sync with the private data repo (app/sync.js) and the Settings screen (app/settings.js), with
Task-07's days-logged count ("M (+P)") and the split read and typed carbs, protein, fat.

Run from the repo root: python tests/test_sync.py   (exit 0 = no FAIL; prints PASS, FAIL or SKIP per check)

Reuses the gate's server, phone and checks from tests/acceptance.py. The GitHub Contents API is mocked in Python
the way Calisthenics-App's tests/acceptance.py mocks it, plus what this repo needs: a file above 1 MB answers the
default and object media types with an empty content (GitHub, checked 2026-10-20) and only the raw media type
carries its text; a PUT with a stale sha gets 409; new shas are git blob shas of the stored text.
The repo's document is built with tools/import_mynetdiary.py from tests/fixtures/mynetdiary-slice.json (three
real days); the full history, references/mynetdiary-history-2026-10-20.json, is used when it is on this machine
(gitignored personal data; SKIP says so when it is absent). Synthetic entries are built here to exercise a rule
(the phone's own entries, another device's pushes, padding past 1 MB). Outputs go to .tmp/test_sync/; the built
documents are removed as soon as they are read, the screenshots (settings-*.png) stay. Pushes wait 10 s after the
last change, so this file takes a few minutes.
"""
import base64
import copy
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = A.ROOT
WORK = ROOT / ".tmp" / "test_sync"
FIXTURE = ROOT / "tests" / "fixtures" / "mynetdiary-slice.json"
FULL_NAME = "mynetdiary-history-2026-10-20.json"
FULL_CANDIDATES = [Path(p) for p in (os.environ.get("MYNETDIARY_SOURCE"),) if p] + [
    ROOT / "references" / FULL_NAME, Path("D:/Projects/Pantry/references") / FULL_NAME]
TOKEN = "github_pat_11TESTONLY0000_mockTokenForPantryTestsNotARealOne0000000000000000000000000"
EXPIRED = "github_pat_11TESTONLY0000_anExpiredTokenThatTheMockRefuses000000000000000000000000"
FIRST_REPO = "Estaed/Pantry-Data"      # the repo a phone connected before the repo was a setting keeps
REPO_PATH = "/repos/" + FIRST_REPO
CONTENTS_PATH = REPO_PATH + "/contents/pantry-data.json"
CONTENTS_URL = "https://api.github.com" + CONTENTS_PATH
PREFIX = "Sync failed. Saved on this phone; it will try again."
POTATO = A.STARTER[4][0]
STARTER_IDS = [s[0] for s in A.STARTER]
LIMIT = 1024 * 1024
TODAY = "2026-10-20"


# ── a GitHub Contents API stand-in ────────────────────────────────
class MockGitHub:
    CORS = {"access-control-allow-origin": "*",
            "access-control-allow-headers": "authorization, accept, content-type, x-github-api-version",
            "access-control-allow-methods": "GET, PUT, OPTIONS",
            "access-control-expose-headers": "etag, x-ratelimit-remaining"}

    def __init__(self, doc=None, repo=FIRST_REPO):
        self.repo = repo
        self.repo_path = "/repos/" + repo
        self.text = None
        self.sha = None
        self.requests = []          # every call: method, url, accept, authorization, body
        self.puts = []              # every PUT: the sha it sent, the status it got, when, the document it carried
        self.mode = None            # None, or 403 / 404: every call with the right token answers that
        self.readonly = False       # reads work, writes answer 403 (a token with Contents read only)
        self.before_put = None      # run once before the next PUT is judged: another device pushing first
        if doc is not None:
            self.store(doc)

    def store(self, doc):
        text = doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
        data = text.encode("utf-8")
        self.text = text
        self.sha = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

    def doc(self):
        return json.loads(self.text)

    def handle(self, route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers=self.CORS)
        path = urllib.parse.urlsplit(req.url).path
        accept = req.headers.get("accept", "")
        auth = req.headers.get("authorization")
        self.requests.append({"method": req.method, "url": req.url, "accept": accept, "auth": auth, "body": req.post_data})

        def answer(status, payload, headers=None):
            return route.fulfill(status=status, headers={**self.CORS, **(headers or {})}, content_type="application/json",
                                 body=json.dumps(payload))

        if auth != f"Bearer {TOKEN}":
            return answer(401, {"message": "Bad credentials"})
        if self.mode == 403:
            return answer(403, {"message": "Resource not accessible by personal access token"}, {"x-ratelimit-remaining": "4999"})
        if self.mode == 404 and path.startswith(self.repo_path):
            return answer(404, {"message": "Not Found"})       # a private repo the token cannot see
        if path == self.repo_path:
            return answer(200, {"full_name": self.repo, "private": True})
        if path != self.repo_path + "/contents/pantry-data.json":
            return answer(404, {"message": "Not Found"})
        if req.method == "GET":
            if self.text is None:
                return answer(404, {"message": "Not Found"})
            data = self.text.encode("utf-8")
            if "application/vnd.github.raw" in accept:
                return route.fulfill(status=200, headers=self.CORS, content_type="text/plain; charset=utf-8", body=data)
            big = len(data) > LIMIT
            raw = base64.b64encode(data).decode()
            content = "" if big else "\n".join(raw[i:i + 60] for i in range(0, len(raw), 60)) + "\n"
            return answer(200, {"type": "file", "name": "pantry-data.json", "path": "pantry-data.json", "sha": self.sha,
                                "size": len(data), "encoding": "none" if big else "base64", "content": content})
        if req.method == "PUT":
            if self.before_put:
                hook, self.before_put = self.before_put, None
                hook(self)
            sent = json.loads(req.post_data or "{}")
            put = {"sha": sent.get("sha"), "time": time.perf_counter()}
            self.puts.append(put)
            if self.readonly:
                put["status"] = 403
                return answer(403, {"message": "Resource not accessible by personal access token"}, {"x-ratelimit-remaining": "4999"})
            if self.text is not None and sent.get("sha") != self.sha:
                put["status"] = 409 if sent.get("sha") else 422
                return answer(put["status"], {"message": "pantry-data.json does not match " + str(sent.get("sha"))})
            if self.text is None and sent.get("sha"):
                put["status"] = 422
                return answer(422, {"message": "sha given for a file that does not exist"})
            created = self.text is None
            self.store(base64.b64decode(sent["content"]).decode("utf-8"))
            put["status"] = 201 if created else 200
            put["doc"] = self.doc()
            return answer(put["status"], {"content": {"name": "pantry-data.json", "sha": self.sha}, "commit": {"message": sent.get("message")}})
        return answer(405, {"message": "Method not allowed"})


# ── helpers ───────────────────────────────────────────────────────
def build_remote(source, name):
    out = WORK / f"{name}.json"
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "import_mynetdiary.py"), str(source), "-o", str(out)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    if done.returncode != 0:
        raise RuntimeError(f"import_mynetdiary.py exit {done.returncode}: {done.stdout[-400:]} {done.stderr[-400:]}")
    doc = json.loads(out.read_text(encoding="utf-8"))
    out.unlink()                                              # the built document may hold personal history
    return doc


def install(site):
    """Serve app/registry.js with this feature's two scripts listed, unless integration already listed them."""
    registry = (ROOT / "app" / "registry.js").read_text(encoding="utf-8")
    add = [f for f in ("app/sync.js", "app/settings.js") if f"PANTRY_FEATURES.push('{f}');" not in registry]
    if add:
        registry = registry if registry.endswith("\n") else registry + "\n"
        site.overlay[A.BASE + "app/registry.js"] = (registry + "".join(f"PANTRY_FEATURES.push('{f}');\n" for f in add)).encode("utf-8")


def watch(page, errors, tag):
    """The gate's error watch, except the browser's own line for a mocked GitHub refusal (401, 404, 409)."""
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))

    def console(m):
        if m.type != "error":
            return
        if m.text.startswith("Failed to load resource") and (m.location or {}).get("url", "").startswith("https://api.github.com/"):
            return
        errors.append(f"[{tag}] console: {m.text}")
    page.on("console", console)


def phone(browser, errors, tag, mock, text=A.BIG_TEXT):
    """The gate's phone, with service workers blocked so every GitHub call reaches the mock."""
    ctx = browser.new_context(**A.PHONE, service_workers="block")
    ctx.clock.set_fixed_time(A.NOW)
    ctx.route("https://api.github.com/**", mock.handle)
    page = ctx.new_page()
    watch(page, errors, tag)
    A.set_text(page, text)
    return ctx, page


def doc(page):
    return page.evaluate("() => Pantry.doc()")


def state(page):
    return page.evaluate("() => Pantry.syncState()")


def ids(d):
    return [e["id"] for e in d["entries"]]


def count(page):
    return page.evaluate("() => Pantry.doc().entries.length")


def has(page, entry_id):
    return page.evaluate("id => Pantry.doc().entries.some(e => e.id === id)", entry_id)


def wait_until(page, cond, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        page.wait_for_timeout(100)
    return cond()


def idle(page):
    page.wait_for_function("() => window.PantrySync && !PantrySync.status().running", timeout=30000)


def pushed(page, mock, n, timeout=30.0):
    """Wait until the mock has taken n PUTs and the last one was stored, then until the sync run has ended."""
    ok = wait_until(page, lambda: len(mock.puts) >= n and mock.puts[n - 1].get("status") in (200, 201), timeout)
    idle(page)
    return ok


def foreground(page):
    page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
        document.dispatchEvent(new Event('visibilitychange')); }""")


def open_settings(page, url):
    page.goto(url + "#/settings")
    page.wait_for_selector('[data-screen="settings"] [data-part="targets"] .settings-row')


def configure(page, url, token=TOKEN, repo=FIRST_REPO):
    """Name the data repo and paste the token in Settings, as Tarik does once."""
    open_settings(page, url)
    page.get_by_label("Data repo").fill(repo)
    page.get_by_label("GitHub token").fill(token)
    page.get_by_role("button", name="Save and sync").click()


def entry(entry_id, food, grams, meal="lunch", date=TODAY):
    kcal = round(food["per100"]["kcal"] * grams / 100, 1)
    return {"id": entry_id, "date": date, "meal": meal, "foodId": food["id"], "amount": f"{grams} g", "grams": grams, "totals": {"kcal": kcal}}


# The phone's own two entries, logged before the first sync (synthetic, from the starter foods).
OWN = """() => { const chicken = Pantry.starter[0].food, potato = Pantry.starter[4].food;
  Pantry.change(d => { d.entries.push(
    { id: '2026-10-20-ptest1', date: '2026-10-20', meal: 'breakfast', foodId: chicken.id, amount: '350 g', grams: 350, totals: Pantry.totals(chicken, 350) },
    { id: '2026-10-20-ptest2', date: '2026-10-20', meal: 'dinner', foodId: potato.id, amount: '500 g', grams: 500, totals: Pantry.totals(potato, 500) }); }); }"""
OWN_IDS = ["2026-10-20-ptest1", "2026-10-20-ptest2"]

ADD = """([id, grams]) => { const potato = Pantry.starter[4].food;
  Pantry.change(d => { d.entries.push({ id, date: '2026-10-20', meal: 'snacks', foodId: potato.id, amount: grams + ' g', grams, totals: Pantry.totals(potato, grams) }); }); }"""

# On the next PUT, edit ptest1 to 400 g right after the request has left: an edit made while a push is in flight.
EDIT_DURING_PUT = """() => { const orig = window.fetch; window.__edited = false;
  window.fetch = function (url, init) {
    const sent = orig.apply(this, arguments);
    if (init && init.method === 'PUT' && !window.__edited) {
      window.__edited = true;
      Pantry.change(d => { const e = d.entries.find(x => x.id === '2026-10-20-ptest1');
        for (const k of Object.keys(e.totals)) e.totals[k] = e.totals[k] * 400 / e.grams;
        e.grams = 400; e.amount = '400 g'; });
    }
    return sent;
  }; }"""

DELETE = """id => Pantry.change(d => { d.entries = d.entries.filter(e => e.id !== id);
  (d.removed = d.removed || []).push({ id, at: new Date().toISOString() }); })"""


# ── scenarios ─────────────────────────────────────────────────────
def check_merge_rules(browser, url, errors, remote):
    """The pure merge, case by case (PantrySync.merge)."""
    ctx, page = phone(browser, errors, "merge", MockGitHub())
    A.open_today(page, url)
    got = page.evaluate("""remote => {
      const local = JSON.parse(JSON.stringify(Pantry.doc()));
      const r = JSON.parse(JSON.stringify(remote));
      const e0 = r.entries[0], e1 = r.entries[1], e2 = r.entries[2];
      local.entries = [{ ...e0, amount: 'phone' }, { ...e1, amount: 'phone' }, { ...e2, amount: 'phone' },
                       { ...e0, id: 'phone-only' }, { ...e0, id: 'phone-deleted-in-repo' }];
      r.removed = [{ id: 'phone-deleted-in-repo', at: '2026-10-20T07:00:00+09:30' }];
      local.removed = [{ id: r.entries[3].id, at: '2026-10-20T07:00:00+09:30' }];
      local.settings = { targets: { ...local.settings.targets, kcal: 1999 } };
      r.catalogue = [{ barcode: '9312726072232', name: 'Tzatziki', store: 'woolworths', per100: { kcal: 108 } }];
      local.catalogue = [];
      const changed = { entries: { [e1.id]: 1 }, foods: {} };
      const m = PantrySync.merge(local, r, changed);
      const m2 = PantrySync.merge(local, r, { ...changed, settings: 2 });
      const byId = Object.fromEntries(m.entries.map(e => [e.id, e]));
      return {
        repoWins: byId[e0.id].amount, phoneWins: byId[e1.id].amount, phoneOnly: 'phone-only' in byId,
        repoOnly: r.entries.slice(4).every(e => e.id in byId), deletedInRepo: 'phone-deleted-in-repo' in byId,
        deletedOnPhone: r.entries[3].id in byId, removed: m.removed.map(x => x.id).sort(),
        catalogue: m.catalogue, settingsRepo: m.settings.targets.kcal, settingsPhone: m2.settings.targets.kcal,
        order: m.entries.slice(0, 2).map(e => e.id), unique: new Set(m.entries.map(e => e.id)).size === m.entries.length,
      };
    }""", remote)
    A.check("merge: an id on both sides takes the repo's version when the phone did not change it", got["repoWins"] != "phone", got)
    A.check("merge: an id on both sides takes the phone's version when the phone changed it", got["phoneWins"] == "phone", got)
    A.check("merge: one only on one side is kept (phone-only and repo-only)", got["phoneOnly"] and got["repoOnly"], got)
    A.check("merge: an id in the repo's removed is dropped from the phone; one in the phone's removed stays dropped",
            not got["deletedInRepo"] and not got["deletedOnPhone"], got)
    A.check("merge: the removed lists are united", got["removed"] == sorted(["phone-deleted-in-repo", remote["entries"][3]["id"]]), got)
    A.check("merge: catalogue comes from the repo", got["catalogue"] and got["catalogue"][0]["barcode"] == "9312726072232", got)
    A.check("merge: settings come from the repo unless the phone changed them", got["settingsRepo"] == 2200 and got["settingsPhone"] == 1999, got)
    A.check("merge: no duplicate ids; the repo's order first", got["unique"] and got["order"] == [e["id"] for e in remote["entries"][:2]], got)
    seen = page.evaluate("""async () => { const seen = [];
        Pantry.subscribe((doc, why) => seen.push(why));
        Pantry.change(d => { d.settings.targets.salt = 6; });
        const during = seen.slice();
        await new Promise(r => setTimeout(r, 0));
        return { during, after: seen, changed: Pantry.syncState().changed }; }""")
    A.check("with sync loaded, other subscribers hear 'change' first; the changed ids are stored right after",
            seen["during"] == ["change"] and seen["after"][:2] == ["change", "sync"] and seen["changed"].get("settings"), seen)
    ctx.close()


def first_sync(browser, url, errors, remote, label):
    """A phone with the starter foods and two own entries meets a repo holding imported history."""
    mock = MockGitHub(remote)
    first_sha = mock.sha
    want = len(remote["entries"]) + 2
    ctx, page = phone(browser, errors, f"first-{label}", mock)
    A.open_today(page, url)
    t0 = time.perf_counter()        # before the change; perf_counter, since monotonic() moves in 16 ms steps on Windows
    page.evaluate(OWN)
    configure(page, url)
    merged = wait_until(page, lambda: count(page) == want, 60)
    d = doc(page)
    early = list(mock.puts)
    entry_ids = ids(d)
    A.check(f"first sync ({label}): {len(remote['entries']):,} repo entries + 2 own = {want:,}, no duplicate ids",
            merged and len(entry_ids) == want and len(set(entry_ids)) == want, (len(entry_ids), len(set(entry_ids))))
    remote_foods = {f["id"]: f for f in remote["foods"]}
    foods = {f["id"]: f for f in d["foods"]}
    A.check(f"first sync ({label}): the overlapping starter (potato) is deep-equal to the repo's food",
            POTATO in remote_foods and foods.get(POTATO) == remote_foods[POTATO], foods.get(POTATO))
    starters_ok = all((foods.get(s) == remote_foods[s]) if s in remote_foods else (s in foods) for s in STARTER_IDS)
    A.check(f"first sync ({label}): every starter food is replaced by the repo's version of the same id, the rest kept",
            starters_ok and len(foods) == len(set(remote_foods) | set(STARTER_IDS)), len(foods))
    own = {e["id"]: e for e in d["entries"] if e["id"] in OWN_IDS}
    A.check(f"first sync ({label}): the phone's own entries are kept as logged", sorted(own) == OWN_IDS
            and own[OWN_IDS[0]]["grams"] == 350 and own[OWN_IDS[1]]["grams"] == 500, own)
    A.check(f"first sync ({label}): nothing is pushed before 10 s after the last change", not early
            or early[0]["time"] - t0 >= 10.0, [p["time"] - t0 for p in early])

    ok = pushed(page, mock, 1, 40)
    A.check(f"first sync ({label}): one push, at least 10 s after the last change, with the sha it read",
            ok and len(mock.puts) == 1 and mock.puts[0]["time"] - t0 >= 10.0 and mock.puts[0]["sha"] == first_sha,
            [(p.get("status"), round(p["time"] - t0, 1), p["sha"] == first_sha) for p in mock.puts])
    d = doc(page)
    st = state(page)
    A.check(f"first sync ({label}): the repo then holds exactly the phone's document", mock.doc() == d)
    A.check(f"first sync ({label}): clean after the push (dirty false, sha stored, no error, changed ids cleared)",
            st.get("dirty") is False and st.get("sha") == mock.sha and st.get("lastError") is None
            and st.get("changed") == {"entries": {}, "foods": {}} and st.get("lastSync"), {k: st.get(k) for k in ("dirty", "lastError", "changed")})
    return ctx, page, mock


def check_slice(browser, url, errors, remote):
    ctx, page, mock = first_sync(browser, url, errors, remote, "slice")
    gets = [r for r in mock.requests if r["method"] == "GET" and r["url"].startswith(CONTENTS_URL)]
    A.check("a file of 1 MB or less is read inline through the object media type, no raw call",
            gets and all(g["accept"] == "application/vnd.github.object+json" for g in gets), [g["accept"] for g in gets])

    # the token: pasted once, kept only under pantry.sync, never in the document, the repo file, a URL or the page
    stored = page.evaluate("() => ({ doc: localStorage.getItem('pantry.v1'), sync: localStorage.getItem('pantry.sync') })")
    A.check("the token is kept only under pantry.sync, never in the document", TOKEN not in stored["doc"] and TOKEN in stored["sync"])
    A.check("the token never appears in a URL or in pantry-data.json; it only travels as the Authorization header",
            all(TOKEN not in r["url"] and TOKEN not in (r["body"] or "") for r in mock.requests)
            and all(TOKEN not in json.dumps(p.get("doc")) for p in mock.puts) and TOKEN not in mock.text
            and all(r["auth"] == f"Bearer {TOKEN}" for r in mock.requests))
    mask = page.locator('[data-test="token-mask"]').inner_text().strip()
    A.check("Settings shows the token masked and nowhere in the page", TOKEN not in page.content()
            and mask == "github_pat_••••" + TOKEN[-4:], mask)
    pill = page.locator('[data-test="sync-pill"]').inner_text().strip()
    last = page.locator('[data-test="sync-last"]').inner_text().strip()
    A.check("Settings says Synced, just now", pill == "Synced" and last == "Just now", (pill, last))
    history = page.locator('[data-test="history"]').inner_text()
    days = page.locator('[data-test="history-days"]').inner_text().strip()
    foods = page.locator('[data-test="foods"]').inner_text()
    A.check("Settings shows the days logged (3 MyNetDiary days; the phone's own entries are on 20 Oct, a MyNetDiary day) "
            "with their range, and the foods",
            "8 Aug 2026 to 20 Oct 2026" in history and days == "3" and foods.strip().endswith("11"), (history, foods))
    A.fits(page, "Settings, synced, 150 % text")

    # an edit made while a push is in flight survives
    page.evaluate(EDIT_DURING_PUT)
    page.evaluate(ADD, ["2026-10-20-ptest3", 120])
    ok = pushed(page, mock, 2, 40)
    sent = {e["id"]: e for e in mock.doc()["entries"]}
    here = {e["id"]: e for e in doc(page)["entries"]}
    A.check("an edit made while a push is in flight keeps the phone dirty; the push carried the state from before it",
            ok and page.evaluate("() => Pantry.dirty()") is True and sent["2026-10-20-ptest1"]["amount"] == "350 g"
            and "2026-10-20-ptest3" in sent and here["2026-10-20-ptest1"]["amount"] == "400 g",
            (ok, sent["2026-10-20-ptest1"]["amount"], here["2026-10-20-ptest1"]["amount"]))
    pizza = next(f for f in remote["foods"] if "Pizza" in f["name"])
    other = mock.doc()
    other["entries"].append(entry("2026-10-20-pother1", pizza, 100))
    mock.store(other)                                         # another device pushed; its copy of ptest1 is still 350 g
    foreground(page)
    wait_until(page, lambda: has(page, "2026-10-20-pother1"), 20)
    idle(page)
    here = {e["id"]: e for e in doc(page)["entries"]}
    A.check("the next pull keeps the edit (and brings the other device's entry)",
            here["2026-10-20-ptest1"]["amount"] == "400 g" and here["2026-10-20-ptest1"]["grams"] == 400 and "2026-10-20-pother1" in here,
            here["2026-10-20-ptest1"]["amount"])
    ok = pushed(page, mock, 3, 40)
    sent = {e["id"]: e for e in mock.doc()["entries"]}
    A.check("then the edit reaches the repo next to the other device's entry",
            ok and sent["2026-10-20-ptest1"]["amount"] == "400 g" and "2026-10-20-pother1" in sent and page.evaluate("() => Pantry.dirty()") is False)

    # deletions: on the phone (doc.removed) and in the repo (its removed)
    on_phone = next(e["id"] for e in remote["entries"] if e["date"] == "2026-08-08" and e["meal"] == "breakfast")
    in_repo = next(e["id"] for e in remote["entries"] if e["date"] == "2026-08-08" and e["meal"] == "lunch")
    page.evaluate(DELETE, on_phone)
    other = mock.doc()
    other["entries"].append(entry("2026-10-20-pother2", pizza, 50))
    mock.store(other)                                         # the repo moved on and still has the deleted entry
    foreground(page)
    wait_until(page, lambda: has(page, "2026-10-20-pother2"), 20)
    idle(page)
    A.check("an entry deleted on the phone (in doc.removed) stays deleted after a pull from a repo that still has it",
            on_phone not in ids(doc(page)) and on_phone in ids(mock.doc()) and "2026-10-20-pother2" in ids(doc(page)))
    other = mock.doc()
    other["entries"] = [e for e in other["entries"] if e["id"] != in_repo]
    other.setdefault("removed", []).append({"id": in_repo, "at": "2026-10-20T06:00:00+09:30"})
    mock.store(other)
    foreground(page)
    wait_until(page, lambda: not has(page, in_repo), 20)
    idle(page)
    A.check("an entry deleted in the repo's removed disappears from the phone after a pull", in_repo not in ids(doc(page)))
    ok = pushed(page, mock, 4, 40)
    repo = mock.doc()
    A.check("after the push the repo has neither deleted entry and lists both in removed",
            ok and on_phone not in ids(repo) and in_repo not in ids(repo)
            and {on_phone, in_repo} <= {r["id"] for r in repo.get("removed", [])}, repo.get("removed"))

    # offline: the change waits; back online it is pushed with the sha it read; a 409 makes it pull, merge, push again
    requests_before = len(mock.requests)
    ctx.set_offline(True)
    page.evaluate(ADD, ["2026-10-20-ptest4", 80])
    page.wait_for_timeout(11500)
    st = state(page)
    A.check("offline, a change waits on the phone: no call to GitHub, no banner, still dirty",
            len(mock.requests) == requests_before and st.get("lastError") is None and st.get("dirty") is True,
            (len(mock.requests) - requests_before, st.get("lastError")))
    read_sha = st.get("sha")
    n = len(mock.puts)

    def another_device(m):
        d = m.doc()
        d["entries"].append(entry("2026-10-20-pother3", pizza, 30))
        m.store(d)
    mock.before_put = another_device
    ctx.set_offline(False)
    ok = pushed(page, mock, n + 2, 40)
    tail = mock.puts[n:]
    repo = mock.doc()
    A.check("back online the waiting change is pushed with the sha it read", tail and read_sha and tail[0]["sha"] == read_sha,
            [(p.get("status"), p["sha"]) for p in tail])
    A.check("a 409 makes it pull, merge and push again, never overwrite",
            ok and tail[0].get("status") == 409 and tail[1].get("status") == 200 and tail[1]["sha"] != read_sha
            and "2026-10-20-pother3" in ids(repo) and "2026-10-20-ptest4" in ids(repo) and repo == doc(page),
            [(p.get("status"), p["sha"][:8] if p["sha"] else None) for p in tail])
    ctx.close()


def check_full(browser, url, errors):
    source = next((p for p in FULL_CANDIDATES if p.is_file()), None)
    if source is None:
        print(f"SKIP first sync with the full history: {FULL_NAME} is not on this machine (looked in "
              + ", ".join(str(p) for p in FULL_CANDIDATES) + ")")
        return
    remote = build_remote(source, "full")
    size = len((json.dumps(remote, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    print(f"     (full history: {len(remote['entries']):,} entries, {size:,} bytes)")
    ctx, page, mock = first_sync(browser, url, errors, remote, "full history")
    raw = [r for r in mock.requests if r["method"] == "GET" and "raw" in r["accept"]]
    A.check("full history: the document above 1 MB was read through the raw media type", size > LIMIT and raw, (size, len(raw)))
    history = page.locator('[data-test="history"]').inner_text()
    days = page.locator('[data-test="history-days"]').inner_text().strip()
    A.check('full history: Settings shows 14 Jul 2025 to 20 Oct 2026 and reads exactly "464" days logged',
            "14 Jul 2025 to 20 Oct 2026" in history and days == "464", (history, days))
    ctx.close()


def check_large(browser, url, errors, remote):
    """A repo file above 1 MB: sha through the object media type, text through the raw media type."""
    big = copy.deepcopy(remote)
    model = big["entries"][0]
    i = 0
    while len(json.dumps(big, separators=(",", ":")).encode("utf-8")) <= LIMIT + 50000:
        for _ in range(200):
            big["entries"].append({**model, "id": f"2026-01-{1 + i % 28:02d}-p{i:06d}", "date": f"2026-01-{1 + i % 28:02d}"})
            i += 1
    mock = MockGitHub(big)
    big_sha = mock.sha
    ctx, page = phone(browser, errors, "large", mock)
    A.open_today(page, url)
    probe = page.evaluate("""async ([url, token]) => { const r = await fetch(url, { headers: { Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json' } }); const j = await r.json(); return { content: j.content, encoding: j.encoding, size: j.size }; }""",
                          [CONTENTS_URL, TOKEN])
    A.check("the mock answers the default media type above 1 MB as GitHub does: no content",
            probe["content"] == "" and probe["encoding"] == "none" and probe["size"] > LIMIT, {k: probe[k] for k in ("encoding", "size")})
    mock.requests.clear()
    configure(page, url)
    ok = pushed(page, mock, 1, 40)
    gets = [r for r in mock.requests if r["method"] == "GET" and r["url"].startswith(CONTENTS_URL)]
    A.check("a remote file above 1 MB: its sha through the object media type, its text through the raw media type",
            len(gets) >= 2 and gets[0]["accept"] == "application/vnd.github.object+json"
            and gets[1]["accept"] == "application/vnd.github.raw+json", [g["accept"] for g in gets])
    d = doc(page)
    A.check("after a >1 MB pull the phone holds every entry, and its push sends the sha read through the object media type",
            ok and len(d["entries"]) == len(big["entries"]) and mock.puts[0]["sha"] == big_sha, (len(d["entries"]), len(big["entries"])))
    st = state(page)
    pill = page.locator('[data-test="sync-pill"]').inner_text().strip()
    A.check("the empty answer above 1 MB is never shown as a token problem", st.get("lastError") is None and pill == "Synced"
            and page.locator('[data-test="sync-reason"]').count() == 0, (st.get("lastError"), pill))
    ctx.close()


def check_missing_file(browser, url, errors, remote):
    """No pantry-data.json yet: the phone creates it; if another device creates it first, the phone merges, never overwrites."""
    mock = MockGitHub()

    def another_device(m):
        m.store(remote)
    mock.before_put = another_device
    ctx, page = phone(browser, errors, "missing", mock)
    A.open_today(page, url)
    configure(page, url)
    ok = pushed(page, mock, 2, 30)
    repo = mock.doc()
    A.check("a file created by another device after it was read as missing is merged, not overwritten (422, pull, push with its sha)",
            ok and [p.get("status") for p in mock.puts] == [422, 200] and mock.puts[0]["sha"] is None and mock.puts[1]["sha"]
            and len(repo["entries"]) == len(remote["entries"]) and set(STARTER_IDS) <= {f["id"] for f in repo["foods"]}
            and repo == doc(page) and state(page).get("lastError") is None, [(p.get("status"), p["sha"]) for p in mock.puts])
    ctx.close()


def check_refused(browser, url, errors, remote):
    """A bad or expired token: the banner sentence for Today, a plain reason in Settings, the phone's log untouched."""
    cases = [("401", EXPIRED, None, "may have expired"),
             ("403", TOKEN, 403, "Contents read and write"),
             ("404", TOKEN, 404, "cannot see Estaed/Pantry-Data")]
    for status, token, mode, words in cases:
        mock = MockGitHub(remote)
        mock.mode = mode
        ctx, page = phone(browser, errors, f"refused-{status}", mock)
        A.open_today(page, url)
        page.evaluate(OWN)
        before = doc(page)
        configure(page, url, token)
        wait_until(page, lambda: state(page).get("lastError"), 20)
        idle(page)
        st = state(page)
        error = st.get("lastError") or ""
        A.check(f"{status}: lastError is the banner sentence with the likely cause",
                error.startswith(PREFIX) and words in error and error.endswith("Settings, Sync."), error)
        A.check(f"{status}: the local document is untouched and still marked dirty",
                doc(page) == before and page.evaluate("() => Pantry.dirty()") is True and not mock.puts)
        reason = page.locator('[data-test="sync-reason"]')
        pill = page.locator('[data-test="sync-pill"]').inner_text().strip()
        A.check(f"{status}: Settings shows Failed and a plain reason",
                reason.count() == 1 and words in reason.inner_text() and "Sync failed" not in reason.inner_text() and pill == "Failed",
                (pill, reason.inner_text() if reason.count() else None))
        if status == "401":
            A.fits(page, "Settings, sync failed, 150 % text")
            page.goto(url + "#/")
            page.wait_for_selector('[data-screen="today"]')
            banner = page.locator('[data-screen="today"] .banner')
            if banner.count():
                A.check("401: Today shows the sync banner", "Sync failed" in banner.inner_text(), banner.inner_text())
            else:
                print("SKIP 401: Today's sync banner: the Today in this tree does not draw it yet (Task-02 draws it from lastError)")
        ctx.close()

    mock = MockGitHub(remote)
    mock.readonly = True
    ctx, page = phone(browser, errors, "refused-readonly", mock)
    A.open_today(page, url)
    page.evaluate(OWN)
    configure(page, url)
    wait_until(page, lambda: state(page).get("lastError"), 30)
    idle(page)
    error = state(page).get("lastError") or ""
    d = doc(page)
    A.check("a token that can read but not write: lastError says so, the own entries stay, still dirty",
            error.startswith(PREFIX) and "cannot write to Estaed/Pantry-Data" in error and set(OWN_IDS) <= set(ids(d))
            and page.evaluate("() => Pantry.dirty()") is True and mock.puts and mock.puts[0]["status"] == 403, error)
    ctx.close()


def check_targets(browser, url, errors, remote):
    mock = MockGitHub(remote)
    ctx, page = phone(browser, errors, "targets", mock)
    A.open_today(page, url)
    configure(page, url)
    pushed(page, mock, 1, 30)                                  # the merge adds the starter foods the repo lacks

    page.get_by_role("button", name="Daily calories").click()
    page.get_by_label("Daily calories").fill("2,000")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_role("button", name="Macro split").click()
    page.get_by_label("Protein").fill("25")
    page.get_by_label("Carbs").fill("40")
    page.get_by_label("Fat").fill("30")
    page.get_by_role("button", name="Save", exact=True).click()
    err = page.locator('[data-form="macro"] [data-err]')
    A.check("a macro split that does not make 100 % is refused with a plain message, nothing saved",
            err.is_visible() and "95 %" in err.inner_text() and doc(page)["settings"]["targets"]["proteinPct"] == 20, err.inner_text())
    A.fits(page, "Settings, macro editor with its error, 150 % text")
    page.get_by_label("Protein").fill("33.33")
    page.get_by_label("Carbs").fill("33.33")
    page.get_by_label("Fat").fill("33.34")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_role("button", name="Macro split").click()
    page.get_by_role("button", name="Save", exact=True).click()      # saved again unchanged
    t = doc(page)["settings"]["targets"]
    split = [t["proteinPct"], t["carbsPct"], t["fatPct"]]
    A.check("a split typed with two decimals is kept as typed (still 100 %) and saves again unchanged",
            split == [33.33, 33.33, 33.34] and page.locator('[data-form="macro"]').count() == 0, split)
    page.get_by_role("button", name="Macro split").click()
    page.get_by_label("Protein").fill("25")
    page.get_by_label("Carbs").fill("40")
    page.get_by_label("Fat").fill("35")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_role("button", name="Salt").click()
    page.get_by_label("Salt").fill("6,5")
    page.get_by_label("Salt").press("Enter")
    rows = [t.strip() for t in page.locator('[data-part="targets"] .settings-v').all_inner_texts()]
    targets = doc(page)["settings"]["targets"]
    want = {"kcal": 2000, "proteinPct": 25, "carbsPct": 40, "fatPct": 35, "salt": 6.5}
    A.check("Settings saves the targets typed (2,000 kcal; protein 25, carbs 40, fat 35 %, shown carbs first: "
            "40 / 25 / 35 %; 6,5 g read as 6.5)",
            targets == want and rows == ["2,000 kcal", "40 / 25 / 35%", "6.5 g"], (targets, rows))
    puts = len(mock.puts)
    page.goto(url + "#/")
    page.wait_for_selector('[data-screen="today"] [data-test="kcal-left"]')
    eaten = round(sum(e["totals"]["kcal"] for e in doc(page)["entries"] if e["date"] == TODAY))
    A.check("Today's kcal budget follows the new target", A.kcal_left(page) == f"{2000 - eaten:,}", (A.kcal_left(page), 2000 - eaten))

    other = mock.doc()                                        # another device pushes with the old targets
    other["entries"].append(entry("2026-10-20-pother9", next(f for f in remote["foods"] if "Pizza" in f["name"]), 40))
    other["settings"] = {"targets": dict(A.TARGETS)}
    mock.store(other)
    foreground(page)
    wait_until(page, lambda: has(page, "2026-10-20-pother9"), 20)
    idle(page)
    A.check("a later pull with the repo's old targets does not undo them (the push was still waiting)",
            len(mock.puts) == puts and doc(page)["settings"]["targets"] == want, (len(mock.puts) - puts, doc(page)["settings"]))
    ok = pushed(page, mock, puts + 1, 30)
    A.check("the new targets are synced", ok and mock.doc()["settings"]["targets"] == want, mock.doc()["settings"])
    ctx.close()


def days_doc(imported, own):
    """Synthetic: one MyNetDiary-shaped entry (id <date>-<n>, as the import names them) per imported day, one
    Pantry-shaped entry (id <date>-p<x>) per own day."""
    entries = [{"id": f"{d}-101", "date": d, "meal": "lunch", "foodId": POTATO, "amount": "100 g", "grams": 100,
                "totals": {"kcal": 59}} for d in imported]
    entries += [{"id": f"{d}-ptest{i}", "date": d, "meal": "dinner", "foodId": POTATO, "amount": "100 g", "grams": 100,
                 "totals": {"kcal": 59}} for i, d in enumerate(own)]
    return {"version": 1, "foods": [], "entries": entries, "settings": {"targets": dict(A.TARGETS)}}


def check_days(browser, url, errors, remote):
    """Task-07: the history row counts every logged day, "M (+P)": M MyNetDiary days, P days logged only in Pantry."""
    ctx, page = phone(browser, errors, "days", MockGitHub(), text=1.0)
    A.open_today(page, url)
    open_settings(page, url)
    start = datetime.date(2025, 7, 14)
    full = [(start + datetime.timedelta(days=i)).isoformat() for i in range(464)]
    cases = [("an empty log", [], [], "0", ["None on this phone yet"]),
             ("a 464-day import", full, [], "464", ["MyNetDiary", "14 Jul 2025 to 20 Oct 2026"]),
             ("three days logged only in Pantry, no import (a new user)", [], ["2026-10-18", "2026-10-19", "2026-10-21"], "3",
              ["18 Oct 2026 to 21 Oct 2026"]),
             ("the import plus two Pantry-only days and one more Pantry entry on 20 Oct (a MyNetDiary day)", full,
              ["2026-10-21", "2026-10-22", "2026-10-20"], "464 (+2)", ["MyNetDiary (+ Pantry only)", "14 Jul 2025 to 22 Oct 2026"])]
    for label, imported, own, count, subs in cases:
        page.evaluate("d => { Pantry.change(() => d, { dirty: false }); }", days_doc(imported, own))
        got = page.locator('[data-test="history-days"]').inner_text().strip()
        lines = page.locator('[data-test="history"] .settings-sub').evaluate_all("els => els.map(e => e.textContent.trim())")
        A.check(f'Settings, {label}: the days logged read exactly "{count}" ({", ".join(subs)})', got == count and lines == subs,
                (got, lines))
    beside = """() => { const n = document.querySelector('[data-test="history"] .settings-t').getBoundingClientRect(),
        v = document.querySelector('[data-test="history-days"]').getBoundingClientRect(); return v.left >= n.right - 0.5 && v.top < n.bottom; }"""
    wide = page.evaluate(beside)
    A.fits(page, "Settings with 464 (+2) days logged, 360 px, text 1.0")
    page.set_viewport_size({"width": 240, "height": 520})
    narrow = page.evaluate(beside)
    A.fits(page, "Settings with 464 (+2) days logged, 240 px")
    A.check("the count stays beside 'Days logged' at 360 px and at 240 px; the lines under the name wrap instead", wide and narrow,
            (wide, narrow))
    ctx.close()


def check_own_repo(browser, url, errors, remote):
    """2026-10-24, public: a new user names their own private repo; nothing on their phone points at Estaed."""
    mock = MockGitHub(repo="alex-k/my-pantry.data")
    ctx, page = phone(browser, errors, "own-repo", mock, text=1.0)
    A.open_today(page, url)
    open_settings(page, url)
    shown = page.locator('[data-screen="settings"]').inner_text()
    A.check("a new phone's Settings names no repo of Tarik's: the repo row says it is not connected, the repo field is empty",
            "Estaed" not in shown and "Not connected" in shown and page.get_by_label("Data repo").input_value() == "", shown[:400])
    for typed in ("", "my-pantry", "alex-k/my pantry"):
        page.get_by_label("Data repo").fill(typed)
        page.get_by_label("GitHub token").fill(TOKEN)
        page.get_by_role("button", name="Save and sync").click()
        err = page.locator('[data-form="token"] [data-err]')
        A.check(f"a data repo typed as {typed!r} is refused in plain words, nothing stored",
                err.is_visible() and "owner/name" in err.inner_text() and not state(page).get("token") and not mock.requests,
                (err.inner_text(), state(page)))
    page.evaluate(OWN)
    configure(page, url, repo="https://github.com/alex-k/my-pantry.data.git")
    pushed(page, mock, 1, 30)
    paths = {urllib.parse.urlsplit(r["url"]).path for r in mock.requests}
    A.check("the repo's github.com address is read as owner/name and stored with the token",
            state(page).get("repo") == "alex-k/my-pantry.data" and state(page).get("token") == TOKEN, state(page))
    A.check("every GitHub call goes to that repo, the first push creates its pantry-data.json with the phone's log",
            paths <= {mock.repo_path, mock.repo_path + "/contents/pantry-data.json"} and mock.doc() == doc(page)
            and set(OWN_IDS) <= set(ids(mock.doc())), sorted(paths))
    sub = page.locator('[data-screen="settings"] [data-part="status"] .settings-sub').first.inner_text().strip()
    A.check("Settings then shows the repo in use", sub == "alex-k/my-pantry.data, private", sub)
    page.get_by_role("button", name="Replace").click()
    A.check("Replace keeps the repo filled in, so only the token has to be pasted again",
            page.get_by_label("Data repo").input_value() == "alex-k/my-pantry.data")
    ctx.close()

    mock = MockGitHub(repo="alex-k/my-pantry.data")
    mock.mode = 404
    ctx, page = phone(browser, errors, "own-repo-404", mock, text=1.0)
    A.open_today(page, url)
    configure(page, url, repo="alex-k/my-pantry.data")
    wait_until(page, lambda: state(page).get("lastError"), 20)
    idle(page)
    A.check("a repo the token cannot see is named in the reason, with what to check",
            "cannot see alex-k/my-pantry.data; check the repo name" in (state(page).get("lastCause") or ""), state(page))
    ctx.close()


def check_first_repo(browser, url, errors, remote):
    """Tarik's phone, connected before the repo was a setting: 'pantry.sync' holds a token and no repo. It keeps
    syncing with Estaed/Pantry-Data, and opening the new version rewrites neither its log nor its sync state."""
    mock = MockGitHub(remote)
    log = json.dumps(remote, ensure_ascii=False, separators=(",", ":"))
    sync = json.dumps({"token": TOKEN, "sha": mock.sha, "lastSync": "2026-10-20T06:00:00.000Z", "dirty": False,
                       "changes": 0, "changed": {"entries": {}, "foods": {}}})
    ctx, page = phone(browser, errors, "first-repo", mock, text=1.0)
    ctx.add_init_script("""(() => { const [log, sync] = %s; if (localStorage.getItem('pantry.v1') === null) {
        localStorage.setItem('pantry.v1', log); localStorage.setItem('pantry.sync', sync); } })()""" % json.dumps([log, sync]))
    A.open_today(page, url)
    wait_until(page, lambda: any(r["method"] == "GET" for r in mock.requests), 20)
    idle(page)
    raw = page.evaluate("() => ({ log: localStorage.getItem('pantry.v1'), sync: JSON.parse(localStorage.getItem('pantry.sync')) })")
    paths = {urllib.parse.urlsplit(r["url"]).path for r in mock.requests}
    A.check("an existing phone with no repo in its sync state syncs with Estaed/Pantry-Data and finds it the same",
            paths == {CONTENTS_PATH} and not mock.puts and raw["sync"].get("lastError") is None, (sorted(paths), mock.puts))
    A.check("its stored log is byte for byte what it was, and no repo key is written into its sync state (no migration)",
            raw["log"] == log and "repo" not in raw["sync"] and raw["sync"]["token"] == TOKEN, sorted(raw["sync"]))
    open_settings(page, url)
    sub = page.locator('[data-screen="settings"] [data-part="status"] .settings-sub').first.inner_text().strip()
    A.check("its Settings shows Estaed/Pantry-Data and the masked token as before",
            sub == "Estaed/Pantry-Data, private" and page.locator('[data-test="token-mask"]').count() == 1, sub)
    page.get_by_role("button", name="Replace").click()
    A.check("Replace there starts from Estaed/Pantry-Data", page.get_by_label("Data repo").input_value() == FIRST_REPO)
    page.evaluate(OWN)
    pushed(page, mock, 1, 30)
    A.check("a new entry on that phone is pushed to Estaed/Pantry-Data, merged with what was there",
            set(OWN_IDS) <= set(ids(mock.doc())) and set(ids(remote)) <= set(ids(mock.doc())) and mock.doc() == doc(page))
    ctx.close()


def check_macro_order(browser, url, errors, remote):
    """Task-07: the split is read and typed carbs, protein, fat; the stored targets keep their shape."""
    ctx, page = phone(browser, errors, "macro-order", MockGitHub(), text=1.0)
    A.open_today(page, url)
    wave2 = {"kcal": 2200, "proteinPct": 20, "carbsPct": 45, "fatPct": 35, "salt": 5.8}
    page.evaluate("t => { Pantry.change(d => { d.settings = { targets: t }; }, { dirty: false }); }", wave2)
    open_settings(page, url)
    row = page.locator('[data-kind="macro"]')
    shown = (row.locator(".settings-sub").inner_text().strip(), row.locator(".settings-v").inner_text().strip())
    row.click()
    form = page.locator('[data-form="macro"]')
    pairs = form.locator(".settings-pair").evaluate_all("els => els.map(e => [e.querySelector('label').textContent, e.querySelector('input').value])")
    help_line = form.locator("[data-help]").inner_text().strip()
    A.check("a document saved by wave 2 (protein 20, carbs 45, fat 35) shows its split carbs, protein, fat: the row "
            "reads 45 / 20 / 35 %, the editor's fields and its grams line follow that order",
            shown == ("Carbs, protein, fat", "45 / 20 / 35%") and pairs == [["Carbs", "45"], ["Protein", "20"], ["Fat", "35"]]
            and help_line == "At 2,200 kcal: 248 g carbs, 110 g protein, 86 g fat.", (shown, pairs, help_line))
    form.get_by_role("button", name="Save", exact=True).click()
    t = doc(page)["settings"]["targets"]
    A.check("saving it unchanged keeps settings.targets deep-equal and in the same shape (key order)",
            t == wave2 and list(t) == list(wave2), t)
    row.click()
    page.get_by_label("Carbs").fill("50")
    page.get_by_label("Protein").fill("30")
    page.get_by_label("Fat").fill("20")
    form.get_by_role("button", name="Save", exact=True).click()
    t = doc(page)["settings"]["targets"]
    A.check("typed carbs 50, protein 30, fat 20 are stored under carbsPct, proteinPct, fatPct",
            (t["carbsPct"], t["proteinPct"], t["fatPct"]) == (50, 30, 20) and list(t) == list(wave2), t)
    ctx.close()


def check_screen(browser, url, errors, remote):
    """Settings at 360 x 780 with text at 150 % and at 240 px, dark and light, every text in rem."""
    mock = MockGitHub(remote)
    ctx, page = phone(browser, errors, "screen", mock, text=1.0)
    A.open_today(page, url)
    open_settings(page, url)
    sizes100 = page.evaluate(A.TEXT_SIZES_JS)
    A.set_text(page, A.BIG_TEXT)
    A.reload_to(page, "settings")
    sizes150 = page.evaluate(A.TEXT_SIZES_JS)
    flat = [a[0] for a, b in zip(sizes100, sizes150) if b[1] < 1.45 * a[1]]
    A.check("every text on Settings grows with the text size (rem, no px font sizes)",
            sizes100 and len(sizes100) == len(sizes150) and not flat, flat or (len(sizes100), len(sizes150)))
    A.fits(page, "Settings, no token yet, 150 % text")
    page.get_by_label("Data repo").fill(FIRST_REPO)
    page.get_by_label("GitHub token").fill("not a token")
    page.get_by_role("button", name="Save and sync").click()
    err = page.locator('[data-form="token"] [data-err]')
    A.check("a pasted text that is not a GitHub token is refused in plain words, nothing stored",
            err.is_visible() and "github_pat_" in err.inner_text() and not state(page).get("token"), err.inner_text())

    shots = {}
    for scheme in ("dark", "light"):
        page.emulate_media(color_scheme=scheme)
        A.reload_to(page, "settings")
        shots[scheme] = page.evaluate("""() => ({ theme: document.documentElement.dataset.theme,
            canvas: getComputedStyle(document.body).backgroundColor, ink: getComputedStyle(document.querySelector('.title')).color })""")
        page.screenshot(path=str(WORK / f"settings-{scheme}.png"), full_page=True)
    A.check("Settings renders in dark and in light (theme follows the phone; canvas and ink differ)",
            shots["dark"]["theme"] == "dark" and shots["light"]["theme"] == "light"
            and shots["dark"]["canvas"] != shots["light"]["canvas"] and shots["dark"]["ink"] != shots["light"]["ink"], shots)

    A.set_text(page, 1.0)
    page.set_viewport_size({"width": 240, "height": 520})
    A.reload_to(page, "settings")
    A.fits(page, "Settings at 240 px (150 % page zoom), no token yet")
    page.get_by_role("button", name="Macro split").click()
    A.fits(page, "Settings at 240 px, macro editor open")
    page.get_by_label("Data repo").fill(FIRST_REPO)
    page.get_by_label("GitHub token").fill(TOKEN)
    page.get_by_role("button", name="Save and sync").click()
    pushed(page, mock, 1, 30)
    A.fits(page, "Settings at 240 px, synced")
    page.screenshot(path=str(WORK / "settings-240.png"), full_page=True)
    ctx.close()


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    srv, site, url = A.start_site()
    install(site)
    errors = []
    try:
        remote = build_remote(FIXTURE, "slice")
        A.check("the repo document from the fixture holds 9 entries and 7 foods, the potato among them",
                len(remote["entries"]) == 9 and len(remote["foods"]) == 7 and any(f["id"] == POTATO for f in remote["foods"]))
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn, args in (("merge rules", check_merge_rules, (remote,)), ("slice sync", check_slice, (remote,)),
                                   ("large file", check_large, (remote,)), ("missing file", check_missing_file, (remote,)),
                                   ("refused token", check_refused, (remote,)),
                                   ("targets", check_targets, (remote,)), ("days logged", check_days, (remote,)),
                                   ("macro order", check_macro_order, (remote,)), ("screen", check_screen, (remote,)),
                                   ("own repo", check_own_repo, (remote,)), ("first repo", check_first_repo, (remote,)),
                                   ("full history", check_full, ())):
                A.guarded(name, fn, browser, url, errors, *args)
            browser.close()
        A.check("no console errors or page errors", not errors, "\n".join(errors[:10]))
    finally:
        srv.shutdown()
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

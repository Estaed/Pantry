"""Checks for the shared seams in app/core.js that wave-2 features build on.

Run from the repo root: python tests/test_core.py   (exit 0 = no FAIL). Reuses the gate's server and phone from
tests/acceptance.py. Synthetic entries are built in the page to exercise a rule; nothing personal is stored.
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acceptance as A  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

CHICKEN = A.json.loads('"v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao="')


def entry(i, date, meal, amount, grams):
    return {"id": f"t{i}", "date": date, "meal": meal, "foodId": CHICKEN, "amount": amount, "grams": grams, "totals": {"kcal": 1}}


def main():
    srv, site, url = A.start_site()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx, page = A.phone(browser, errors, "core")
        A.open_today(page, url)

        A.check("mealNow follows the clock (07:00 is breakfast)", page.evaluate("Pantry.mealNow()") == "breakfast")

        # usualAmounts: most typed at that meal within 90 days wins over the latest; older or other meals fall back
        entries = [entry(1, "2026-10-01", "dinner", "350 g", 350), entry(2, "2026-10-05", "dinner", "350 g", 350),
                   entry(3, "2026-10-19", "dinner", "375 g", 375), entry(4, "2026-01-01", "dinner", "999 g", 999),
                   entry(5, "2026-10-18", "lunch", "200 g", 200)]
        page.evaluate("es => Pantry.change(d => { d.entries.push(...es); })", entries)
        got = page.evaluate(f"Pantry.usualAmounts({A.json.dumps(CHICKEN)}, 'dinner')")
        A.check("usualAmounts ranks the most typed amount at that meal first, within 90 days",
                [g["amount"] for g in got] == ["350 g", "375 g"], got)
        got = page.evaluate(f"Pantry.usualAmounts({A.json.dumps(CHICKEN)}, 'snacks')")
        A.check("usualAmounts falls back to any meal when the meal has none", got and got[0]["amount"] in ("350 g", "999 g", "375 g", "200 g"), got)
        got = page.evaluate("Pantry.usualAmounts('v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg=', 'dinner')")
        A.check("usualAmounts falls back to the starter's usual grams", got == [{"amount": "500 g", "grams": 500, "count": 0}], got)

        # markClean(upTo): a change during a push keeps the document dirty
        page.evaluate("Pantry.change(d => { d.entries.push({id:'t9',date:'2026-10-20',meal:'lunch',foodId:'x',amount:'1 g',grams:1,totals:{kcal:1}}); })")
        before = page.evaluate("Pantry.changes()")
        page.evaluate("Pantry.change(d => { d.entries[d.entries.length - 1].amount = '2 g'; })")
        page.evaluate(f"Pantry.markClean({before})")
        A.check("markClean(upTo) keeps it dirty when a change happened during the push", page.evaluate("Pantry.dirty()") is True)
        page.evaluate("Pantry.markClean(Pantry.changes())")
        A.check("markClean(upTo) clears it when nothing changed since", page.evaluate("Pantry.dirty()") is False)

        # subscribe gets prev on change; setSyncState announces 'sync'
        seen = page.evaluate("""() => {
            window.__seen = [];
            Pantry.subscribe((doc, why, prev) => __seen.push([why, prev ? prev.entries.length : null, doc.entries.length]));
            Pantry.change(d => { d.entries.pop(); });
            Pantry.setSyncState({ lastError: null });
            return __seen;
        }""")
        A.check("subscribers get the previous document on a change", seen[0][0] == "change" and seen[0][1] == seen[0][2] + 1, seen)
        A.check("setSyncState announces 'sync'", any(s[0] == "sync" for s in seen), seen)

        # check(): removed and catalogue must be well formed when present
        bad = page.evaluate("() => { try { Pantry.change(d => { d.removed = [{ id: 7 }]; }); return 'saved'; } catch (e) { return e.message; } }")
        A.check("a malformed removed list is refused", bad != "saved", bad)
        ok = page.evaluate("() => { Pantry.change(d => { d.removed = [{ id: 't1', at: '2026-10-20T07:00:00Z' }]; }); return Pantry.doc().removed.length; }")
        A.check("a well-formed removed list saves", ok == 1, ok)
        bad = page.evaluate("() => { try { Pantry.change(d => { d.catalogue = [{ barcode: '1', name: 'x', store: 'aldi', per100: { kcal: 1 } }]; }); return 'saved'; } catch (e) { return e.message; } }")
        A.check("a catalogue item from an unknown store is refused", bad != "saved", bad)

        # routes: undefined args become empty segments; unknown routes open Today without args
        page.evaluate("Pantry.view('probeargs', { render(root, ...a) { window.__args = a; root.textContent = 'probe'; } })")
        page.evaluate("Pantry.go('probeargs', undefined, '2026-08-08')")
        page.wait_for_selector('[data-screen="probeargs"]')
        A.check("an undefined route arg arrives as undefined, the next one intact",
                page.evaluate("JSON.stringify(__args)") == '[null,"2026-08-08"]', page.evaluate("JSON.stringify(__args)"))
        page.evaluate("location.hash = '#/nosuchscreen/abc'")
        page.wait_for_selector('[data-screen="today"]')
        A.check("an unknown route opens Today", page.locator('[data-screen="today"]').count() == 1)

        # toast: survives a screen change, Undo runs its action
        page.evaluate("() => { window.__undone = 0; Pantry.toast('350 g added to dinner', { action: 'Undo', onAction: () => { __undone += 1; } }); }")
        page.evaluate("Pantry.go('probeargs')")
        page.wait_for_selector('[data-screen="probeargs"]')
        A.check("a toast survives a screen change", page.locator("#toast .toast").count() == 1)
        page.get_by_role("button", name="Undo").click()
        A.check("the toast's action runs and the toast closes", page.evaluate("__undone") == 1 and page.locator("#toast .toast").count() == 0)

        A.check("no console errors or page errors", not errors, errors)
        browser.close()
    srv.shutdown()
    print(f"{len(A.FAILS)} failed")
    return 1 if A.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

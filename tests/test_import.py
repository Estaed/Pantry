"""Gate for Task-01: tools/import_mynetdiary.py.

Run from the repo root: python tests/test_import.py   (exit 0 = no FAIL; prints PASS, FAIL or SKIP per check)

The committed fixture (tests/fixtures/mynetdiary-slice.json, three real days) is checked always. The
full history, references/mynetdiary-history-2026-10-20.json, is gitignored personal data: when it is
present (or MYNETDIARY_SOURCE points at it) the full-source checks run, otherwise they SKIP and say so.
Outputs go to .tmp/ when git ignores it, else to a temp folder outside the repo; both are removed.
Expected values come from the source itself, from Task-00's starter foods and from hand-worked numbers,
never from the tool.
"""

import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # importing the tool must leave no __pycache__ in the repo

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "import_mynetdiary.py"
FIXTURE = ROOT / "tests" / "fixtures" / "mynetdiary-slice.json"
FULL = Path(os.environ.get("MYNETDIARY_SOURCE") or ROOT / "references" / "mynetdiary-history-2026-10-20.json")

MEALS = {"Breakfast": "breakfast", "Lunch": "lunch", "Dinner": "dinner", "Snacks": "snacks"}
TARGETS = {"targets": {"kcal": 2200, "proteinPct": 20, "carbsPct": 45, "fatPct": 35, "salt": 5.8}}
FOOD_KEYS = {"id", "name", "brand", "barcode", "per100", "servings", "source"}
ENTRY_KEYS = ["id", "date", "meal", "foodId", "amount", "grams", "totals"]
POTATO = "v1.iDrOYS8VTR3WqlsjSmhKQquNuENy*Ye3zEYbkuAybx6Agegqo+nWunqLTjg="
PIZZA = "v1.AaXrHp8yjLLkNvxwp*PVeve4n8ReQ5gN1xHHGpCvIk88t8oOJ+Wfj9PyCY4="
ROY_ROGERS = "v1.L1aeZ4jJ7z9D03z0RtXaO4j2DZBMQBEm*Qx0u8GJHBbq1MMvKI1jOH55HtE="
BUTTER = "v1.aKW*42YP1j2TAk0bfGM*EM*zCxIsoQLSdlyVsH9Lzqk1scOD*H2WCHxRDw=="
# Task-00 -> Fixed -> starter foods: per 100 g "as MyNetDiary has them" (butter has no fibre).
STARTERS = {
    "v1.PF**qbOTPRSmP+anKguITLEXtnZfPc3QW7oI1Ut9AHNb8a14BuQaLUsUVao=":
        {"kcal": 108.1, "protein": 20.33, "carbs": 0, "fat": 3.0, "sugars": 0, "satFat": 0.54, "salt": 0.43, "fibre": 0},
    "v1.nWY1wUENSPOyu4Pt9ojJcGQKyXNwC+i8TqtlZmsYpNIdi2IepiE5wgTOo1g=":
        {"kcal": 90.0, "protein": 4.75, "carbs": 12.0, "fat": 3.25, "sugars": 7.25, "satFat": 2.5, "salt": 0.8, "fibre": 2.5},
    "v1.d6DR1H5K+qWQUAWwc3j8qf3M2Hc3hKdn3YcTs5+OuZghSHwXFrx2D3cMe9c=":
        {"kcal": 360.0, "protein": 8.4, "carbs": 80.0, "fat": 0.6, "sugars": 0, "satFat": 0.2, "salt": 0, "fibre": 2.0},
    BUTTER: {"kcal": 616.6, "protein": 20.0, "carbs": 20.0, "fat": 60.0, "sugars": 20.0, "satFat": 28.0, "salt": 1.2},
    POTATO: {"kcal": 59.0, "protein": 2.27, "carbs": 14.8, "fat": 0.13, "sugars": 0.67, "satFat": 0.13, "salt": 0.01, "fibre": 1.87},
}
STARTER_KEYS = ("kcal", "protein", "carbs", "fat", "sugars", "satFat", "salt", "fibre")


class Skip(Exception):
    pass


def git_ignores(path):
    return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--", path]).returncode == 0


def run_tool(source, output):
    """The tool as Tarik runs it: a separate process from the repo root."""
    done = subprocess.run([sys.executable, str(TOOL), str(source), "-o", str(output)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    return done.returncode, done.stdout + done.stderr


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fresh(name):
    folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=WORK))
    return folder


def write_source(folder, source):
    path = folder / "source.json"
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    return path


def summary_value(output, label):
    found = re.search(rf"^\s+{re.escape(label)}:\s+(.+?)\s*$", output, re.M)
    assert found, f"summary has no '{label}:' line:\n{output}"
    return found.group(1)


def entries_of(source):
    return [(day["date"], entry) for day in source["days"] for entry in day["entries"]]


def source_day_sums(source):
    """Per day: kcal, protein, carbs (totalCarbs), fat (totalFat), salt (sodium mg x 2.5 / 1000) and how many entries know each."""
    days = {}
    for date, entry in entries_of(source):
        n = entry["nutrients"]
        values = {"kcal": entry["kcal"], "protein": n.get("protein"), "carbs": n.get("totalCarbs"),
                  "fat": n.get("totalFat"), "salt": n["sodium"] * 2.5 / 1000 if "sodium" in n else None}
        add(days, date, values)
    return days


def doc_day_sums(doc):
    days = {}
    for entry in doc["entries"]:
        add(days, entry["date"], {key: entry["totals"].get(key) for key in ("kcal", "protein", "carbs", "fat", "salt")})
    return days


def add(days, date, values):
    day = days.setdefault(date, {"entries": 0, **{key: [0.0, 0] for key in values}})
    day["entries"] += 1
    for key, value in values.items():
        if value is not None:
            day[key][0] += value
            day[key][1] += 1


def assert_day_sums_match(source, doc):
    want, got = source_day_sums(source), doc_day_sums(doc)
    assert sorted(want) == sorted(got), "the document's days differ from the source's"
    for date in want:
        assert want[date]["entries"] == got[date]["entries"], f"{date}: entry count differs"
        for key in ("kcal", "protein", "carbs", "fat", "salt"):
            limit = 1.0 if key == "kcal" else 0.1
            assert abs(want[date][key][0] - got[date][key][0]) <= limit, \
                f"{date} {key}: document {got[date][key][0]:.3f}, source {want[date][key][0]:.3f}"
            assert want[date][key][1] == got[date][key][1], f"{date} {key}: known on a different number of entries"
    return len(want)


def gram_kcal_per_100(entry):
    gram = next(s for s in entry["servings"] if s["title"] == "gram")
    return round(gram["kcal"] / float(gram["gm"].split()[0]) * 100, 1)


# ---------------------------------------------------------------- fixture checks

FIX = json.loads(FIXTURE.read_text(encoding="utf-8"))
_fixture_run = {}


def fixture_run():
    if not _fixture_run:
        out = fresh("fixture") / "pantry-data.json"
        code, output = run_tool(FIXTURE, out)
        assert code == 0, f"exit {code}:\n{output}"
        _fixture_run.update(out=out, output=output, doc=load(out))
    return _fixture_run


def test_fixture_writes_and_summarises():
    run = fixture_run()
    entries = entries_of(FIX)
    foods = {e["foodId"] for _, e in entries}
    weighed = {e["foodId"] for _, e in entries if e.get("grams") is not None}
    dates = sorted(day["date"] for day in FIX["days"])
    want = {"days": str(len(FIX["days"])), "entries": str(len(entries)), "foods": str(len(foods)),
            "foods without grams": str(len(foods - weighed)), "entries with no nutrients": "0",
            "first date": dates[0], "last date": dates[-1], "days where eaten differs": "0"}
    assert want["foods without grams"] == "1" and want["entries"] == "9", "the fixture itself changed"
    for label, value in want.items():
        assert summary_value(run["output"], label) == value, f"summary {label}: {summary_value(run['output'], label)}, want {value}"
    assert len(run["doc"]["entries"]) == len(entries) and len(run["doc"]["foods"]) == len(foods)


def test_fixture_document_shape():
    doc = fixture_run()["doc"]
    assert list(doc) == ["version", "foods", "entries", "settings"], f"top keys {list(doc)}"
    assert doc["version"] == 1 and doc["settings"] == TARGETS, f"settings {doc['settings']}"
    for food in doc["foods"]:
        assert set(food) <= FOOD_KEYS and {"id", "name", "servings", "source"} <= set(food), f"food keys {list(food)}"
        assert food["source"] == "mynetdiary" and food["servings"], food["name"]
        for serving in food["servings"]:
            assert list(serving) == ["label", "grams", "kcal"], f"{food['name']} serving {serving}"
        if "per100" in food:
            assert all(isinstance(v, (int, float)) for v in food["per100"].values()), food["name"]
    for entry in doc["entries"]:
        assert list(entry) == ENTRY_KEYS, f"entry keys {list(entry)}"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["date"]) and entry["meal"] in MEALS.values()
        assert "kcal" in entry["totals"] and all(isinstance(v, (int, float)) for v in entry["totals"].values()), entry["id"]


def test_fixture_day_sums_match():
    assert_day_sums_match(FIX, fixture_run()["doc"])


def test_fixture_ids_stable():
    run = fixture_run()
    doc = run["doc"]
    assert [f["id"] for f in doc["foods"]] == list(dict.fromkeys(e["foodId"] for _, e in entries_of(FIX)))
    assert [e["id"] for e in doc["entries"]] == [f"{d}-{e['entryNo']}" for d, e in entries_of(FIX)]
    assert [e["foodId"] for e in doc["entries"]] == [e["foodId"] for _, e in entries_of(FIX)]
    again = fresh("again") / "pantry-data.json"
    code, output = run_tool(FIXTURE, again)
    assert code == 0, output
    assert again.read_bytes() == run["out"].read_bytes(), "a re-import does not give the same bytes"


def test_fixture_per100():
    foods = {f["id"]: f for f in fixture_run()["doc"]["foods"]}
    first = {}
    for _, entry in entries_of(FIX):
        first.setdefault(entry["foodId"], entry)
    for food_id, entry in first.items():
        if entry.get("grams") is not None:
            assert foods[food_id]["per100"]["kcal"] == gram_kcal_per_100(entry), foods[food_id]["name"]
    potato = foods[POTATO]["per100"]
    assert {k: potato.get(k) for k in STARTER_KEYS} == STARTERS[POTATO], f"potato per100 {potato}"
    pizza = foods[PIZZA]["per100"]  # 500 g entry: 1304 kcal ... sodium 1556 mg; MyNetDiary has no fibre for it
    assert pizza == {"kcal": 260.8, "protein": 13.36, "carbs": 28.64, "fat": 9.52, "sugars": 6.16, "satFat": 6.32,
                     "salt": 0.78, "sodium": 311.2}, f"pizza per100 {pizza}"
    # The heaviest entry (potato 1000 g, not 350 g) gives the values besides kcal.
    for date, grams, expect in (("2026-10-19", 350, 2.27), ("2026-08-08", 1000, 9.9)):
        source = copy.deepcopy(FIX)
        day = next(d for d in source["days"] if d["date"] == date)
        next(e for e in day["entries"] if e["foodId"] == POTATO)["nutrients"]["protein"] = 99.0
        folder = fresh("heaviest")
        code, output = run_tool(write_source(folder, source), folder / "out.json")
        assert code == 0, output
        got = next(f for f in load(folder / "out.json")["foods"] if f["id"] == POTATO)["per100"]["protein"]
        assert got == expect, f"protein 99 g on the {grams} g entry: per100.protein {got}, want {expect}"


def test_fixture_food_without_grams():
    doc = fixture_run()["doc"]
    food = next(f for f in doc["foods"] if f["id"] == ROY_ROGERS)
    assert "per100" not in food, "a food never weighed has per100"
    assert food["servings"] == [{"label": "1 serving", "grams": None, "kcal": 350}], food["servings"]
    assert food["name"] == "Sandwiches Roast Beef Sand Whole Grain" and food["brand"] == "Roy Rogers"
    entry = next(e for e in doc["entries"] if e["foodId"] == ROY_ROGERS)
    assert entry["grams"] is None and entry["amount"] == "1 servings" and entry["totals"]["kcal"] == 350


def test_fixture_nutrient_mapping():
    doc = fixture_run()["doc"]
    entries = {e["id"]: e for e in doc["entries"]}
    # mozzarella 150 g: totalCarbs 12, totalFat 36.6, fiber 6, sodium 720 mg -> salt 1.8 g; netCarbs, diabetesCarbCount dropped
    assert entries["2026-10-19-102"]["totals"] == {"kcal": 486, "protein": 38.4, "carbs": 12, "fat": 36.6, "sugars": 6,
                                                   "satFat": 25.2, "salt": 1.8, "fibre": 6, "sodium": 720,
                                                   "calcium": 1158}, entries["2026-10-19-102"]["totals"]
    grilled = entries["2026-08-08-102"]["totals"]
    want = (612, 2298.0, 200.0, 0)  # the source carries float noise (2297.9999999808); kept as is, not rounded
    got = (grilled["cholesterol"], grilled["potassium"], grilled["vitaminA"], grilled["transFat"])
    assert all(abs(g - w) <= 1e-6 for g, w in zip(got, want)), got
    renamed = {"totalCarbs": "carbs", "totalFat": "fat", "fiber": "fibre"}
    for date, source_entry in entries_of(FIX):
        nutrients = source_entry["nutrients"]
        want = {"kcal"} | {renamed.get(k, k) for k in nutrients if k not in ("netCarbs", "diabetesCarbCount")}
        want |= {"salt"} if "sodium" in nutrients else set()
        got = entries[f"{date}-{source_entry['entryNo']}"]["totals"]
        assert set(got) == want, f"{date}-{source_entry['entryNo']}: keys {sorted(set(got) ^ want)} differ"
        for key, value in nutrients.items():
            if key not in ("netCarbs", "diabetesCarbCount"):
                assert got[renamed.get(key, key)] == value, f"{date} {key}: {got[renamed.get(key, key)]} != {value}"
        if "sodium" in nutrients:
            assert abs(got["salt"] - nutrients["sodium"] * 2.5 / 1000) <= 1e-6
    pizza = next(f for f in doc["foods"] if f["id"] == PIZZA)
    assert "fibre" not in pizza["per100"] and all("fibre" not in e["totals"] for e in doc["entries"] if e["foodId"] == PIZZA), \
        "a missing nutrient was filled in"


def test_fixture_names_meals_amounts():
    doc = fixture_run()["doc"]
    foods = {f["id"]: f for f in doc["foods"]}
    by_id = {e["id"]: e for e in doc["entries"]}
    for date, source_entry in entries_of(FIX):
        food = foods[source_entry["foodId"]]
        assert food["name"] == source_entry["cleanName"], food["name"]
        if source_entry.get("vendor"):
            assert food["brand"] == source_entry["vendor"], food["name"]
        else:
            assert "brand" not in food, f"{food['name']} has a brand MyNetDiary does not"
        entry = by_id[f"{date}-{source_entry['entryNo']}"]
        assert entry["meal"] == MEALS[source_entry["meal"]] and entry["amount"] == source_entry["amount"]
        assert entry["grams"] == source_entry.get("grams") and entry["date"] == date
    assert by_id["2026-10-19-103"]["amount"] == "4 eggs" and by_id["2026-08-08-401"]["amount"] == "1.5 slices"


# ---------------------------------------------------------------- refusals

def test_refuses_path_git_does_not_ignore():
    rel = "pantry-data-refusal-check.json"
    assert not git_ignores(rel), f"{rel} is ignored, so it cannot test the refusal"
    code, output = run_tool(FIXTURE, ROOT / rel)
    exists = (ROOT / rel).exists()
    if exists:
        (ROOT / rel).unlink()
    assert code != 0 and not exists, f"exit {code}, file written {exists}:\n{output}"


def test_refuses_inside_references():
    rel = "references/mynetdiary-history-refusal-check.json"
    assert git_ignores(rel), f"{rel} is not ignored, so only the ignore rule would be tested"
    had_folder = (ROOT / "references").exists()
    code, output = run_tool(FIXTURE, ROOT / rel)
    assert code != 0 and "references" in output, f"exit {code}:\n{output}"
    assert not (ROOT / rel).exists(), "wrote inside references/"
    assert (ROOT / "references").exists() == had_folder, "created references/"


def test_tmp_follows_git():
    rel = ".tmp/test-import-situation.json"
    ignored, had_tmp = git_ignores(rel), (ROOT / ".tmp").exists()
    code, output = run_tool(FIXTURE, ROOT / rel)
    written = (ROOT / rel).exists()
    if written:
        (ROOT / rel).unlink()
    if ignored:
        assert code == 0 and written, f".tmp/ is ignored but the tool refused it (exit {code}):\n{output}"
    else:
        assert code != 0 and not written, f".tmp/ is not ignored but the tool wrote there (exit {code})"
        assert (ROOT / ".tmp").exists() == had_tmp, "a refused run created .tmp/"
    return ".tmp/ ignored: written" if ignored else ".tmp/ not ignored yet: refused"


def test_outside_work_tree_allowed():
    outside = Path(tempfile.mkdtemp(prefix="pantry-test-import-outside-"))
    try:
        probe = subprocess.run(["git", "-C", str(outside), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if probe.returncode == 0:
            raise Skip(f"the system temp folder is inside the git work tree {probe.stdout.strip()}")
        code, output = run_tool(FIXTURE, outside / "pantry-data.json")
        assert code == 0 and (outside / "pantry-data.json").exists(), f"exit {code}:\n{output}"
    finally:
        shutil.rmtree(outside, ignore_errors=True)


# ---------------------------------------------------------------- corruption

def test_corrupt_kcal_in_source_writes_nothing():
    for bad in ("296", None, -296, float("nan"), True):
        source = copy.deepcopy(FIX)
        source["days"][1]["entries"][2]["kcal"] = bad  # 2026-10-19-103, the eggs
        folder = fresh("corrupt")
        out = folder / "out.json"
        out.write_text("sentinel", encoding="utf-8")
        code, output = run_tool(write_source(folder, source), out)
        assert code != 0, f"kcal {bad!r}: exit 0"
        assert out.read_text(encoding="utf-8") == "sentinel", f"kcal {bad!r}: the existing file was touched"
        out.unlink()
        code, output = run_tool(write_source(folder, source), out)
        assert code != 0 and not out.exists(), f"kcal {bad!r}: exit {code}, file written {out.exists()}"


def test_document_off_from_source_writes_nothing():
    """The per-day guard itself: the built document is corrupted after build, the tool must refuse."""
    spec = importlib.util.spec_from_file_location("import_mynetdiary", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    build = tool.build_document

    def entry(doc, entry_id):
        return next(e for e in doc["entries"] if e["id"] == entry_id)["totals"]

    def bump(doc, entry_id, key, delta):
        entry(doc, entry_id)[key] += delta

    mutations = {
        "none (control)": lambda doc: None,
        "one entry's kcal +2": lambda doc: bump(doc, "2026-10-19-103", "kcal", 2),
        "one entry's protein +0.2 g": lambda doc: bump(doc, "2026-08-08-301", "protein", 0.2),
        "carbs read from netCarbs": lambda doc: entry(doc, "2026-10-19-102").update(carbs=6),
        "fat +0.2 g": lambda doc: bump(doc, "2026-10-20-101", "fat", 0.2),
        "salt as sodium / 1000": lambda doc: entry(doc, "2026-10-19-102").update(salt=0.72),
        "a known 0 g carbs dropped": lambda doc: entry(doc, "2026-08-08-102").pop("carbs"),
        "an entry dropped": lambda doc: doc["entries"].pop(0),
        "an entry moved to another day": lambda doc: next(e for e in doc["entries"] if e["id"] == "2026-08-08-401").update(date="2026-10-19"),
    }
    for name, mutate in mutations.items():
        def corrupted(source, mutate=mutate):
            doc = build(source)
            mutate(doc)
            return doc
        tool.build_document = corrupted
        out = fresh("guard") / "out.json"
        with contextlib.redirect_stdout(io.StringIO()) as said, contextlib.redirect_stderr(said):
            code = tool.main([str(FIXTURE), "-o", str(out)])
        if name.startswith("none"):
            assert code == 0 and out.exists(), f"control run failed (exit {code}):\n{said.getvalue()}"
        else:
            assert code != 0 and not out.exists(), f"{name}: exit {code}, file written {out.exists()}"
    tool.build_document = build


def test_eaten_differs_listed_not_fatal():
    source = copy.deepcopy(FIX)
    source["days"][1]["eaten"] = "2,400"  # 2026-10-19: its entries sum to 2,292
    folder = fresh("eaten")
    code, output = run_tool(write_source(folder, source), folder / "out.json")
    assert code == 0 and (folder / "out.json").exists(), f"exit {code}:\n{output}"
    assert summary_value(output, "days where eaten differs") == "1", output
    assert re.search(r"2026-10-19\s+eaten 2,400, entries 2,292", output), output


# ---------------------------------------------------------------- full source

_full_run = {}


def full_run():
    if not FULL.exists():
        raise Skip(f"full source not found at {FULL} (gitignored; set MYNETDIARY_SOURCE to run these)")
    if not _full_run:
        out = fresh("full") / "pantry-data.json"
        code, output = run_tool(FULL, out)
        assert code == 0, f"exit {code}:\n{output}"
        _full_run.update(output=output, doc=load(out), source=json.loads(FULL.read_text(encoding="utf-8")))
    return _full_run


def test_full_counts():
    run = full_run()
    want = {"days": "464", "entries": "2,722", "foods": "115", "foods without grams": "16",
            "entries with no nutrients": "55", "first date": "2025-07-14", "last date": "2026-10-20"}
    for label, value in want.items():
        assert summary_value(run["output"], label) == value, f"summary {label}: {summary_value(run['output'], label)}, want {value}"
    doc = run["doc"]
    assert len(doc["entries"]) == 2722 and len(doc["foods"]) == 115, (len(doc["entries"]), len(doc["foods"]))
    assert sum(1 for f in doc["foods"] if "per100" not in f) == 16
    assert len({e["date"] for e in doc["entries"]}) == 464


def test_full_eaten_listing():
    output = full_run()["output"]
    assert summary_value(output, "days where eaten differs") == "1", output
    assert re.search(r"^\s+2026-04-06\s+eaten 2,318, entries 2,141 kcal$", output, re.M), output


def test_full_butter_and_starters():
    foods = {f["id"]: f for f in full_run()["doc"]["foods"]}
    assert foods[BUTTER]["per100"]["kcal"] == 616.6, foods[BUTTER]["per100"]
    for food_id, want in STARTERS.items():
        got = {k: foods[food_id]["per100"][k] for k in STARTER_KEYS if k in foods[food_id]["per100"]}
        assert got == want, f"{foods[food_id]['name']}: {got}, Task-00 has {want}"


def test_full_empty_nutrients():
    run = full_run()
    empty = {f"{d}-{e['entryNo']}": e["kcal"] for d, e in entries_of(run["source"]) if not e["nutrients"]}
    assert len(empty) == 55, len(empty)
    for entry in run["doc"]["entries"]:
        if entry["id"] in empty:
            assert entry["totals"] == {"kcal": empty[entry["id"]]}, f"{entry['id']}: {entry['totals']}"


def test_full_totals_exact():
    # every entry keeps MyNetDiary's values unrounded (a 0.004 g protein must not become 0)
    renamed = {"totalCarbs": "carbs", "totalFat": "fat", "fiber": "fibre"}
    run = full_run()
    entries = {e["id"]: e for e in run["doc"]["entries"]}
    for date, source_entry in entries_of(run["source"]):
        got = entries[f"{date}-{source_entry['entryNo']}"]["totals"]
        for key, value in source_entry["nutrients"].items():
            if key not in ("netCarbs", "diabetesCarbCount"):
                assert got[renamed.get(key, key)] == value, f"{date}-{source_entry['entryNo']} {key}: {got[renamed.get(key, key)]} != {value}"


def test_full_day_sums_match():
    assert assert_day_sums_match(full_run()["source"], full_run()["doc"]) == 464


def test_full_foods():
    run = full_run()
    latest = {}
    weighed = set()
    for _, entry in entries_of(run["source"]):
        latest[entry["foodId"]] = entry
        if entry.get("grams") is not None:
            weighed.add(entry["foodId"])
    for food in run["doc"]["foods"]:
        if food["id"] in weighed:
            assert food["per100"]["kcal"] == gram_kcal_per_100(latest[food["id"]]), food["name"]
        else:
            assert "per100" not in food and all(s["grams"] is None for s in food["servings"]), food["name"]
            assert all("kcal" in s for s in food["servings"]), food["name"]


# ---------------------------------------------------------------- runner

def main():
    global WORK
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if git_ignores(".tmp/test-import-probe.json"):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        WORK = tempfile.mkdtemp(prefix="test-import-", dir=ROOT / ".tmp")
        print("outputs in .tmp/ (git ignores it)")
    else:
        WORK = tempfile.mkdtemp(prefix="pantry-test-import-")
        print("outputs in a temp folder outside the repo (.tmp/ is not ignored yet)")
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn)]
    failed = skipped = 0
    try:
        for name, fn in tests:
            try:
                note = fn()
                print(f"PASS {name}" + (f" ({note})" if note else ""))
            except Skip as reason:
                skipped += 1
                print(f"SKIP {name}: {reason}")
            except Exception as error:  # an assertion, or the tool crashing on the way
                failed += 1
                print(f"FAIL {name}: {type(error).__name__}: {error}")
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print(f"{len(tests) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


WORK = None

if __name__ == "__main__":
    sys.exit(main())

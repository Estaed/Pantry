"""Build the Pantry data document from a MyNetDiary history export.

Usage, from the repo root:
    python tools/import_mynetdiary.py references/mynetdiary-history-2026-10-20.json -o .tmp/pantry-data.json

The source is the export pulled from mynetdiary.com (notes.md, "MyNetDiary history"): top keys
exported, source, days, errors; each day {date, eaten, entries}. The output is one JSON document
{version, foods, entries, settings} in the shape fixed in tasks/Task-00.md:
- every entry keeps its date, meal, amount as typed, grams and nutrient totals as MyNetDiary had
  them; ids are stable across re-imports (entry "<date>-<entryNo>", food = MyNetDiary foodId);
- every food keeps its servings; a food ever logged by grams gets per100 (kcal from its gram
  serving, the rest from its entry with the most grams); a nutrient MyNetDiary lacks stays absent.

Exit 2: the output path is refused (inside references/, or not reported ignored by git; a path
outside any git work tree cannot be committed and is allowed). Exit 1: the source is malformed, or
the built document's per-day kcal, protein, carbs, fat or salt differ from the source entries.
Nothing is written in either case. Standard library only.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import date as Date
from pathlib import Path

MEALS = {"Breakfast": "breakfast", "Lunch": "lunch", "Dinner": "dinner", "Snacks": "snacks"}
RENAMED = {"totalCarbs": "carbs", "totalFat": "fat", "fiber": "fibre"}  # the others keep their names
DROPPED = {"netCarbs", "diabetesCarbCount"}
DERIVED = {"kcal", "carbs", "fat", "fibre", "salt"}  # Pantry keys a source nutrient must not already use
KEY_ORDER = ("kcal", "protein", "carbs", "fat", "sugars", "satFat", "salt", "fibre", "sodium")
SETTINGS = {"targets": {"kcal": 2200, "proteinPct": 20, "carbsPct": 45, "fatPct": 35, "salt": 5.8}}
CHECKED = ("kcal", "protein", "carbs", "fat", "salt")
TOLERANCE = {"kcal": 1.0, "protein": 0.1, "carbs": 0.1, "fat": 0.1, "salt": 0.1}
GM = re.compile(r"(\d+(?:\.\d+)?) g")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(source):
    """Problems that stop the import; empty when the source is usable."""
    if not isinstance(source, dict) or not isinstance(source.get("days"), list):
        return ["the source has no list under 'days'"]
    problems, dates, foods = [], set(), {}
    for d, day in enumerate(source["days"]):
        if not isinstance(day, dict):
            problems.append(f"days[{d}] is not an object")
            continue
        when = day.get("date")
        if not (isinstance(when, str) and DATE.fullmatch(when)) or not _real_date(when):
            problems.append(f"days[{d}]: date {when!r} is not YYYY-MM-DD")
            continue
        if when in dates:
            problems.append(f"{when}: the day appears twice")
        dates.add(when)
        if not isinstance(day.get("entries"), list):
            problems.append(f"{when}: no list under 'entries'")
            continue
        numbers = set()
        for e, entry in enumerate(day["entries"]):
            where = f"{when} entry {e + 1}"
            if not isinstance(entry, dict):
                problems.append(f"{where}: not an object")
                continue
            no = entry.get("entryNo")
            if not isinstance(no, int) or isinstance(no, bool):
                problems.append(f"{where}: entryNo {no!r} is not a whole number")
            elif no in numbers:
                problems.append(f"{where}: entryNo {no} appears twice on the day")
            else:
                numbers.add(no)
                where = f"{when}-{no}"
            problems += _entry_problems(where, entry)
            if isinstance(entry.get("foodId"), str) and entry["foodId"]:
                foods.setdefault(entry["foodId"], []).append((when, entry))
    for food_id, logged in foods.items():
        weighed = any(is_number(entry.get("grams")) for _, entry in logged)
        servings = sorted(logged, key=lambda pair: pair[0])[-1][1].get("servings")  # the entry build_food reads
        if weighed and isinstance(servings, list) and not any(
                isinstance(s, dict) and s.get("title") == "gram" and "gm" in s for s in servings):
            problems.append(f"food {food_id}: logged by grams but has no 'gram' serving")
    return problems


def _real_date(text):
    try:
        Date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _entry_problems(where, entry):
    problems = []
    if entry.get("meal") not in MEALS:
        problems.append(f"{where}: meal {entry.get('meal')!r} is not one of {', '.join(MEALS)}")
    for key in ("foodId", "cleanName", "amount"):
        if not isinstance(entry.get(key), str) or (key != "amount" and not entry[key]):
            problems.append(f"{where}: {key} is missing or not text")
    if entry.get("vendor") is not None and not isinstance(entry["vendor"], str):
        problems.append(f"{where}: vendor is not text")
    grams = entry.get("grams")
    if grams is not None and not (is_number(grams) and grams > 0):
        problems.append(f"{where}: grams {grams!r} is not a positive number")
    if not (is_number(entry.get("kcal")) and entry["kcal"] >= 0):
        problems.append(f"{where}: kcal {entry.get('kcal')!r} is not a number of 0 or more")
    nutrients = entry.get("nutrients")
    if not isinstance(nutrients, dict):
        problems.append(f"{where}: nutrients is not an object")
    else:
        for key, value in nutrients.items():
            if key in DERIVED:
                problems.append(f"{where}: nutrient name {key!r} clashes with a Pantry key")
            if not (is_number(value) and value >= 0):
                problems.append(f"{where}: nutrient {key} {value!r} is not a number of 0 or more")
    servings = entry.get("servings")
    if not isinstance(servings, list):
        problems.append(f"{where}: servings is not a list")
        return problems
    for s, serving in enumerate(servings):
        if not _serving_ok(serving):
            problems.append(f"{where}: serving {s + 1} {serving!r} is not {{amount, title, gm?, kcal}}")
    return problems


def _serving_ok(serving):
    """{amount: "2", title: "eggs", gm?: "104 g", kcal: 148.0}, as the export writes servings."""
    if not (isinstance(serving, dict) and isinstance(serving.get("title"), str) and serving["title"]):
        return False
    amount, gm = serving.get("amount"), serving.get("gm", "1 g")
    return (isinstance(amount, str) and bool(NUMBER.fullmatch(amount)) and float(amount) > 0
            and is_number(serving.get("kcal")) and serving["kcal"] >= 0
            and isinstance(gm, str) and bool(GM.fullmatch(gm)) and float(GM.fullmatch(gm).group(1)) > 0)


def map_nutrients(kcal, nutrients):
    """Pantry nutrient keys from MyNetDiary's; a nutrient MyNetDiary lacks stays absent, never 0."""
    mapped = {"kcal": kcal}
    for key, value in nutrients.items():
        if key not in DROPPED:
            mapped[RENAMED.get(key, key)] = value
    if "sodium" in nutrients:
        mapped["salt"] = round(nutrients["sodium"] * 2.5 / 1000, 6)  # sodium mg -> salt g; sodium is kept too
    ordered = {key: mapped[key] for key in KEY_ORDER if key in mapped}
    ordered.update((key, value) for key, value in mapped.items() if key not in ordered)
    return ordered


def _gm(text):
    number = GM.fullmatch(text).group(1)
    return float(number) if "." in number else int(number)


def build_food(food_id, logged):
    """A Pantry food from every source entry that logged it, oldest first."""
    latest = logged[-1]  # the export repeats the food's current definition on every entry
    food = {"id": food_id, "name": latest["cleanName"]}
    if latest.get("vendor"):
        food["brand"] = latest["vendor"]
    weighed = [entry for entry in logged if entry.get("grams") is not None]
    if weighed:
        gram = next(s for s in latest["servings"] if s["title"] == "gram" and "gm" in s)
        heaviest = max(weighed, key=lambda entry: entry["grams"])  # the earliest of equals
        rest = map_nutrients(0, heaviest["nutrients"])
        del rest["kcal"]
        food["per100"] = {"kcal": round(gram["kcal"] * 100 / _gm(gram["gm"]), 1)}
        food["per100"].update((key, round(value * 100 / heaviest["grams"], 2)) for key, value in rest.items())
    food["servings"] = [{
        "label": f"{serving['amount']} {serving['title']}",
        "grams": _gm(serving["gm"]) if "gm" in serving else None,
        "kcal": serving["kcal"],
    } for serving in latest["servings"]]
    food["source"] = "mynetdiary"
    return food


def build_document(source):
    """The Pantry document for a validated source."""
    logged_by_food, entries = {}, []
    for day in sorted(source["days"], key=lambda day: day["date"]):
        for entry in day["entries"]:
            logged_by_food.setdefault(entry["foodId"], []).append(entry)
            totals = map_nutrients(entry["kcal"], entry["nutrients"])
            entries.append({
                "id": f"{day['date']}-{entry['entryNo']}",
                "date": day["date"],
                "meal": MEALS[entry["meal"]],
                "foodId": entry["foodId"],
                "amount": entry["amount"],
                "grams": entry.get("grams"),
                "totals": totals,  # exactly as MyNetDiary had them; salt is derived from sodium
            })
    foods = [build_food(food_id, logged) for food_id, logged in logged_by_food.items()]
    return {"version": 1, "foods": foods, "entries": entries, "settings": json.loads(json.dumps(SETTINGS))}


def _source_values(entry):
    """The checked values read straight from a source entry, apart from map_nutrients on purpose."""
    nutrients, values = entry["nutrients"], {"kcal": entry["kcal"]}
    for pantry_key, source_key in (("protein", "protein"), ("carbs", "totalCarbs"), ("fat", "totalFat")):
        if source_key in nutrients:
            values[pantry_key] = nutrients[source_key]
    if "sodium" in nutrients:
        values["salt"] = nutrients["sodium"] * 2.5 / 1000
    return values


def _day_sums(rows):
    days = {}
    for when, values in rows:
        day = days.setdefault(when, {"entries": 0, **{key: [0.0, 0] for key in CHECKED}})
        day["entries"] += 1
        for key in CHECKED:
            if key in values:
                day[key][0] += values[key]
                day[key][1] += 1
    return days


def verify(source, doc):
    """Where the document does not match the source; empty when it does."""
    problems = []
    want = _day_sums((day["date"], _source_values(entry)) for day in source["days"] for entry in day["entries"])
    got = _day_sums((entry["date"], entry["totals"]) for entry in doc["entries"])
    for when in sorted(set(want) | set(got)):
        if when not in got or when not in want:
            problems.append(f"{when}: has entries only in the {'source' if when in want else 'document'}")
            continue
        w, g = want[when], got[when]
        if w["entries"] != g["entries"]:
            problems.append(f"{when}: {g['entries']} entries in the document, {w['entries']} in the source")
        for key in CHECKED:
            if abs(w[key][0] - g[key][0]) > TOLERANCE[key] + 1e-9:
                problems.append(f"{when}: {key} {g[key][0]:,.2f} in the document, {w[key][0]:,.2f} in the source")
            if w[key][1] != g[key][1]:
                problems.append(f"{when}: {key} known on {g[key][1]} entries in the document, {w[key][1]} in the source")
    entry_ids = [entry["id"] for entry in doc["entries"]]
    food_ids = [food["id"] for food in doc["foods"]]
    if len(set(entry_ids)) != len(entry_ids):
        problems.append("entry ids are not unique")
    if len(set(food_ids)) != len(food_ids):
        problems.append("food ids are not unique")
    source_foods = {entry["foodId"] for day in source["days"] for entry in day["entries"]}
    if set(food_ids) != source_foods:
        problems.append(f"{len(set(food_ids))} foods in the document, {len(source_foods)} in the source")
    if {entry["foodId"] for entry in doc["entries"]} - set(food_ids):
        problems.append("some entries name a food the document does not have")
    return problems


def eaten_differs(source):
    """(date, eaten as MyNetDiary showed it, kcal sum of the day's entries) where the two differ."""
    differs = []
    for day in sorted(source["days"], key=lambda day: day["date"]):
        total = sum(entry["kcal"] for entry in day["entries"])
        try:
            eaten = float(str(day.get("eaten")).replace(",", ""))
        except ValueError:
            eaten = math.nan
        if not math.isfinite(eaten) or round(eaten) != round(total):
            differs.append((day["date"], day.get("eaten"), total))
    return differs


def summary(source_path, source):
    days = source["days"]
    entries = [entry for day in days for entry in day["entries"]]
    weighed = {entry["foodId"] for entry in entries if entry.get("grams") is not None}
    foods = {entry["foodId"] for entry in entries}
    dates = sorted(day["date"] for day in days)
    differs = eaten_differs(source)
    rows = [
        ("source", str(source_path)),
        ("days", f"{len(days):,}"),
        ("first date", dates[0] if dates else "-"),
        ("last date", dates[-1] if dates else "-"),
        ("entries", f"{len(entries):,}"),
        ("foods", f"{len(foods):,}"),
        ("foods without grams", f"{len(foods - weighed):,}"),
        ("entries with no nutrients", f"{sum(1 for entry in entries if not entry['nutrients']):,}"),
        ("days where eaten differs", f"{len(differs):,}"),
    ]
    lines = ["MyNetDiary import"] + [f"  {label + ':':<27} {value}" for label, value in rows]
    for when, eaten, total in differs:
        lines.append(f"    {when}  eaten {eaten}, entries {total:,} kcal")
    errors = source.get("errors")
    if errors:
        lines.append(f"  {'pull errors in source:':<27} {len(errors)} (first: {json.dumps(errors[0])[:120]})")
    return lines


def refuse_output(output, source_path):
    """Why the document must not be written to `output`, or None when it may be."""
    path = output.resolve()
    if any(part.casefold() == "references" for part in path.parent.parts):
        return "it is inside references/, which this tool never writes"
    if path == source_path.resolve():
        return "it is the source file"
    if path.is_dir():
        return "it is a directory"
    anchor = path.parent
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    env = {key: value for key, value in os.environ.items() if key not in ("GIT_DIR", "GIT_WORK_TREE")}
    env.update(LC_ALL="C", LANGUAGE="C")
    try:
        top = subprocess.run(["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, env=env)
        if top.returncode != 0:
            if "not a git repository" in top.stderr:
                return None  # outside every git work tree: no repo can commit it
            return f"git could not place it in a work tree: {top.stderr.strip()}"
        root = Path(top.stdout.strip()).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            return f"it could not be placed under the work tree {root}"
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative],
                                 capture_output=True, text=True, env=env)
    except OSError as error:
        return f"git could not be run ({error}), so the path cannot be checked"
    if ignored.returncode == 0:
        return None
    if ignored.returncode == 1:
        return f"git check-ignore does not report it as ignored in {root}, so the personal data could be committed"
    return f"git check-ignore failed: {ignored.stderr.strip()}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Pantry data document from a MyNetDiary history export.")
    parser.add_argument("source", type=Path, help="the MyNetDiary history JSON")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="where to write the document; must be git-ignored (for example .tmp/pantry-data.json)")
    args = parser.parse_args(argv)

    reason = refuse_output(args.output, args.source)
    if reason:
        print(f"REFUSED {args.output}: {reason}. Nothing written.", file=sys.stderr)
        return 2
    try:
        source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        print(f"REFUSED: cannot read {args.source}: {error}. Nothing written.", file=sys.stderr)
        return 1
    problems = validate(source)
    if problems:
        print(f"REFUSED: {args.source} cannot be imported as it is ({len(problems)} problems). Nothing written.",
              file=sys.stderr)
        for problem in problems[:20]:
            print(f"  {problem}", file=sys.stderr)
        return 1

    doc = build_document(source)
    print("\n".join(summary(args.source, source)))
    problems = verify(source, doc)
    if problems:
        print(f"REFUSED: the document does not match the source ({len(problems)} problems). Nothing written.",
              file=sys.stderr)
        for problem in problems[:20]:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"  {'check:':<27} {', '.join(CHECKED)} match the source on every day")

    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    if json.loads(output.read_text(encoding="utf-8")) != doc:
        print(f"FAILED: {args.output} does not read back as the document.", file=sys.stderr)
        return 1
    print(f"wrote {args.output} ({len(doc['foods']):,} foods, {len(doc['entries']):,} entries, "
          f"{output.stat().st_size / 1024:,.0f} KB)")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())

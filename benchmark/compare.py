"""Compare two benchmark runs on the questions they both answered.

    python -m benchmark.compare v2 day18
"""
import json
import sys
from pathlib import Path

from benchmark.run import load_questions
from benchmark.scoring import PASSING, pct, summarize

HERE = Path(__file__).parent


def load_records(name):
    path = HERE / "results" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def compare(questions, before, after):
    """Compare on shared questions. Questions that errored in either run are left out."""
    shared = [q for q in questions if q["id"] in before and q["id"] in after]
    scored_before = {s["id"]: s["outcome"] for s in summarize(shared, before)["scored"]}
    scored_after = {s["id"]: s["outcome"] for s in summarize(shared, after)["scored"]}
    usable = [
        q for q in shared
        if "error" not in (scored_before[q["id"]], scored_after[q["id"]])
    ]
    ids = [q["id"] for q in usable]
    return {
        "questions": usable,
        "before": summarize(usable, before),
        "after": summarize(usable, after),
        "fixed": [i for i in ids if scored_before[i] not in PASSING and scored_after[i] in PASSING],
        "broke": [i for i in ids if scored_before[i] in PASSING and scored_after[i] not in PASSING],
        "still_failing": [
            i for i in ids if scored_before[i] not in PASSING and scored_after[i] not in PASSING
        ],
        "skipped": len(shared) - len(usable),
    }


def format_comparison(name_before, name_after, result):
    b, a = result["before"], result["after"]
    rows = [
        ("Retrieval hit rate", pct(b["retrieval_hits"], b["answerable"]), pct(a["retrieval_hits"], a["answerable"])),
        ("Answer accuracy", pct(b["correct"], b["answerable"]), pct(a["correct"], a["answerable"])),
        ("Correct refusals", pct(b["correct_refusal"], b["unanswerable"]), pct(a["correct_refusal"], a["unanswerable"])),
        ("Silent errors", str(b["silent_errors"]), str(a["silent_errors"])),
        ("False refusals", str(b["false_refusal"]), str(a["false_refusal"])),
        ("Right answer, wrong citation", str(b["miscited"]), str(a["miscited"])),
        ("Overall pass rate", pct(b["passed"], b["valid"]), pct(a["passed"], a["valid"])),
    ]
    by_id = {q["id"]: q["question"] for q in result["questions"]}
    lines = [
        f"# {name_before} compared with {name_after}",
        "",
        f"{len(result['questions'])} shared questions compared ({result['skipped']} skipped because of errors).",
        "",
        f"| Metric | {name_before} | {name_after} |",
        "|---|---|---|",
    ]
    lines += [f"| {label} | {x} | {y} |" for label, x, y in rows]
    for title, key in (("Fixed", "fixed"), ("Broke", "broke"), ("Still failing", "still_failing")):
        lines += ["", f"## {title}", ""]
        if not result[key]:
            lines.append("None.")
        lines += [f"- {i}: {by_id[i]}" for i in result[key]]
    return "\n".join(lines) + "\n"


def main():
    name_before, name_after = sys.argv[1], sys.argv[2]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = compare(load_questions(), load_records(name_before), load_records(name_after))
    report = format_comparison(name_before, name_after, result)
    (HERE / "results" / f"compare_{name_before}_{name_after}.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

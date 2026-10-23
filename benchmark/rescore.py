"""Re-score a saved run with the current scoring rules. Makes no API calls.

    python -m benchmark.rescore baseline
"""
import json
import sys
from pathlib import Path

from benchmark.run import load_questions
from benchmark.scoring import format_report, summarize

HERE = Path(__file__).parent


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = HERE / "results" / f"{name}.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    records = saved["records"]
    questions = [q for q in load_questions() if q["id"] in records]
    report = format_report(summarize(questions, records), questions, records, saved.get("meta"))
    (HERE / "results" / f"{name}.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

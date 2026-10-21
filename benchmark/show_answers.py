"""Print a random sample of benchmark answers so a human can check the scorer.

    python benchmark/show_answers.py baseline 10
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
count = int(sys.argv[2]) if len(sys.argv) > 2 else 10

data = json.loads((HERE / "results" / f"{name}.json").read_text(encoding="utf-8"))
questions = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

records = data["records"]
for qid in sorted(random.sample(sorted(records), min(count, len(records)))):
    record = records[qid]
    question = questions[qid]
    print(f"{qid} [{record['status']}] {question['question']}")
    print(f"   answer: {record['answer'][:300]}")
    print(f"   cited: {[(s['source'], s['page']) for s in record['sources']]}")
    if question["answerable"]:
        print(f"   needs: {question['answer_keys']}")
    print()

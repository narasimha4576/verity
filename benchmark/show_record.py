"""Show everything recorded for specific benchmark questions.

    python benchmark/show_record.py v2 AM03 TU01
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
name = sys.argv[1]
ids = sys.argv[2:]

data = json.loads((HERE / "results" / f"{name}.json").read_text(encoding="utf-8"))
questions = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for qid in ids:
    record = data["records"][qid]
    question = questions[qid]
    print(f"{qid} [{record['status']}] {question['question']}")
    print(f"   searched for: {record['question_used']}")
    print("   retrieved (top results, before the similarity floor):")
    for hit in record["retrieved"]:
        print(f"      {hit['source']} p.{hit['page']}  score {hit['score']}")
    print(f"   cited: {[(s['source'], s['page']) for s in record['sources']]}")
    print(f"   answer: {record['answer']}")
    if question["answerable"]:
        print(f"   expected: {[(e['source'], e['page']) for e in question['expected']]}")
    print()

import sys

from app.answer import answer_question

result = answer_question(" ".join(sys.argv[1:]))
print(f"[{result['status']}] {result['answer']}")
for s in result["sources"]:
    print(f"  source: {s['source']} page {s['page']}")

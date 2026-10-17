import sys

from app.answer import answer_question

result = answer_question(" ".join(sys.argv[1:]))
print(result["answer"])
print("\nPages searched:")
for s in result["sources"]:
    print(f"  {s['source']} page {s['page']} (score {s['score']:.2f})")

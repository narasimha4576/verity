import sys

from app.embedder import embed_texts
from app.store import VectorStore

question = " ".join(sys.argv[1:])
query_vector = embed_texts([question], task_type="RETRIEVAL_QUERY")[0]
for hit in VectorStore().search(query_vector, k=3):
    print(f"[{hit['source']} page {hit['page']}] score={hit['score']:.2f}")
    print(f"  {hit['text'][:160]}\n")

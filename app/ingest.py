import sys
from pathlib import Path

from app.chunker import chunk_pages
from app.embedder import embed_texts
from app.loader import load_pdf
from app.store import VectorStore


def ingest(path, store=None, embed=embed_texts):
    path = Path(path)
    chunks = chunk_pages(load_pdf(path), source=path.name)
    if not chunks:
        return 0
    store = store or VectorStore()
    # Embed first: if this fails, the old version of the document stays intact
    vectors = embed([c["text"] for c in chunks])
    store.replace_source(path.name, chunks, vectors)
    return len(chunks)


if __name__ == "__main__":
    count = ingest(sys.argv[1])
    print(f"Stored {count} chunks from {sys.argv[1]}")

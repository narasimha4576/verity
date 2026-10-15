import sys
from pathlib import Path

from app.chunker import chunk_pages
from app.loader import load_pdf

path = Path(sys.argv[1])
pages = load_pdf(path)
chunks = chunk_pages(pages, source=path.name)
print(f"Pages with text: {len(pages)}")
print(f"Chunks: {len(chunks)}")
if chunks:
    first = chunks[0]
    print(f"First chunk ({first['source']}, page {first['page']}):")
    print(first["text"][:300])

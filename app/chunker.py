def chunk_pages(pages, source, size=800, overlap=150):
    """Split each page into overlapping chunks. Every chunk keeps its
    source file name and page number so answers can cite them."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks = []
    for page in pages:
        text = " ".join(page["text"].split())
        start = 0
        index = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append({
                "id": f"{source}-p{page['page']}-{index}",
                "source": source,
                "page": page["page"],
                "text": text[start:end],
            })
            index += 1
            if end == len(text):
                break
            start = end - overlap
    return chunks

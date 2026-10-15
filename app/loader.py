from pypdf import PdfReader


def load_pdf(path):
    """Return a list of {"page": n, "text": ...} with 1-based page numbers.
    Pages with no extractable text (scans, blank pages) are skipped."""
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": number, "text": text})
    return pages

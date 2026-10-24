"""Decide whether a question the documents could not answer may go to the web.

Documents always come first. The web is a fallback, and only when it is allowed.
"""

# The documents were searched and genuinely hold no answer.
DOCUMENT_GAPS = {"not_found", "low_similarity", "no_documents"}


def decide(result, allow_web, sources=None):
    """Return (use_web, reason). The reason is for logs and for the user.

    A rejected answer (ungrounded, invalid_output) is a problem with the
    system, not a gap in the documents, so it never falls through to the web.
    That would hide a bug and could replace a document answer with a worse one.
    """
    if not allow_web:
        return False, "web search is switched off"
    if sources:
        return False, "the search was limited to chosen documents"
    status = result["status"]
    if status in DOCUMENT_GAPS:
        return True, "your documents do not answer this question"
    if status == "answered":
        return False, "your documents answered it"
    return False, "the document answer was rejected, so the web was not used"

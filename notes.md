# Verity notes

## Day 1
- Key check printed ready after fixing the model name. The display name "Gemini 3.1 Flash Lite" is not the API id.
- A file called "notepad .env" got staged by mistake. Caught it before the first commit.

## Day 2
- Sample policy: 4 pages, 6 chunks. Chunks overlap so a sentence cut at a boundary still appears whole.

## Day 3
- Embedding = text turned into numbers so similar meaning gives similar numbers. ChromaDB finds the closest chunks.
- Retry only temporary errors (network drops, 429, 5xx).

## Day 4-5
- Premium question scored 0.64 similarity, like a real question, so a score alone cannot detect "not answerable".
- Two layers: similarity floor, then the AI found flag. Plus JSON shape check and citation check.

## Day 6
- Status codes: 400 bad input, 413 too large, 422 unusable content, 503 temporary AI problem.
- dependency_overrides swaps real parts for fakes in tests.

## Day 8-9 (screen and memory)
- A follow-up like "and for seniors?" cannot be searched directly, so it is rewritten into a full question first.
- The rewriter sometimes adds words I never typed (it added "for a prepayment" because the chat was about prepayment). This goes into the benchmark as a baseline before I fix it.

## Day 10 (streaming)
- Answers are verified before they are shown, so the stages stream live and the typing effect comes after the checks. Honest trade-off: first word is later, but unverified text is never shown.

## Day 11 (documents)
- A search filter limits which documents are searched. If the AI cites a document outside the filter, the citation check rejects the answer.
- Re-uploading a file used to leave stale chunks. Now the new version is embedded first, then swapped in, so a network drop cannot lose the old version.

## Day 12 (new UI)
- Streamlit cannot produce a chat layout like the big assistants, so I built a plain web page served by FastAPI. Text is inserted as text, never as HTML, so a hostile document cannot run code in the browser.

## Day 13 (Docker)
- Image size: 841 MB. whoami inside the container prints "verity" (not root).
- .env and the database are kept out of the image with .dockerignore, and the key is supplied at run time.

## Day 15 (benchmark v1)
- 57 questions on 2 fake documents (10 chunks). Retrieval 47/47, answers 47/47, refusals 10/10, 0 silent errors, 0 errors.
- A perfect score means the set is too easy, not that Verity is perfect: top-4 covers 40% of a 10-chunk library, questions reuse the documents' words, and scoring is substring matching ("2%" would also accept "12%").
- Plan: benchmark v2 with more documents and harder questions.

## Day 16 results (benchmark v2)
- 103 questions: 101 pass (98.1%). Retrieval 84/85, answers 84/85, refusals 17/18, 2 silent errors, 0 errors.
- Weak groups: ambiguous (2/3) and tempting_not_in_docs (7/8).
- AM03: answer covered 2 of 3 documents. Cause (from the retrieved list): ___
- TU01: answered a neighbouring fact (2 GB of high speed data) to a question about maximum speed. Fix planned: answer only when the excerpts directly answer the question.
- Run-to-run check (v2b): ___

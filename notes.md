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

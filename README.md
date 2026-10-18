# Verity

![CI](https://github.com/narasimha4576/verity/actions/workflows/ci.yml/badge.svg)

A document assistant that answers from your PDFs, cites the page, and says "not found" instead of guessing.

## How it works

1. **Load and chunk:** each PDF page is split into overlapping chunks that keep their page number.
2. **Embed and store:** chunks become vectors (Gemini embeddings) stored in ChromaDB.
3. **Retrieve:** a question is embedded and the closest chunks are found.
4. **Answer:** the AI reads only those chunks and returns JSON with citations.
5. **Verify:** code checks the similarity score, the JSON shape and that every cited page was really retrieved.

Every answer has a status: `answered`, `not_found`, `low_similarity`, `ungrounded` or `invalid_output`.

## Design decisions

| Decision | Why | Trade-off |
|---|---|---|
| Answer only from retrieved excerpts | Stops the AI filling gaps from memory | Cannot answer general questions |
| Similarity floor before calling the AI | Unrelated questions are refused cheaply and safely | The threshold needs measuring (planned) |
| JSON output checked with Pydantic | Code can verify the answer, free text cannot be verified | Needs a model that supports structured output |
| Reject citations the AI never saw | Catches invented page numbers | Extra code to maintain |
| Retry only temporary errors | Busy services recover, a wrong key never does | Needs error classification |
| Fake AI and fake embeddings in tests | Tests are free, fast and need no key | Real model behaviour is measured separately |

## Run it

    pip install -r requirements.txt -r requirements-dev.txt
    copy .env.example .env      # then fill in your Gemini key and model
    python -m app.ingest data\your.pdf
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000 for the chat screen. The API docs are at /docs.

## Status and roadmap

Done: ingestion, retrieval, grounded answers, checks, API, tests, CI.
Next: chat screen, Docker, benchmark, guarded web-search fallback.

All sample documents are fake.

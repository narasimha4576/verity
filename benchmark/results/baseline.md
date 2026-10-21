# Verity benchmark

Run 2026-10-21, model gemini-3.1-flash-lite, embeddings gemini-embedding-001, top-k 4, similarity floor 0.55.

| Metric | Result |
|---|---|
| Retrieval hit rate (right page in the top results) | 47/47 (100.0%) |
| Answer accuracy (answerable questions) | 47/47 (100.0%) |
| Correct refusals (questions not in the documents) | 10/10 (100.0%) |
| Silent errors (wrong answer or invented answer shown) | 0 |
| Wrong answers shown | 0 |
| Invented answers to unanswerable questions | 0 |
| Right answer, wrong citation | 0 |
| False refusals (answerable but refused) | 0 |
| Standalone questions rewritten after a chat | 0/3 (0.0%) |
| Overall pass rate | 57/57 (100.0%) |
| Questions that errored (not scored) | 0 |

## By category

| Category | Passed |
|---|---|
| policy_fact | 17/17 (100.0%) |
| loan_fact | 16/16 (100.0%) |
| cross_document | 4/4 (100.0%) |
| not_in_documents | 9/9 (100.0%) |
| follow_up | 6/6 (100.0%) |
| standalone_after_chat | 3/3 (100.0%) |
| filtered | 2/2 (100.0%) |

## Questions to review

None.

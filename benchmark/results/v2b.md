# Verity benchmark

Run 2026-10-23, model gemini-3.1-flash-lite, embeddings gemini-embedding-001, top-k 4, similarity floor 0.55.

| Metric | Result |
|---|---|
| Retrieval hit rate (right page in the top results) | 84/85 (98.8%) |
| Answer accuracy (answerable questions) | 84/85 (98.8%) |
| Correct refusals (questions not in the documents) | 17/18 (94.4%) |
| Silent errors (wrong answer or invented answer shown) | 2 |
| Wrong answers shown | 1 |
| Invented answers to unanswerable questions | 1 |
| Right answer, wrong citation | 0 |
| False refusals (answerable but refused) | 0 |
| Standalone questions rewritten after a chat | 0/3 (0.0%) |
| Overall pass rate | 101/103 (98.1%) |
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
| paraphrase | 8/8 (100.0%) |
| confusable | 10/10 (100.0%) |
| ambiguous | 2/3 (66.7%) |
| computed | 6/6 (100.0%) |
| typo | 5/5 (100.0%) |
| conditional | 6/6 (100.0%) |
| tempting_not_in_docs | 7/8 (87.5%) |

## Questions to review

- AM03 [wrong_answer] How many days do I have to cancel or return something? Status: answered. Answer: You have 15 days to cancel an insurance policy after receiving it, and 7 days to return a laptop if it is unopened. Expected: sample_policy.pdf p.4, sample_warranty.pdf p.2, sample_savings.pdf p.2.
- TU01 [hallucination] What is the maximum data speed on the mobile plan? Status: answered. Answer: The plan includes 2 GB of high speed data every day. Expected: no answer.

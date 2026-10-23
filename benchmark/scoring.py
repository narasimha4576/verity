"""Scoring for the Verity benchmark. Pure functions: no network, no AI.

Each question has a ground truth: whether it is answerable, which page(s)
hold the answer, and answer_keys, a list of groups. A group is a list of
accepted spellings; the answer must contain one spelling from every group.
"""
import re

CATEGORIES = [
    "policy_fact",
    "loan_fact",
    "cross_document",
    "not_in_documents",
    "follow_up",
    "standalone_after_chat",
    "filtered",
    "paraphrase",
    "confusable",
    "ambiguous",
    "computed",
    "typo",
    "conditional",
    "tempting_not_in_docs",
]
PASSING = {"correct", "correct_refusal"}


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def contains_key(text, option):
    """Is this accepted spelling in the (normalized) answer text?

    Keys with digits must not sit inside a longer number, so "2%" does not
    match "12%" and "500" does not match "2,500" or "5000".
    """
    pattern = re.escape(normalize(option))
    if any(ch.isdigit() for ch in option):
        pattern = r"(?<!\d)(?<!\d[.,])" + pattern + r"(?!\d)(?!,\d)"
    return re.search(pattern, text) is not None


def keys_match(answer, groups):
    text = normalize(answer)
    return all(any(contains_key(text, option) for option in group) for group in groups)


def pairs(items):
    return {(item["source"], item["page"]) for item in items}


def score_question(question, record):
    """Return the outcome for one question.

    answerable: correct, wrong_answer (shown but wrong), miscited
                (right answer, wrong page), false_refusal
    unanswerable: correct_refusal, hallucination (an answer was shown)
    """
    if record.get("error"):
        return {"outcome": "error"}

    status = record["status"]
    result = {}
    history = question.get("history")
    if history:
        used = record.get("question_used") or ""
        result["rewrite_changed"] = normalize(used) != normalize(question["question"])

    if not question["answerable"]:
        result["outcome"] = "hallucination" if status == "answered" else "correct_refusal"
        return result

    expected = pairs(question["expected"])
    result["retrieval_hit"] = expected <= pairs(record.get("retrieved", []))
    if status != "answered":
        result["outcome"] = "false_refusal"
    elif not keys_match(record["answer"], question["answer_keys"]):
        result["outcome"] = "wrong_answer"
    elif not expected <= pairs(record["sources"]):
        result["outcome"] = "miscited"
    else:
        result["outcome"] = "correct"
    return result


def pct(part, whole):
    return "n/a" if whole == 0 else f"{part}/{whole} ({100 * part / whole:.1f}%)"


def summarize(questions, records):
    scored = []
    for q in questions:
        record = records.get(q["id"])
        if record is None:
            continue
        item = score_question(q, record)
        item.update(id=q["id"], category=q["category"], answerable=q["answerable"])
        scored.append(item)

    valid = [s for s in scored if s["outcome"] != "error"]
    answerable = [s for s in valid if s["answerable"]]
    unanswerable = [s for s in valid if not s["answerable"]]

    def count(items, outcome):
        return sum(1 for s in items if s["outcome"] == outcome)

    standalone = [s for s in valid if s["category"] == "standalone_after_chat"]
    by_category = {}
    for s in valid:
        row = by_category.setdefault(s["category"], {"total": 0, "passed": 0})
        row["total"] += 1
        row["passed"] += s["outcome"] in PASSING

    wrong = count(answerable, "wrong_answer")
    hallucinated = count(unanswerable, "hallucination")
    return {
        "run": len(scored),
        "errors": len(scored) - len(valid),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "retrieval_hits": sum(1 for s in answerable if s.get("retrieval_hit")),
        "correct": count(answerable, "correct"),
        "wrong_answer": wrong,
        "miscited": count(answerable, "miscited"),
        "false_refusal": count(answerable, "false_refusal"),
        "correct_refusal": count(unanswerable, "correct_refusal"),
        "hallucination": hallucinated,
        "silent_errors": wrong + hallucinated,
        "passed": sum(1 for s in valid if s["outcome"] in PASSING),
        "valid": len(valid),
        "standalone_total": len(standalone),
        "standalone_rewritten": sum(1 for s in standalone if s.get("rewrite_changed")),
        "by_category": by_category,
        "scored": scored,
    }


def format_report(summary, questions, records, meta=None):
    s = summary
    lines = ["# Verity benchmark", ""]
    if meta:
        lines.append(
            f"Run {meta.get('date', '')}, model {meta.get('model', '?')}, "
            f"embeddings {meta.get('embed_model', '?')}, top-k {meta.get('k', '?')}, "
            f"similarity floor {meta.get('min_score', '?')}."
        )
        lines.append("")
    lines += [
        "| Metric | Result |",
        "|---|---|",
        f"| Retrieval hit rate (right page in the top results) | {pct(s['retrieval_hits'], s['answerable'])} |",
        f"| Answer accuracy (answerable questions) | {pct(s['correct'], s['answerable'])} |",
        f"| Correct refusals (questions not in the documents) | {pct(s['correct_refusal'], s['unanswerable'])} |",
        f"| Silent errors (wrong answer or invented answer shown) | {s['silent_errors']} |",
        f"| Wrong answers shown | {s['wrong_answer']} |",
        f"| Invented answers to unanswerable questions | {s['hallucination']} |",
        f"| Right answer, wrong citation | {s['miscited']} |",
        f"| False refusals (answerable but refused) | {s['false_refusal']} |",
        f"| Standalone questions rewritten after a chat | {pct(s['standalone_rewritten'], s['standalone_total'])} |",
        f"| Overall pass rate | {pct(s['passed'], s['valid'])} |",
        f"| Questions that errored (not scored) | {s['errors']} |",
        "",
        "## By category",
        "",
        "| Category | Passed |",
        "|---|---|",
    ]
    for name in CATEGORIES:
        row = s["by_category"].get(name)
        if row:
            lines.append(f"| {name} | {pct(row['passed'], row['total'])} |")

    by_id = {q["id"]: q for q in questions}
    problems = [x for x in s["scored"] if x["outcome"] not in PASSING]
    lines += ["", "## Questions to review", ""]
    if not problems:
        lines.append("None.")
    for item in problems:
        q = by_id[item["id"]]
        record = records[item["id"]]
        if item["outcome"] == "error":
            lines.append(f"- {q['id']} (error: {record.get('error')}) {q['question']}")
            continue
        answer = (record.get("answer") or "").replace("\n", " ")[:220]
        expected = ", ".join(f"{e['source']} p.{e['page']}" for e in q.get("expected", [])) or "no answer"
        lines.append(
            f"- {q['id']} [{item['outcome']}] {q['question']} "
            f"Status: {record['status']}. Answer: {answer} Expected: {expected}."
        )
    return "\n".join(lines) + "\n"

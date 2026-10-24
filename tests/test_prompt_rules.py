import json
from pathlib import Path

from app.answer import SYSTEM_RULES

BENCH = Path(__file__).resolve().parent.parent / "benchmark" / "questions.json"
QUESTIONS = json.loads(BENCH.read_text(encoding="utf-8"))


def test_rules_allow_arithmetic_but_say_a_related_fact_is_not_an_answer():
    text = SYSTEM_RULES.lower()
    assert "arithmetic" in text
    assert "related fact is not an answer" in text


def test_the_prompt_never_contains_a_benchmark_question():
    # Teaching to the test would make the benchmark meaningless.
    text = SYSTEM_RULES.lower()
    for question in QUESTIONS:
        assert question["question"].lower() not in text

"""Run the benchmark against the real pipeline.

    python -m benchmark.run --name baseline

It builds a temporary store from benchmark/docs, so your own documents are
never touched. Progress is saved after every question, so a network drop can be
resumed by running the same command again.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from benchmark.scoring import format_report, summarize

HERE = Path(__file__).parent
K = 4


def load_questions():
    return json.loads((HERE / "questions.json").read_text(encoding="utf-8"))


def run_questions(questions, answer_fn, retrieve_fn, done=None, on_record=None,
                  delay=0.0, sleep=time.sleep):
    """Ask every question that has no result yet. A failed question is recorded
    (error type only) and the run continues."""
    records = dict(done or {})
    for q in questions:
        if q["id"] in records:
            continue
        started = time.time()
        try:
            result = answer_fn(q)
            record = {
                "id": q["id"],
                "status": result["status"],
                "answer": result["answer"],
                "sources": result["sources"],
                "question_used": result.get("question_used"),
                "retrieved": retrieve_fn(q, result.get("question_used") or q["question"]),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - one failed question must not stop the run
            record = {"id": q["id"], "status": None, "answer": "", "sources": [],
                      "question_used": None, "retrieved": [], "error": type(exc).__name__}
        record["seconds"] = round(time.time() - started, 2)
        records[q["id"]] = record
        if on_record:
            on_record(records)
        sleep(delay)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="latest", help="results file name")
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between questions")
    parser.add_argument("--fresh", action="store_true", help="ignore saved progress")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from app.answer import answer_question
    from app.embedder import embed_texts
    from app.ingest import ingest
    from app.store import VectorStore

    questions = load_questions()[: args.limit]
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    json_path = results_dir / f"{args.name}.json"

    done = {}
    if json_path.exists() and not args.fresh:
        saved = json.loads(json_path.read_text(encoding="utf-8"))["records"]
        done = {k: v for k, v in saved.items() if not v.get("error")}
        print(f"Resuming: {len(done)} questions already answered.")

    meta = {
        "date": date.today().isoformat(),
        "model": os.getenv("GEMINI_MODEL"),
        "embed_model": os.getenv("EMBED_MODEL", "gemini-embedding-001"),
        "k": K,
        "min_score": float(os.getenv("MIN_SCORE", "0.55")),
    }

    def save(records):
        payload = {"meta": meta, "records": records}
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(path=Path(tmp) / "db")
        for pdf in sorted((HERE / "docs").glob("*.pdf")):
            print(f"Indexing {pdf.name}: {ingest(pdf, store=store)} chunks")

        def answer_fn(q):
            return answer_question(q["question"], store=store,
                                   history=q.get("history"), sources=q.get("sources"), k=K)

        def retrieve_fn(q, used):
            vector = embed_texts([used], task_type="RETRIEVAL_QUERY")[0]
            hits = store.search(vector, k=K, sources=q.get("sources"))
            return [{"source": h["source"], "page": h["page"], "score": round(h["score"], 3)}
                    for h in hits]

        def progress(records):
            save(records)
            print(f"  {len(records)}/{len(questions)} done", end="\r")

        records = run_questions(questions, answer_fn, retrieve_fn, done=done,
                                on_record=progress, delay=args.delay)

    save(records)
    summary = summarize(questions, records)
    report = format_report(summary, questions, records, meta)
    (results_dir / f"{args.name}.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()

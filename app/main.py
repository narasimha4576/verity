import json
import logging
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from pypdf.errors import PdfReadError

from app.answer import answer_events, answer_question, generate, rewrite_generate
from app.embedder import embed_texts
from app.ingest import ingest
from app.retry import is_temporary
from app.store import VectorStore

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
STATIC_DIR = Path(__file__).parent / "static"

logger = logging.getLogger("verity")
app = FastAPI(title="Verity")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[Turn] = Field(default_factory=list, max_length=20)
    sources: list[str] | None = Field(default=None, max_length=20)

    @field_validator("sources")
    @classmethod
    def names_must_be_short(cls, value):
        if value and any(len(name) > 255 for name in value):
            raise ValueError("document name is too long")
        return value


@lru_cache
def get_store():
    return VectorStore()


def get_embed():
    return embed_texts


def get_llm():
    return generate


def get_rewriter():
    return rewrite_generate


def get_upload_dir():
    return Path(os.getenv("UPLOAD_DIR", "data/uploads"))


StoreDep = Annotated[VectorStore, Depends(get_store)]
EmbedDep = Annotated[Callable, Depends(get_embed)]
LlmDep = Annotated[Callable, Depends(get_llm)]
RewriterDep = Annotated[Callable, Depends(get_rewriter)]
DirDep = Annotated[Path, Depends(get_upload_dir)]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
def upload(
    file: Annotated[UploadFile, File()],
    store: StoreDep,
    embed: EmbedDep,
    upload_dir: DirDep,
):
    # Never trust the file name: keep only the last part so "../../x.pdf" is harmless
    name = Path(file.filename or "").name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a real PDF.")

    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / name
    path.write_bytes(data)

    try:
        chunks = ingest(path, store=store, embed=embed)
    except PdfReadError:
        raise HTTPException(422, "The PDF could not be read.") from None
    if chunks == 0:
        raise HTTPException(422, "No readable text found. Scanned PDFs are not supported.")
    return {"filename": name, "chunks": chunks}


@app.get("/documents")
def documents(store: StoreDep):
    return {"documents": store.list_sources()}


@app.delete("/documents/{name}")
def delete_document(name: str, store: StoreDep, upload_dir: DirDep):
    removed = store.delete_source(name)
    if removed == 0:
        raise HTTPException(404, "Document not found.")
    # Only names that were really stored reach this line, and they came from
    # sanitised upload names, so this can only touch a file inside upload_dir
    path = upload_dir / name
    if Path(name).name == name and path.is_file():
        path.unlink()
    return {"filename": name, "chunks_removed": removed}


@app.post("/ask")
def ask(
    body: AskRequest,
    store: StoreDep,
    embed: EmbedDep,
    llm: LlmDep,
    rewriter: RewriterDep,
):
    try:
        return answer_question(
            body.question,
            store=store,
            embed=embed,
            llm=llm,
            history=[t.model_dump() for t in body.history],
            rewriter=rewriter,
            sources=body.sources,
        )
    except Exception as exc:
        if is_temporary(exc):
            raise HTTPException(
                503, "The AI service is busy. Please try again shortly."
            ) from None
        raise


def _event_lines(events):
    """Send each event as one JSON line. Once streaming has started the HTTP
    status cannot change, so failures become an error event. Internal details
    are logged on the server and never sent to the user."""
    try:
        for event in events:
            yield json.dumps(event) + "\n"
    except Exception as exc:
        if is_temporary(exc):
            message = "The AI service is busy. Please try again shortly."
        else:
            logger.exception("Unexpected error while answering")
            message = "Something went wrong. Please try again."
        yield json.dumps({"event": "error", "message": message}) + "\n"


@app.post("/ask/stream")
def ask_stream(
    body: AskRequest,
    store: StoreDep,
    embed: EmbedDep,
    llm: LlmDep,
    rewriter: RewriterDep,
):
    events = answer_events(
        body.question,
        store=store,
        embed=embed,
        llm=llm,
        history=[t.model_dump() for t in body.history],
        rewriter=rewriter,
        sources=body.sources,
    )
    return StreamingResponse(_event_lines(events), media_type="application/x-ndjson")



@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")

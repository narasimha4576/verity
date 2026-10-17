import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf.errors import PdfReadError

from app.answer import answer_question, generate, rewrite_generate
from app.embedder import embed_texts
from app.ingest import ingest
from app.retry import is_temporary
from app.store import VectorStore

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="Verity")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[Turn] = Field(default_factory=list, max_length=20)


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
        )
    except Exception as exc:
        if is_temporary(exc):
            raise HTTPException(
                503, "The AI service is busy. Please try again shortly."
            ) from None
        raise

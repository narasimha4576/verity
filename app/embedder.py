import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.retry import with_retry

load_dotenv()


def embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", batch_size=50):
    """Turn texts into vectors. Use RETRIEVAL_DOCUMENT for chunks and
    RETRIEVAL_QUERY for questions."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    model = os.getenv("EMBED_MODEL", "gemini-embedding-001")
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        result = with_retry(
            lambda b=batch: client.models.embed_content(
                model=model,
                contents=b,
                config=types.EmbedContentConfig(task_type=task_type),
            )
        )
        vectors.extend(e.values for e in result.embeddings)
    return vectors

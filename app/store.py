import chromadb


class VectorStore:
    def __init__(self, path="chroma_db", name="verity"):
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks, embeddings):
        """Upsert, so ingesting the same file twice does not duplicate chunks."""
        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "page": c["page"]} for c in chunks],
        )

    def count(self):
        return self.collection.count()

    def search(self, query_embedding, k=4):
        total = self.count()
        if total == 0:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding], n_results=min(k, total)
        )
        hits = []
        for cid, text, meta, dist in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            hits.append({
                "id": cid,
                "text": text,
                "source": meta["source"],
                "page": meta["page"],
                "score": 1 - dist,  # cosine similarity: higher is closer
            })
        return hits

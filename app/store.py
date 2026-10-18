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

    def delete_source(self, source):
        """Remove every chunk of one document. Returns how many were removed."""
        ids = self.collection.get(where={"source": source})["ids"]
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def replace_source(self, source, chunks, embeddings):
        """Swap a document for its new version, so no stale chunks remain."""
        self.delete_source(source)
        self.add_chunks(chunks, embeddings)

    def list_sources(self):
        metas = self.collection.get(include=["metadatas"])["metadatas"]
        counts = {}
        for meta in metas:
            counts[meta["source"]] = counts.get(meta["source"], 0) + 1
        return [{"source": s, "chunks": n} for s, n in sorted(counts.items())]

    def count(self):
        return self.collection.count()

    def search(self, query_embedding, k=4, sources=None):
        """Find the closest chunks. If sources is given, search only those documents."""
        where = {"source": {"$in": list(sources)}} if sources else None
        total = len(self.collection.get(where=where)["ids"]) if where else self.count()
        if total == 0:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding], n_results=min(k, total), where=where
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

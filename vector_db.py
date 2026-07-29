import os
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


class QdrantStorage:
    def __init__(self, url=None, api_key=None, collection="docs", dim=3072):
        url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.client = QdrantClient(url=url, api_key=api_key, timeout=30)
        self.collection = collection
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        records = self.client.retrieve(
            collection_name=self.collection,
            ids=ids,
            with_payload=False,
            with_vectors=False,
        )
        return {str(r.id) for r in records}

    def upsert(self, ids, vectors, payloads):
        points = [PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i]) for i in range(len(ids))]
        self.client.upsert(self.collection, points=points)

    def search(self, query_vector, top_k: int = 5):
        results = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            with_payload=True,
            limit=top_k
        ).points
        contexts = []
        sources = set()

        for r in results:
            payload = getattr(r, "payload", None) or {}
            text = payload.get("text", "")
            source = payload.get("source", "")
            if text:
                contexts.append(text)
                sources.add(source)

        return {"contexts": contexts, "sources": list(sources)}
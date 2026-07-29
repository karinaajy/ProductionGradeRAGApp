import logging
import threading
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import inngest
import inngest.fast_api
from inngest.experimental import ai
from dotenv import load_dotenv
import uuid
import os
import datetime
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from custom_types import RAQQueryResult, RAGSearchResult, RAGUpsertResult, RAGChunkAndSrc

load_dotenv()

INNGEST_DEV_SERVER_URL = os.getenv("INNGEST_DEV_SERVER_URL", "http://127.0.0.1:8288")
INNGEST_ENV = os.getenv("INNGEST_ENV")

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=INNGEST_ENV == "production",
    event_key=os.getenv("INNGEST_EVENT_KEY"),
    signing_key=os.getenv("INNGEST_SIGNING_KEY"),
    api_base_url=INNGEST_DEV_SERVER_URL if INNGEST_ENV != "production" else None,
    event_api_base_url=INNGEST_DEV_SERVER_URL if INNGEST_ENV != "production" else None,
    serializer=inngest.PydanticSerializer()
)

_results_store: dict[str, dict] = {}
_results_lock = threading.Lock()


def load_pdf_chunks(pdf_path: str, source_id: str) -> RAGChunkAndSrc:
    chunks = load_and_chunk_pdf(pdf_path)
    return RAGChunkAndSrc(chunks=chunks, source_id=source_id)


def upsert_chunks(chunks_and_src: RAGChunkAndSrc) -> RAGUpsertResult:
    chunks = chunks_and_src.chunks
    source_id = chunks_and_src.source_id
    store = QdrantStorage()

    all_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
    already_ingested = store.existing_ids(all_ids)

    new_indices = [i for i in range(len(chunks)) if all_ids[i] not in already_ingested]

    if not new_indices:
        return RAGUpsertResult(ingested=0)

    new_chunks = [chunks[i] for i in new_indices]
    new_ids = [all_ids[i] for i in new_indices]

    vecs = embed_texts(new_chunks)
    payloads = [{"source": source_id, "text": new_chunks[i]} for i in range(len(new_chunks))]

    store.upsert(new_ids, vecs, payloads)
    return RAGUpsertResult(ingested=len(new_chunks))


@inngest_client.create_function(
    fn_id="RAG: Ingest PDF",
    trigger=inngest.TriggerEvent(event="rag/ingest_pdf"),
    throttle=inngest.Throttle(
        limit=2, period=datetime.timedelta(minutes=1)
    ),
    rate_limit=inngest.RateLimit(
        limit=1,
        period=datetime.timedelta(hours=4),
        key="event.data.source_id",
  ),
)
async def rag_ingest_pdf(ctx: inngest.Context):
    pdf_path = ctx.event.data["pdf_path"]
    source_id = ctx.event.data.get("source_id", pdf_path)

    chunks_and_src = await ctx.step.run(
        "load-and-chunk",
        lambda: load_pdf_chunks(pdf_path, source_id),
        output_type=RAGChunkAndSrc,
    )
    ingested = await ctx.step.run(
        "embed-and-upsert",
        lambda: upsert_chunks(chunks_and_src),
        output_type=RAGUpsertResult,
    )
    return ingested.model_dump()


def search_chunks(question: str, top_k: int = 5) -> RAGSearchResult:
    query_vec = embed_texts([question])[0]
    store = QdrantStorage()
    found = store.search(query_vec, top_k)
    return RAGSearchResult(contexts=found["contexts"], sources=found["sources"])


@inngest_client.create_function(
    fn_id="RAG: Query PDF",
    trigger=inngest.TriggerEvent(event="rag/query_pdf_ai")
)
async def rag_query_pdf_ai(ctx: inngest.Context):
    question = ctx.event.data["question"]
    top_k = int(ctx.event.data.get("top_k", 5))

    found = await ctx.step.run(
        "embed-and-search",
        lambda: search_chunks(question, top_k),
        output_type=RAGSearchResult,
    )

    context_block = "\n\n".join(f"- {c}" for c in found.contexts)
    user_content = (
        "Use the following context to answer the question.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n"
        "Answer concisely using the context above."
    )

    adapter = ai.openai.Adapter(
        auth_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini"
    )

    res = await ctx.step.ai.infer(
        "llm-answer",
        adapter=adapter,
        body={
            "max_tokens": 1024,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "You answer questions using only the provided context."},
                {"role": "user", "content": user_content}
            ]
        }
    )

    answer = res["choices"][0]["message"]["content"].strip()
    result = {"answer": answer, "sources": found.sources, "num_contexts": len(found.contexts)}

    with _results_lock:
        _results_store[ctx.event.id] = result

    return result

app = FastAPI()


@app.get("/results/{event_id}")
async def get_result(event_id: str):
    with _results_lock:
        result = _results_store.get(event_id)
    if result is None:
        return JSONResponse(status_code=202, content={"status": "pending"})
    return {"status": "completed", "output": result}


inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf_ai])
from unittest.mock import MagicMock, patch
import uuid

def test_skips_embedding_for_already_ingested_chunks(mocker):
    from vector_db import QdrantStorage

    chunks = ["chunk one", "chunk two"]
    source_id = "test.pdf"
    all_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]

    mocker.patch("vector_db.QdrantClient.collection_exists", return_value=True)
    store = QdrantStorage()
    # simulate that the first chunk already exists in Qdrant
    store.existing_ids = MagicMock(return_value={all_ids[0]})

    embed_mock = mocker.patch("main.embed_texts", return_value=[[0.1] * 3072])
    store.upsert = MagicMock()

    from main import rag_ingest_pdf  # import after patching if needed

    # call the inner _upsert logic directly, or refactor it out for easier testing
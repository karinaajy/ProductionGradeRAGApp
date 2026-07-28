from unittest.mock import MagicMock
from vector_db import QdrantStorage

def test_existing_ids_returns_matching_set(mocker):
    mocker.patch("vector_db.QdrantClient.collection_exists", return_value=True)
    store = QdrantStorage()
    fake_record = MagicMock()
    fake_record.id = "abc123"
    store.client.retrieve = MagicMock(return_value=[fake_record])

    result = store.existing_ids(["abc123", "def456"])
    assert result == {"abc123"}

def test_existing_ids_empty_input_returns_empty_set(mocker):
    mocker.patch("vector_db.QdrantClient.collection_exists", return_value=True)
    store = QdrantStorage()
    assert store.existing_ids([]) == set()
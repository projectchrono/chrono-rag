from unittest.mock import patch, MagicMock, call
from src.preprocess.dataparser import Document
from src.preprocess.vectorstore import upsert_documents


def _make_doc(name: str = "MyClass") -> Document:
    return Document(
        content="class MyClass {}",
        source_repo="chrono",
        file_path="test.h",
        language="cpp",
        chunk_type="class",
        chunk_name=name,
        embedding=[0.1] * 1536,
    )


def _mock_mongo():
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection
    return mock_client, mock_collection


def test_upsert_documents_calls_update_one_per_doc():
    docs = [_make_doc("ClassA"), _make_doc("ClassB")]
    mock_client, mock_collection = _mock_mongo()

    with patch("src.preprocess.vectorstore.MongoClient", return_value=mock_client):
        upsert_documents(docs)

    assert mock_collection.update_one.call_count == 2


def test_upsert_documents_uses_upsert_true():
    docs = [_make_doc()]
    mock_client, mock_collection = _mock_mongo()

    with patch("src.preprocess.vectorstore.MongoClient", return_value=mock_client):
        upsert_documents(docs)

    _, kwargs = mock_collection.update_one.call_args
    assert kwargs.get("upsert") is True


def test_upsert_documents_filter_key():
    doc = _make_doc("Foo")
    mock_client, mock_collection = _mock_mongo()

    with patch("src.preprocess.vectorstore.MongoClient", return_value=mock_client):
        upsert_documents([doc])

    filter_arg = mock_collection.update_one.call_args[0][0]
    assert filter_arg["file_path"] == "test.h"
    assert filter_arg["chunk_name"] == "Foo"


def test_upsert_documents_sets_embedding():
    doc = _make_doc()
    mock_client, mock_collection = _mock_mongo()

    with patch("src.preprocess.vectorstore.MongoClient", return_value=mock_client):
        upsert_documents([doc])

    set_arg = mock_collection.update_one.call_args[0][1]["$set"]
    assert set_arg["embedding"] == [0.1] * 1536

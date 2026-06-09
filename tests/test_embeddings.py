from unittest.mock import patch, MagicMock
from src.preprocess.dataparser import Document
from src.preprocess.embeddings import generate_embeddings


def _make_doc(content: str = "test content") -> Document:
    return Document(
        content=content, source_repo="chrono", file_path="test.py",
        language="py", chunk_type="function", chunk_name="test_func",
    )


def test_generate_embeddings_attaches_vectors():
    docs = [_make_doc("hello"), _make_doc("world")]
    fake = [[0.1] * 1536, [0.2] * 1536]

    with patch("src.preprocess.embeddings.OpenAIEmbeddings") as mock_cls:
        mock_cls.return_value.embed_documents.return_value = fake
        result = generate_embeddings(docs)

    assert result[0].embedding == [0.1] * 1536
    assert result[1].embedding == [0.2] * 1536


def test_generate_embeddings_batches_correctly():
    docs = [_make_doc(f"doc {i}") for i in range(5)]
    single_emb = [0.1] * 1536

    with patch("src.preprocess.embeddings.OpenAIEmbeddings") as mock_cls:
        mock_instance = mock_cls.return_value
        # Return 3 embeddings for first batch, 2 for second
        mock_instance.embed_documents.side_effect = [
            [single_emb] * 3,
            [single_emb] * 2,
        ]
        result = generate_embeddings(docs, batch_size=3)

    assert mock_instance.embed_documents.call_count == 2
    assert all(d.embedding == single_emb for d in result)


def test_generate_embeddings_returns_same_objects():
    docs = [_make_doc()]
    with patch("src.preprocess.embeddings.OpenAIEmbeddings") as mock_cls:
        mock_cls.return_value.embed_documents.return_value = [[0.5] * 1536]
        result = generate_embeddings(docs)
    assert result is docs  # mutates in-place and returns same list

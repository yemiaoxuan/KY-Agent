import pytest

from app.services.rag.langchain_vector_store import SQLAlchemyPgVectorStore


class _FakeEmbeddings:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.vectors

    def embed_query(self, text: str) -> list[float]:
        return [0.0]


class _RollbackTrackingSession:
    def __init__(self) -> None:
        self.rollback_called = False

    def rollback(self) -> None:
        self.rollback_called = True


class _FakeDocument:
    def __init__(self) -> None:
        self.title = "old"
        self.description = "old"
        self.visibility = "public"
        self.doc_metadata = {"old": True}


class _FakeQuery:
    def __init__(self, document) -> None:
        self.document = document

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.document


class _ExistingDocumentSession(_RollbackTrackingSession):
    def __init__(self, document) -> None:
        super().__init__()
        self.document = document

    def query(self, model):
        return _FakeQuery(self.document)


def test_add_texts_rejects_mismatched_embeddings_before_pg_write() -> None:
    db = _RollbackTrackingSession()
    store = SQLAlchemyPgVectorStore(db, embeddings=_FakeEmbeddings([[0.1]]))

    with pytest.raises(RuntimeError, match="Embedding count mismatch"):
        store.add_texts(["first", "second"])

    assert not db.rollback_called


def test_upsert_document_replaces_existing_document_chunks(monkeypatch) -> None:
    document = _FakeDocument()
    db = _ExistingDocumentSession(document)
    store = SQLAlchemyPgVectorStore(db, embeddings=_FakeEmbeddings([]))
    captured: dict = {}

    def _replace(existing_document, **kwargs):
        captured["document"] = existing_document
        captured["kwargs"] = kwargs
        return existing_document

    monkeypatch.setattr(store, "replace_document_chunks", _replace)

    result = store.upsert_document(
        title="new",
        description="updated",
        file_path="/tmp/note.md",
        file_type="md",
        visibility="public",
        original_filename="note.md",
        document_metadata={"source": "test"},
        texts=["content"],
    )

    assert result is document
    assert document.title == "new"
    assert document.description == "updated"
    assert document.doc_metadata["old"] is True
    assert document.doc_metadata["source"] == "test"
    assert captured["document"] is document
    assert captured["kwargs"]["texts"] == ["content"]


def test_replace_document_chunks_rejects_mismatched_embeddings_before_pg_write() -> None:
    db = _RollbackTrackingSession()
    store = SQLAlchemyPgVectorStore(db, embeddings=_FakeEmbeddings([[0.1]]))

    with pytest.raises(RuntimeError, match="Embedding count mismatch"):
        store.replace_document_chunks(
            document=object(),
            texts=["first", "second"],
        )

    assert not db.rollback_called

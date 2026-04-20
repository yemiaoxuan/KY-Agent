from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.services.rag.retrieval_service import document_to_search_result, documents_to_context
from app.services.rag.search_service import answer_with_rag


def test_document_to_search_result_uses_document_metadata() -> None:
    document = Document(
        id="chunk-1",
        page_content="content",
        metadata={
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "title": "Test Title",
            "score": 0.8,
            "file_type": "md",
        },
    )

    result = document_to_search_result(document)

    assert result.document_id == "doc-1"
    assert result.chunk_id == "chunk-1"
    assert result.title == "Test Title"
    assert result.content == "content"
    assert result.score == 0.8
    assert result.metadata == {"file_type": "md"}


def test_documents_to_context_formats_numbered_sources() -> None:
    documents = [
        Document(page_content="chunk a", metadata={"title": "Doc A"}),
        Document(page_content="chunk b", metadata={"title": "Doc B"}),
    ]

    context = documents_to_context(documents)

    assert "[1] 标题：Doc A" in context
    assert "内容：chunk a" in context
    assert "[2] 标题：Doc B" in context
    assert "内容：chunk b" in context


def test_answer_with_rag_returns_fallback_when_llm_not_configured(monkeypatch) -> None:
    documents = [Document(page_content="retrieved text", metadata={"title": "Doc A"})]

    monkeypatch.setattr(
        "app.services.rag.search_service.search_public_documents",
        lambda db, question, limit: documents,
    )
    monkeypatch.setattr(
        "app.services.rag.search_service.get_settings",
        lambda: SimpleNamespace(llm_api_key="replace-me"),
    )

    response = answer_with_rag(db=None, question="test question", limit=3)

    assert "LLM_API_KEY 尚未配置" in response.answer
    assert len(response.sources) == 1
    assert response.sources[0].title == "Doc A"


def test_answer_with_rag_uses_standard_chain(monkeypatch) -> None:
    documents = [
        Document(
            page_content="retrieved text",
            metadata={"title": "Doc A", "document_id": "doc-1", "chunk_id": "chunk-1"},
        )
    ]

    monkeypatch.setattr(
        "app.services.rag.search_service.search_public_documents",
        lambda db, question, limit: documents,
    )
    monkeypatch.setattr(
        "app.services.rag.search_service.get_settings",
        lambda: SimpleNamespace(llm_api_key="configured"),
    )
    monkeypatch.setattr(
        "app.services.rag.search_service.get_llm",
        lambda: RunnableLambda(lambda prompt_value: AIMessage(content="答案 [1]")),
    )

    response = answer_with_rag(db=None, question="test question", limit=3)

    assert response.answer == "答案 [1]"
    assert len(response.sources) == 1
    assert response.sources[0].document_id == "doc-1"

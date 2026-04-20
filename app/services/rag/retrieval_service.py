from __future__ import annotations

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.schemas.search import SearchResult
from app.services.rag.langchain_vector_store import get_public_vector_store


def search_public_documents(
    db: Session,
    query: str,
    limit: int = 5,
) -> list[Document]:
    vector_store = get_public_vector_store(db)
    retriever = vector_store.as_retriever(
        search_kwargs={"k": limit, "filter": {"visibility": "public"}}
    )
    return retriever.invoke(query)


def search_public_documents_with_scores(
    db: Session,
    query: str,
    limit: int = 5,
) -> list[tuple[Document, float]]:
    vector_store = get_public_vector_store(db)
    return vector_store.similarity_search_with_score(
        query,
        k=limit,
        filter={"visibility": "public"},
    )


def search_public_chunks(
    db: Session,
    query: str,
    limit: int = 5,
) -> list[SearchResult]:
    docs_with_scores = search_public_documents_with_scores(db, query, limit)
    return [document_to_search_result(document, score) for document, score in docs_with_scores]


def document_to_search_result(document: Document, score: float | None = None) -> SearchResult:
    metadata = dict(document.metadata or {})
    resolved_score = float(score if score is not None else metadata.pop("score", 0.0))
    document_id = str(metadata.pop("document_id", ""))
    chunk_id = str(metadata.pop("chunk_id", document.id or ""))
    title = str(metadata.pop("title", ""))
    return SearchResult(
        document_id=document_id,
        chunk_id=chunk_id,
        title=title,
        content=document.page_content,
        score=resolved_score,
        metadata=metadata,
    )


def documents_to_context(documents: list[Document]) -> str:
    if not documents:
        return "无相关上下文"
    lines: list[str] = []
    for index, document in enumerate(documents, start=1):
        title = str((document.metadata or {}).get("title", ""))
        lines.append(f"[{index}] 标题：{title}\n内容：{document.page_content}")
    return "\n\n".join(lines)

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import UploadedDocument
from app.services.ai.embedding_service import get_configured_embeddings


class SQLAlchemyPgVectorStore(VectorStore):
    """LangChain VectorStore over the existing uploaded_documents/document_chunks schema."""

    def __init__(
        self,
        db: Session,
        *,
        embeddings: Embeddings | None = None,
        visibility: str = "public",
    ) -> None:
        self.db = db
        self._embeddings = embeddings or get_configured_embeddings()
        self.visibility = visibility

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Embeddings,
        metadatas: list[dict] | None = None,
        *,
        db: Session | None = None,
        **kwargs: Any,
    ) -> SQLAlchemyPgVectorStore:
        if db is None:
            raise ValueError("SQLAlchemyPgVectorStore.from_texts requires a db Session.")
        store = cls(db, embeddings=embedding, visibility=kwargs.get("visibility", "public"))
        store.add_texts(texts, metadatas=metadatas, ids=kwargs.get("ids"))
        return store

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: list[dict] | None = None,
        *,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        text_list = list(texts)
        if metadatas is not None and len(metadatas) != len(text_list):
            raise ValueError("The number of metadatas must match the number of texts.")
        if ids is not None and len(ids) != len(text_list):
            raise ValueError("The number of ids must match the number of texts.")

        title = kwargs.get("title") or "Untitled Document"
        description = kwargs.get("description")
        file_path = kwargs.get("file_path") or ""
        file_type = kwargs.get("file_type") or "text"
        visibility = kwargs.get("visibility") or self.visibility
        original_filename = kwargs.get("original_filename")
        document_metadata = kwargs.get("document_metadata") or {}

        vectors = self.embeddings.embed_documents(text_list) if text_list else []
        # 自定义 VectorStore 的价值在于：保留现有表结构，同时让上层继续按 LangChain 接口工作。
        if len(vectors) != len(text_list):
            raise RuntimeError(
                f"Embedding count mismatch: expected {len(text_list)}, got {len(vectors)}."
            )
        try:
            document = UploadedDocument(
                title=title,
                description=description,
                file_path=file_path,
                file_type=file_type,
                visibility=visibility,
                doc_metadata={
                    **document_metadata,
                    "original_filename": original_filename,
                    "chunk_count": len(text_list),
                },
            )
            self.db.add(document)
            self.db.flush()

            chunk_ids: list[str] = []
            for index, (content, vector) in enumerate(zip(text_list, vectors, strict=False)):
                metadata = metadatas[index] if metadatas is not None else {}
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    embedding=vector,
                    chunk_metadata={
                        "visibility": visibility,
                        "title": title,
                        **metadata,
                    },
                )
                self.db.add(chunk)
                self.db.flush()
                chunk_ids.append(str(chunk.id))
            self.db.commit()
            self.db.refresh(document)
        except Exception:
            self.db.rollback()
            raise
        return chunk_ids

    def upsert_document(
        self,
        *,
        title: str,
        description: str | None,
        file_path: str,
        file_type: str,
        texts: list[str],
        metadatas: list[dict] | None = None,
        visibility: str | None = None,
        original_filename: str | None = None,
        document_metadata: dict | None = None,
    ) -> UploadedDocument:
        resolved_visibility = visibility or self.visibility
        # upsert 语义按业务主键(file_path + file_type)复用已有文档，而不是重复插入文档行。
        document = (
            self.db.query(UploadedDocument)
            .filter(
                UploadedDocument.file_path == file_path,
                UploadedDocument.file_type == file_type,
            )
            .order_by(UploadedDocument.created_at.desc())
            .first()
        )
        metadata = {
            **(document_metadata or {}),
            "original_filename": original_filename,
        }
        if document is not None:
            document.title = title
            document.description = description
            document.visibility = resolved_visibility
            document.doc_metadata = {
                **(document.doc_metadata or {}),
                **metadata,
            }
            return self.replace_document_chunks(
                document,
                texts=texts,
                metadatas=metadatas,
                document_metadata=metadata,
            )

        self.add_texts(
            texts,
            metadatas=metadatas,
            title=title,
            description=description,
            file_path=file_path,
            file_type=file_type,
            visibility=resolved_visibility,
            original_filename=original_filename,
            document_metadata=document_metadata or {},
        )
        created = (
            self.db.query(UploadedDocument)
            .filter(
                UploadedDocument.file_path == file_path,
                UploadedDocument.file_type == file_type,
            )
            .order_by(UploadedDocument.created_at.desc())
            .first()
        )
        if created is None:
            raise RuntimeError("Failed to persist uploaded document.")
        return created

    def replace_document_chunks(
        self,
        document: UploadedDocument,
        *,
        texts: list[str],
        metadatas: list[dict] | None = None,
        document_metadata: dict | None = None,
    ) -> UploadedDocument:
        if metadatas is not None and len(metadatas) != len(texts):
            raise ValueError("The number of metadatas must match the number of texts.")

        vectors = self.embeddings.embed_documents(texts) if texts else []
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(vectors)}."
            )
        try:
            document.doc_metadata = {
                **(document.doc_metadata or {}),
                **(document_metadata or {}),
                "chunk_count": len(texts),
            }
            for chunk in list(document.chunks):
                self.db.delete(chunk)
            self.db.flush()

            for index, (content, vector) in enumerate(zip(texts, vectors, strict=False)):
                metadata = metadatas[index] if metadatas is not None else {}
                self.db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        embedding=vector,
                        chunk_metadata={
                            "visibility": document.visibility,
                            "title": document.title,
                            **metadata,
                        },
                    )
                )
            self.db.commit()
            self.db.refresh(document)
        except Exception:
            self.db.rollback()
            raise
        return document

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[Document]:
        return [doc for doc, _score in self.similarity_search_with_score(query, k=k, **kwargs)]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        query_vector = self.embeddings.embed_query(query)
        return self.similarity_search_by_vector_with_score(query_vector, k=k, **kwargs)

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        k: int = 4,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        visibility = kwargs.get("filter", {}).get("visibility", self.visibility)
        # 距离计算直接下推到 pgvector，LangChain 这里只负责对接 Document 抽象。
        distance = DocumentChunk.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(DocumentChunk, UploadedDocument, distance)
            .join(UploadedDocument, UploadedDocument.id == DocumentChunk.document_id)
            .where(UploadedDocument.visibility == visibility)
            .order_by(distance)
            .limit(k)
        )

        docs: list[tuple[Document, float]] = []
        for chunk, document, dist in self.db.execute(stmt):
            score = float(1 - dist) if dist is not None else 0.0
            metadata = {
                **(chunk.chunk_metadata or {}),
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "title": document.title,
                "file_path": document.file_path,
                "file_type": document.file_type,
                "visibility": document.visibility,
                "score": score,
            }
            docs.append(
                (
                    Document(
                        id=str(chunk.id),
                        page_content=chunk.content,
                        metadata=metadata,
                    ),
                    score,
                )
            )
        return docs


def get_public_vector_store(db: Session) -> SQLAlchemyPgVectorStore:
    return SQLAlchemyPgVectorStore(db, visibility="public")

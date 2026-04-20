from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.document import UploadedDocument
from app.services.content.file_extraction_service import chunk_text
from app.services.rag.langchain_vector_store import get_public_vector_store

_REPORT_INGEST_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="report-ingest")


def upsert_report_document(
    db: Session,
    *,
    title: str,
    description: str,
    markdown_path: Path,
    topic_name: str,
    report_date: str,
    visibility: str = "public",
) -> UploadedDocument:
    text = markdown_path.read_text(encoding="utf-8")
    chunks = chunk_text(text)

    existing = (
        db.query(UploadedDocument)
        .filter(
            UploadedDocument.file_path == str(markdown_path),
            UploadedDocument.file_type == "report_md",
        )
        .one_or_none()
    )
    if existing is None:
        existing = UploadedDocument(
            title=title,
            description=description,
            file_path=str(markdown_path),
            file_type="report_md",
            visibility=visibility,
            doc_metadata={
                "source": "daily_report",
                "topic_name": topic_name,
                "report_date": report_date,
                "chunk_count": len(chunks),
            },
        )
        db.add(existing)
        db.flush()
    else:
        existing.title = title
        existing.description = description
        existing.visibility = visibility
        existing.doc_metadata = {
            **(existing.doc_metadata or {}),
            "source": "daily_report",
            "topic_name": topic_name,
            "report_date": report_date,
            "chunk_count": len(chunks),
        }
    db.flush()

    metadatas = [
        {
            "visibility": visibility,
            "title": title,
            "source": "daily_report",
            "topic_name": topic_name,
            "report_date": report_date,
            "chunk_index": index,
        }
        for index, _chunk in enumerate(chunks)
    ]
    vector_store = get_public_vector_store(db)
    return vector_store.replace_document_chunks(
        existing,
        texts=chunks,
        metadatas=metadatas,
        document_metadata={
            "source": "daily_report",
            "topic_name": topic_name,
            "report_date": report_date,
        },
    )


def enqueue_report_document_upsert(
    *,
    title: str,
    description: str,
    markdown_path: Path,
    topic_name: str,
    report_date: str,
    visibility: str = "public",
) -> None:
    def _task() -> None:
        db = SessionLocal()
        try:
            upsert_report_document(
                db,
                title=title,
                description=description,
                markdown_path=markdown_path,
                topic_name=topic_name,
                report_date=report_date,
                visibility=visibility,
            )
        finally:
            db.close()

    _REPORT_INGEST_EXECUTOR.submit(_task)

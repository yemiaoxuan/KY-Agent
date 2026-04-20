from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import UploadedDocument
from app.services.content.file_extraction_service import chunk_text, detect_file_type, extract_text
from app.services.rag.langchain_vector_store import get_public_vector_store


async def save_upload_file(file: UploadFile) -> Path:
    settings = get_settings()
    suffix = Path(file.filename or "upload").suffix.lower()
    target = settings.uploads_dir / f"{uuid4()}{suffix}"
    content = await file.read()
    target.write_bytes(content)
    return target


def save_text_upload(content: str, suffix: str = ".md") -> Path:
    settings = get_settings()
    target = settings.uploads_dir / f"{uuid4()}{suffix}"
    target.write_text(content, encoding="utf-8")
    return target


def _persist_document(
    db: Session,
    *,
    path: Path,
    title: str,
    description: str | None,
    visibility: str,
    file_type: str,
    original_filename: str | None,
    text: str,
) -> UploadedDocument:
    chunks = chunk_text(text)
    metadatas = [
        {
            "visibility": visibility,
            "title": title,
            "chunk_index": index,
        }
        for index, _chunk in enumerate(chunks)
    ]
    vector_store = get_public_vector_store(db)
    return vector_store.upsert_document(
        title=title,
        description=description,
        file_path=str(path),
        file_type=file_type,
        visibility=visibility,
        original_filename=original_filename,
        texts=chunks,
        metadatas=metadatas,
    )


async def ingest_upload(
    db: Session,
    file: UploadFile,
    title: str | None = None,
    description: str | None = None,
    visibility: str = "public",
) -> UploadedDocument:
    path = await save_upload_file(file)
    file_type = detect_file_type(path)
    text = extract_text(path)
    return _persist_document(
        db=db,
        path=path,
        title=title or Path(file.filename or path.name).stem,
        description=description,
        visibility=visibility,
        file_type=file_type,
        original_filename=file.filename,
        text=text,
    )


def ingest_text_content(
    db: Session,
    *,
    title: str,
    content: str,
    description: str | None = None,
    visibility: str = "public",
    suffix: str = ".md",
) -> UploadedDocument:
    path = save_text_upload(content, suffix=suffix)
    file_type = suffix.removeprefix(".") or "md"
    return _persist_document(
        db=db,
        path=path,
        title=title,
        description=description,
        visibility=visibility,
        file_type=file_type,
        original_filename=f"{title}{suffix}",
        text=content,
    )

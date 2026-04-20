from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.document import UploadedDocument
from app.schemas.upload import UploadedDocumentRead
from app.services.content.upload_service import ingest_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadedDocumentRead)
async def upload_document(
    db: DbSession,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    visibility: str = Form(default="public"),
) -> UploadedDocumentRead:
    document = await ingest_upload(
        db=db,
        file=file,
        title=title,
        description=description,
        visibility=visibility,
    )
    return UploadedDocumentRead.model_validate(document)


@router.get("", response_model=list[UploadedDocumentRead])
def list_uploads(db: DbSession) -> list[UploadedDocumentRead]:
    documents = db.scalars(
        select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    ).all()
    return [UploadedDocumentRead.model_validate(document) for document in documents]

from uuid import UUID

from pydantic import BaseModel


class UploadedDocumentRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    file_path: str
    file_type: str
    visibility: str

    model_config = {"from_attributes": True}

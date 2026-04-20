from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.schemas.agent import AgentChatRequest
from app.services.agent.chat_service import stream_agent_chat
from app.services.content.upload_service import ingest_upload

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentChatRequest, db: DbSession) -> StreamingResponse:
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        stream_agent_chat(db, request),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/chat/stream-with-files")
async def agent_chat_stream_with_files(
    db: DbSession,
    payload: str = Form(...),
    files: list[UploadFile] = File(default_factory=list),
) -> StreamingResponse:
    request = AgentChatRequest.model_validate_json(payload)
    uploaded_documents: list[dict] = []
    for file in files:
        document = await ingest_upload(
            db=db,
            file=file,
            title=file.filename,
            description="agent chat attachment",
            visibility="public",
        )
        uploaded_documents.append(
            {
                "id": str(document.id),
                "title": document.title,
                "description": document.description,
                "file_path": document.file_path,
                "file_type": document.file_type,
                "visibility": document.visibility,
            }
        )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        stream_agent_chat(db, request, uploaded_documents=uploaded_documents),
        media_type="text/event-stream",
        headers=headers,
    )

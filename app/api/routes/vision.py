from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.integrations.sam3.service import SamIntegrationError, segment_image_with_sam
from app.schemas.vision import SamSegmentResponse
from app.services.content.file_extraction_service import IMAGE_EXTENSIONS
from app.services.content.upload_service import save_upload_file

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/sam-segment", response_model=SamSegmentResponse)
async def sam_segment(
    instruction: str = Form(...),
    image_path: str | None = Form(default=None),
    output_name: str | None = Form(default=None),
    confidence_threshold: float | None = Form(default=None),
    top_k: int | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> SamSegmentResponse:
    if not instruction.strip():
        raise HTTPException(status_code=400, detail="instruction 不能为空")
    if not image_path and file is None:
        raise HTTPException(status_code=400, detail="必须提供 image_path 或上传 file")
    if image_path and file is not None:
        raise HTTPException(status_code=400, detail="image_path 和 file 只能二选一")

    resolved_image_path: str
    if file is not None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"仅支持图片上传: {', '.join(sorted(IMAGE_EXTENSIONS))}",
            )
        saved_path = await save_upload_file(file)
        resolved_image_path = str(saved_path.resolve())
    else:
        resolved_image_path = str(Path(image_path or "").expanduser().resolve())

    try:
        payload = segment_image_with_sam(
            image_path=resolved_image_path,
            instruction=instruction,
            output_name=output_name,
            confidence_threshold=confidence_threshold,
            top_k=top_k,
        )
    except SamIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SamSegmentResponse.model_validate(payload)

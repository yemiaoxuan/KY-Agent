from __future__ import annotations

from pydantic import BaseModel, Field


class SamDetection(BaseModel):
    index: int
    score: float
    box: list[float] = Field(default_factory=list)
    area_pixels: int


class SamSegmentResponse(BaseModel):
    ok: bool = True
    message: str = "ok"
    prompt: str
    image_path: str
    mask_path: str | None = None
    overlay_path: str | None = None
    output_dir: str
    device: str
    confidence_threshold: float
    top_k: int
    detection_count: int
    detections: list[SamDetection] = Field(default_factory=list)

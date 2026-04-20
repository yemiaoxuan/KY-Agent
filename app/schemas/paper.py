from datetime import datetime

from pydantic import BaseModel, Field


class PaperCandidate(BaseModel):
    source: str = "arxiv"
    source_id: str
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    url: str
    pdf_url: str | None = None
    relevance_score: float | None = None
    summary_zh: str | None = None
    relevance_reason: str | None = None


class PaperSummary(BaseModel):
    source_id: str
    title: str
    one_sentence_summary: str
    contributions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    why_it_matters: str = ""
    relevance_reason: str = ""

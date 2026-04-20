from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    metadata: dict


class ChatRequest(BaseModel):
    question: str
    limit: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    sources: list[SearchResult]

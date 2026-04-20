from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.search import ChatRequest, ChatResponse, SearchRequest, SearchResult
from app.services.rag.retrieval_service import search_public_chunks
from app.services.rag.search_service import answer_with_rag

router = APIRouter(tags=["search"])


@router.post("/search", response_model=list[SearchResult])
def search(request: SearchRequest, db: DbSession) -> list[SearchResult]:
    return search_public_chunks(db, request.query, request.limit)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: DbSession) -> ChatResponse:
    return answer_with_rag(db, request.question, request.limit)

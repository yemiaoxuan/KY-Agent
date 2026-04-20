import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.search import ChatResponse
from app.services.ai.llm_service import get_llm
from app.services.rag.retrieval_service import (
    document_to_search_result,
    documents_to_context,
    search_public_documents,
)

logger = logging.getLogger(__name__)


def build_rag_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是科研进展检索助手。只能基于提供的上下文回答；如果上下文不足，请明确说明。",
            ),
            ("human", "问题：{question}\n\n上下文：\n{context}\n\n请用中文回答，并引用来源编号。"),
        ]
    )
    # documents 先转换成上下文，再进入 prompt / llm / parser，形成清晰的 Runnable 数据流。
    return (
        RunnablePassthrough.assign(
            context=lambda payload: documents_to_context(payload["documents"])
        )
        | prompt
        | get_llm()
        | StrOutputParser()
    )


def answer_with_rag(db: Session, question: str, limit: int = 5) -> ChatResponse:
    documents = search_public_documents(db, question, limit)
    sources = [document_to_search_result(document) for document in documents]

    settings = get_settings()
    if settings.llm_api_key == "replace-me":
        return ChatResponse(
            answer=(
                "LLM_API_KEY 尚未配置。以下是最相关的检索片段，"
                "请配置镜像站模型后启用 RAG 回答。"
            ),
            sources=sources,
        )

    chain = build_rag_chain()
    answer = chain.invoke({"question": question, "documents": documents})
    return ChatResponse(answer=answer, sources=sources)

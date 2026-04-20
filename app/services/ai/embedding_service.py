import logging

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.core.config import get_settings
from app.services.runtime.runtime_config_service import load_runtime_config

logger = logging.getLogger(__name__)


def get_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    runtime_config = load_runtime_config()
    return OpenAIEmbeddings(
        model=runtime_config.selected_embedding_model or settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimensions=settings.embedding_dimensions,
        timeout=60,
        max_retries=2,
    )


class ConfiguredEmbeddings(Embeddings):
    """LangChain Embeddings adapter that preserves the project's local fallback."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed_query(text)


def get_configured_embeddings() -> Embeddings:
    # 上层只依赖 LangChain Embeddings 抽象，不直接依赖具体供应商 SDK。
    return ConfiguredEmbeddings()


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.embedding_api_key == "replace-me":
        logger.warning(
            "Embedding API key is not configured; returning zero vectors for local scaffolding."
        )
        return [[0.0] * settings.embedding_dimensions for _ in texts]
    return get_embeddings().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    settings = get_settings()
    if settings.embedding_api_key == "replace-me":
        logger.warning("Embedding API key is not configured; returning zero query vector.")
        return [0.0] * settings.embedding_dimensions
    return get_embeddings().embed_query(text)

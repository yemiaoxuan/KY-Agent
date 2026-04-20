import json
import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.topic import Topic
from app.schemas.paper import PaperCandidate, PaperSummary
from app.services.runtime.runtime_config_service import load_runtime_config

logger = logging.getLogger(__name__)


def _build_chat_llm(model_name: str) -> ChatOpenAI:
    settings = get_settings()
    # 统一走 OpenAI-compatible 接口，便于切换镜像站或模型供应商。
    return ChatOpenAI(
        model=model_name,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        timeout=60,
        max_retries=2,
    )


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    runtime_config = load_runtime_config()
    return _build_chat_llm(runtime_config.selected_chat_model or settings.llm_model)


def get_rewriter_llm() -> ChatOpenAI:
    settings = get_settings()
    runtime_config = load_runtime_config()
    return _build_chat_llm(runtime_config.selected_rewrite_model or settings.llm_model)


def keyword_relevance_score(paper: PaperCandidate, topic: Topic) -> float:
    text = f"{paper.title}\n{paper.abstract}".lower()
    include_hits = sum(1 for keyword in topic.include_keywords if keyword.lower() in text)
    exclude_hits = sum(1 for keyword in topic.exclude_keywords if keyword.lower() in text)
    category_hits = sum(1 for category in topic.arxiv_categories if category in paper.categories)
    return max(0.0, include_hits * 1.0 + category_hits * 0.3 - exclude_hits * 1.5)


def fallback_summary(paper: PaperCandidate, topic: Topic) -> PaperSummary:
    del topic
    abstract = paper.abstract.strip()
    one_sentence = abstract[:240] + ("..." if len(abstract) > 240 else "")
    return PaperSummary(
        source_id=paper.source_id,
        title=paper.title,
        one_sentence_summary=one_sentence,
        contributions=["LLM 摘要不可用，暂以 arXiv 摘要为准。"],
        limitations=["未调用模型生成局限分析。"],
        why_it_matters="该论文与当前配置的关键词或 arXiv 分类相关。",
        relevance_reason=paper.relevance_reason or "关键词或分类匹配。",
    )


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def summarize_paper_with_llm(
    paper: PaperCandidate,
    topic: Topic,
    prompt_suffix: str | None = None,
) -> PaperSummary:
    suffix_block = f"\n额外日报偏好：{prompt_suffix}\n" if prompt_suffix else ""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是严谨的科研助理。请只根据用户提供的 arXiv 标题和摘要总结，不要编造信息。"
                f"{suffix_block}",
            ),
            (
                "human",
                """研究主题：{topic}

论文标题：{title}
作者：{authors}
arXiv 分类：{categories}
摘要：{abstract}

请输出 JSON，字段包括：
- one_sentence_summary: 中文一句话总结
- contributions: 2 到 4 条中文核心贡献
- limitations: 1 到 3 条可能局限，如果摘要未提及请明确说明“摘要未充分说明”
- why_it_matters: 为什么值得关注
- relevance_reason: 与研究主题相关的原因
""",
            ),
        ]
    )
    # prompt | llm | parser 是最直接的 LangChain runnable 组合方式。
    chain = prompt | get_llm() | StrOutputParser()
    raw = chain.invoke(
        {
            "topic": topic.display_name,
            "title": paper.title,
            "authors": ", ".join(paper.authors[:8]),
            "categories": ", ".join(paper.categories),
            "abstract": paper.abstract,
        }
    )
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        payload = json.loads(cleaned)
        return PaperSummary(
            source_id=paper.source_id,
            title=paper.title,
            one_sentence_summary=payload.get("one_sentence_summary", ""),
            contributions=payload.get("contributions", []),
            limitations=payload.get("limitations", []),
            why_it_matters=payload.get("why_it_matters", ""),
            relevance_reason=payload.get("relevance_reason", ""),
        )
    except Exception:
        logger.exception("Failed to parse LLM summary; using fallback. raw=%s", raw[:500])
        return fallback_summary(paper, topic)


def summarize_paper(
    paper: PaperCandidate,
    topic: Topic,
    prompt_suffix: str | None = None,
) -> PaperSummary:
    settings = get_settings()
    # 开发环境允许在未配置 LLM 时退化运行，先打通整个日报工作流。
    if settings.llm_api_key == "replace-me":
        return fallback_summary(paper, topic)
    try:
        return summarize_paper_with_llm(paper, topic, prompt_suffix=prompt_suffix)
    except Exception:
        logger.exception("LLM summary failed; using fallback for paper=%s", paper.source_id)
        return fallback_summary(paper, topic)

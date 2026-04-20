from __future__ import annotations

import json

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.agent import AgentChatMessage
from app.services.ai.llm_service import get_rewriter_llm
from app.services.runtime.runtime_config_service import load_runtime_config


def rewrite_agent_request(
    messages: list[AgentChatMessage],
    selected_topics: list[str] | None = None,
) -> dict[str, object]:
    runtime_config = load_runtime_config()
    if not runtime_config.enable_query_rewrite or not messages:
        latest = messages[-1].content if messages else ""
        return {
            "enabled": runtime_config.enable_query_rewrite,
            "rewritten_query": latest,
            "reasoning_focus": [],
        }

    latest_message = messages[-1].content
    topic_text = "、".join(selected_topics or []) or "未指定"
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是科研对话预处理器。你的任务是在主 Agent 执行前，"
                "把用户最后一轮问题重写成更适合科研检索、工具调用和日报生成的清晰任务。"
                "不要改变用户真实意图。输出 JSON。",
            ),
            (
                "human",
                """当前会话关注主题：{topics}

用户最后一轮输入：
{message}

请输出 JSON，字段包括：
- rewritten_query: 更清晰、更适合科研助手执行的中文任务描述
- reasoning_focus: 1 到 4 条重点关注项
""",
            ),
        ]
    )
    chain = prompt | get_rewriter_llm() | StrOutputParser()
    raw = chain.invoke({"topics": topic_text, "message": latest_message})
    cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
        return {
            "enabled": True,
            "rewritten_query": payload.get("rewritten_query", latest_message),
            "reasoning_focus": payload.get("reasoning_focus", []),
        }
    except Exception:
        return {
            "enabled": True,
            "rewritten_query": latest_message,
            "reasoning_focus": [],
            "raw": raw,
        }

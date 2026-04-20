from __future__ import annotations

from dataclasses import dataclass

from app.agents.chat.tool_routes import (
    ANSWER_TOOL_NAMES,
    DAILY_TOOL_NAMES,
    EMAIL_TOOL_NAMES,
    REPORT_TOOL_NAMES,
    SEARCH_TOOL_NAMES,
)


@dataclass(frozen=True)
class AgentToolProfile:
    name: str
    display_name: str
    tool_names: frozenset[str]
    responsibilities: str
    delegation_description: str


ALL_SPECIALIST_TOOL_NAMES = (
    SEARCH_TOOL_NAMES
    | ANSWER_TOOL_NAMES
    | REPORT_TOOL_NAMES
    | EMAIL_TOOL_NAMES
    | DAILY_TOOL_NAMES
    | {
        "list_topics",
        "upload_research_note",
        "list_uploads",
        "mcp_get_current_time",
        "mcp_summarize_text_stats",
        "mcp_extract_keywords_local",
        "mcp_read_local_markdown_excerpt",
        "segment_image_with_sam",
    }
)

AGENT_TOOL_PROFILES: tuple[AgentToolProfile, ...] = (
    AgentToolProfile(
        name="research",
        display_name="科研检索与问答",
        tool_names=frozenset(
            {
                "list_topics",
                "semantic_search_public_progress",
                "rag_answer_public_progress",
                "upload_research_note",
                "list_uploads",
                "mcp_summarize_text_stats",
                "mcp_extract_keywords_local",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 列出研究主题、检索公共研究进展、基于 RAG 回答科研问题。\n"
            "- 上传/登记文本研究笔记，读取上传文档或本地 markdown 摘要。\n"
            "- 对文本做本地统计或关键词提取。"
        ),
        delegation_description=(
            "Delegate research search, RAG Q&A, topic listing, upload listing, "
            "research-note ingestion, local markdown reading, and text analysis tasks."
        ),
    ),
    AgentToolProfile(
        name="reporting",
        display_name="日报与报告",
        tool_names=frozenset(
            {
                "list_topics",
                "run_daily_report",
                "list_reports",
                "get_report_content",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 生成每日 arXiv 研究报告。\n"
            "- 列出、读取和总结已生成的日报内容。\n"
            "- 必要时读取报告 markdown 摘要。"
        ),
        delegation_description=(
            "Delegate daily arXiv report generation, report listing, report reading, "
            "and report summarization tasks."
        ),
    ),
    AgentToolProfile(
        name="communication",
        display_name="邮件通知",
        tool_names=frozenset(
            {
                "send_markdown_email",
                "send_report_email",
                "send_plain_email",
                "list_reports",
                "get_report_content",
            }
        ),
        responsibilities=(
            "- 发送 markdown、纯文本邮件或已有日报邮件。\n"
            "- 需要发送报告前可查询报告列表和报告内容。"
        ),
        delegation_description=(
            "Delegate email sending and report-email delivery tasks, including "
            "looking up report metadata/content when needed."
        ),
    ),
    AgentToolProfile(
        name="vision",
        display_name="图像分割",
        tool_names=frozenset({"segment_image_with_sam"}),
        responsibilities=(
            "- 对本地图片执行 SAM 目标分割、抠图、mask、框选、主体或区域提取。\n"
            "- 输入必须包含可用的本地图片路径和自然语言分割指令。"
        ),
        delegation_description=(
            "Delegate image segmentation, mask extraction, cutout, object/region "
            "selection, and bounding-box style vision tasks."
        ),
    ),
    AgentToolProfile(
        name="utility",
        display_name="通用本地工具",
        tool_names=frozenset(
            {
                "mcp_get_current_time",
                "mcp_summarize_text_stats",
                "mcp_extract_keywords_local",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 获取当前时间。\n"
            "- 做轻量文本统计、关键词提取或读取本地 markdown 摘要。"
        ),
        delegation_description=(
            "Delegate lightweight local utility tasks such as current time, text "
            "statistics, keyword extraction, and markdown excerpt reading."
        ),
    ),
)

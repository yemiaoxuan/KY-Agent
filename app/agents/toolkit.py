from __future__ import annotations

import inspect
from collections.abc import Sequence
from functools import wraps
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy.orm import Session

from app.agents.daily_research_graph import run_daily_research
from app.integrations.mcp.client import call_local_mcp_tool_sync
from app.integrations.sam3.service import SamIntegrationError, segment_image_with_sam
from app.models.document import UploadedDocument
from app.models.report import DailyReport
from app.models.topic import Topic
from app.services.content.upload_service import ingest_text_content
from app.services.notification.email_service import send_email_sync, send_markdown_email_sync
from app.services.observability.tool_logging_service import write_tool_call_log
from app.services.rag.retrieval_service import search_public_chunks
from app.services.rag.search_service import answer_with_rag
from app.services.reporting.report_query_service import (
    get_report_content_payload,
    list_reports_payload,
)
from app.services.research.topic_service import list_enabled_topics


def _jsonable_report(report: DailyReport) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "title": report.title,
        "report_date": report.report_date.isoformat(),
        "markdown_path": report.markdown_path,
        "email_status": report.email_status,
    }


def _jsonable_topic(topic: Topic) -> dict[str, Any]:
    return {
        "id": str(topic.id),
        "name": topic.name,
        "display_name": topic.display_name,
        "query": topic.query,
        "include_keywords": topic.include_keywords,
        "exclude_keywords": topic.exclude_keywords,
        "arxiv_categories": topic.arxiv_categories,
        "enabled": topic.enabled,
    }


def _jsonable_document(document: UploadedDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "title": document.title,
        "description": document.description,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "visibility": document.visibility,
    }


def _model_dump_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _with_tool_logging(
    tool_name: str,
    func,
):
    signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            write_tool_call_log(
                tool_name=tool_name,
                args=kwargs,
                result=result,
            )
            return result
        except Exception as exc:
            write_tool_call_log(
                tool_name=tool_name,
                args=kwargs,
                error=repr(exc),
            )
            raise

    wrapper.__signature__ = signature
    return wrapper


def _build_tool(func, *, name: str, description: str) -> StructuredTool:
    return StructuredTool.from_function(
        _with_tool_logging(name, func),
        name=name,
        description=description,
    )


def build_internal_tools(db: Session) -> list[BaseTool]:
    def list_topics_tool() -> list[dict[str, Any]]:
        return [_jsonable_topic(topic) for topic in list_enabled_topics(db)]

    def semantic_search_tool(query: str, limit: int = 5) -> list[dict[str, Any]]:
        results = search_public_chunks(db, query, limit)
        return [result.model_dump() for result in results]

    def rag_answer_tool(question: str, limit: int = 5) -> dict[str, Any]:
        result = answer_with_rag(db, question, limit)
        return _model_dump_jsonable(result)

    def run_daily_report_tool(
        topic_name: str | None = None,
        topic_names: list[str] | None = None,
        prompt_suffix: str | None = None,
        recipients: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        results = run_daily_research(
            db,
            topic_name=topic_name,
            topic_names=topic_names,
            send_email=bool(recipients),
            email_recipients=recipients,
            prompt_suffix=prompt_suffix,
        )
        return [_model_dump_jsonable(result) for result in results]

    def list_reports_tool(limit: int = 10) -> list[dict[str, Any]]:
        return list_reports_payload(db, limit=limit)

    def get_report_content_tool(report_id: str) -> dict[str, Any]:
        return get_report_content_payload(db, report_id)

    def upload_research_note_tool(
        title: str,
        content: str,
        description: str | None = None,
        visibility: str = "public",
    ) -> dict[str, Any]:
        document = ingest_text_content(
            db,
            title=title,
            content=content,
            description=description,
            visibility=visibility,
        )
        return _jsonable_document(document)

    def list_uploads_tool(limit: int = 10) -> list[dict[str, Any]]:
        documents = (
            db.query(UploadedDocument).order_by(UploadedDocument.created_at.desc()).limit(limit).all()
        )
        return [_jsonable_document(document) for document in documents]

    def send_markdown_email_tool(
        subject: str,
        markdown_text: str,
        recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        result = send_markdown_email_sync(
            subject=subject,
            markdown_text=markdown_text,
            recipients=recipients,
        )
        return _model_dump_jsonable(result)

    def send_report_email_tool(
        report_id: str,
        subject: str | None = None,
        recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        report = db.get(DailyReport, report_id)
        if report is None:
            return {"ok": False, "message": "report not found", "report_id": report_id}
        markdown = Path(report.markdown_path).read_text(encoding="utf-8")
        result = send_markdown_email_sync(
            subject=subject or report.title,
            markdown_text=markdown,
            recipients=recipients,
            attachment_path=Path(report.markdown_path),
        )
        payload = _model_dump_jsonable(result)
        payload["report_id"] = report_id
        return payload

    def send_plain_email_tool(
        subject: str,
        plain_text: str,
        recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        result = send_email_sync(
            subject=subject,
            plain_text=plain_text,
            recipients=recipients,
        )
        return _model_dump_jsonable(result)

    def mcp_get_current_time_tool() -> dict[str, Any]:
        return call_local_mcp_tool_sync("get_current_time", {})

    def mcp_summarize_text_stats_tool(text: str) -> dict[str, Any]:
        return call_local_mcp_tool_sync("summarize_text_stats", {"text": text})

    def mcp_extract_keywords_tool(text: str, top_k: int = 8) -> dict[str, Any]:
        return call_local_mcp_tool_sync("extract_keywords_local", {"text": text, "top_k": top_k})

    def mcp_read_markdown_excerpt_tool(path: str, max_lines: int = 80) -> dict[str, Any]:
        return call_local_mcp_tool_sync(
            "read_local_markdown_excerpt",
            {"path": path, "max_lines": max_lines},
        )

    def segment_image_with_sam_tool(
        image_path: str,
        instruction: str,
        output_name: str | None = None,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        try:
            return segment_image_with_sam(
                image_path=image_path,
                instruction=instruction,
                output_name=output_name,
                confidence_threshold=confidence_threshold,
                top_k=top_k,
            )
        except SamIntegrationError as exc:
            return {"ok": False, "message": str(exc), "image_path": image_path}

    return [
        _build_tool(
            name="list_topics",
            func=list_topics_tool,
            description="List current enabled research topics configured in the system.",
        ),
        _build_tool(
            name="semantic_search_public_progress",
            func=semantic_search_tool,
            description="Semantic search over public uploaded research progress documents.",
        ),
        _build_tool(
            name="rag_answer_public_progress",
            func=rag_answer_tool,
            description=(
                "Answer a research question from the public progress database "
                "with cited sources."
            ),
        ),
        _build_tool(
            name="run_daily_report",
            func=run_daily_report_tool,
            description="Generate the daily arXiv report for a specific topic or all topics.",
        ),
        _build_tool(
            name="list_reports",
            func=list_reports_tool,
            description="List recent generated daily report metadata.",
        ),
        _build_tool(
            name="get_report_content",
            func=get_report_content_tool,
            description="Read full markdown content of a generated report by report id.",
        ),
        _build_tool(
            name="upload_research_note",
            func=upload_research_note_tool,
            description=(
                "Save a text research note into the shared vector database "
                "as a public document."
            ),
        ),
        _build_tool(
            name="list_uploads",
            func=list_uploads_tool,
            description="List recent uploaded research documents.",
        ),
        _build_tool(
            name="send_markdown_email",
            func=send_markdown_email_tool,
            description="Send a markdown email to the default recipient or provided recipients.",
        ),
        _build_tool(
            name="send_report_email",
            func=send_report_email_tool,
            description="Send an existing daily report by report id as markdown email.",
        ),
        _build_tool(
            name="send_plain_email",
            func=send_plain_email_tool,
            description="Send a plain text email for notifications or follow-up messages.",
        ),
        _build_tool(
            name="mcp_get_current_time",
            func=mcp_get_current_time_tool,
            description="Call the local MCP service to get current Beijing time.",
        ),
        _build_tool(
            name="mcp_summarize_text_stats",
            func=mcp_summarize_text_stats_tool,
            description="Call the local MCP service to summarize text statistics.",
        ),
        _build_tool(
            name="mcp_extract_keywords_local",
            func=mcp_extract_keywords_tool,
            description="Call the local MCP service to extract simple local keywords from text.",
        ),
        _build_tool(
            name="mcp_read_local_markdown_excerpt",
            func=mcp_read_markdown_excerpt_tool,
            description="Call the local MCP service to read an excerpt from a local markdown file.",
        ),
        _build_tool(
            name="segment_image_with_sam",
            func=segment_image_with_sam_tool,
            description=(
                "Segment objects or regions in a local image with SAM. "
                "Input an absolute image_path and a natural-language instruction."
            ),
        ),
    ]


def build_agent_tools(
    db: Session,
    extra_tools: Sequence[BaseTool] | None = None,
) -> list[BaseTool]:
    tools = build_internal_tools(db)
    if extra_tools:
        tools.extend(extra_tools)
    return tools

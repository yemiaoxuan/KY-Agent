import logging
from datetime import date, datetime
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.paper import ExternalPaper
from app.models.report import DailyReport
from app.models.topic import Topic
from app.schemas.paper import PaperCandidate, PaperSummary
from app.schemas.report import DailyReportResult
from app.services.ai.llm_service import keyword_relevance_score, summarize_paper
from app.services.notification.email_service import send_markdown_email_sync
from app.services.reporting.report_ingestion_service import enqueue_report_document_upsert
from app.services.reporting.report_service import render_daily_report, save_report_markdown
from app.services.research.arxiv_service import search_arxiv
from app.services.research.topic_service import get_topic_by_name, list_enabled_topics
from app.services.runtime.runtime_config_service import load_runtime_config

logger = logging.getLogger(__name__)


class DailyResearchState(TypedDict, total=False):
    db: Session
    topic_name: str | None
    topic_names: list[str] | None
    send_email: bool
    email_recipients: list[str] | None
    prompt_suffix: str | None
    topics: list[Topic]
    topic: Topic
    candidates: list[PaperCandidate]
    selected: list[PaperCandidate]
    summaries: list[PaperSummary]
    markdown_text: str
    report_result: DailyReportResult
    agent_run_id: str
    error: str


def _start_run(state: DailyResearchState) -> DailyResearchState:
    db = state["db"]
    run = AgentRun(
        agent_name="daily_research",
        status="running",
        input={"topic_name": state.get("topic_name"), "send_email": state.get("send_email", True)},
        output={},
        started_at=datetime.now().astimezone(),
    )
    db.add(run)
    db.commit()
    return {"agent_run_id": str(run.id)}


def _load_topics(state: DailyResearchState) -> DailyResearchState:
    db = state["db"]
    topic_name = state.get("topic_name")
    topic_names = state.get("topic_names") or []
    if topic_names:
        topics: list[Topic] = []
        for item in topic_names:
            topic = get_topic_by_name(db, item)
            if topic is None:
                raise ValueError(f"Topic not found: {item}")
            topics.append(topic)
    elif topic_name:
        topic = get_topic_by_name(db, topic_name)
        if topic is None:
            raise ValueError(f"Topic not found: {topic_name}")
        topics = [topic]
    else:
        topics = list_enabled_topics(db)
    return {"topics": topics}


def _search_and_select(state: DailyResearchState) -> DailyResearchState:
    topic = state["topic"]
    candidates = search_arxiv(topic)
    seen: set[str] = set()
    scored: list[PaperCandidate] = []
    for paper in candidates:
        if paper.source_id in seen:
            continue
        seen.add(paper.source_id)
        score = keyword_relevance_score(paper, topic)
        paper.relevance_score = score
        paper.relevance_reason = "关键词或分类匹配" if score > 0 else "按 arXiv 最新排序保留"
        if score > 0:
            scored.append(paper)

    if not scored:
        scored = candidates[: topic.report_top_k]
    else:
        scored = sorted(scored, key=lambda item: item.relevance_score or 0, reverse=True)[
            : topic.report_top_k
        ]
    return {"candidates": candidates, "selected": scored}


def _summarize(state: DailyResearchState) -> DailyResearchState:
    topic = state["topic"]
    runtime_config = load_runtime_config()
    extra_prompt_parts = [
        item
        for item in [topic.report_prompt_hint, state.get("prompt_suffix")]
        if item
    ]
    merged_prompt_suffix = "\n".join(extra_prompt_parts) if extra_prompt_parts else None
    llm_prompt_parts = [
        item
        for item in [
            runtime_config.daily_report_system_prompt_suffix,
            *extra_prompt_parts,
        ]
        if item
    ]
    llm_prompt_suffix = "\n".join(llm_prompt_parts) if llm_prompt_parts else None
    summaries = [
        summarize_paper(paper, topic, prompt_suffix=llm_prompt_suffix)
        for paper in state.get("selected", [])
    ]
    return {"summaries": summaries, "prompt_suffix": merged_prompt_suffix}


def _persist_papers(
    db: Session,
    topic: Topic,
    selected: list[PaperCandidate],
    summaries: list[PaperSummary],
) -> None:
    summary_by_id = {summary.source_id: summary for summary in summaries}
    for paper in selected:
        summary = summary_by_id.get(paper.source_id)
        stmt = insert(ExternalPaper).values(
            source=paper.source,
            source_id=paper.source_id,
            title=paper.title,
            abstract=paper.abstract,
            authors=paper.authors,
            categories=paper.categories,
            published_at=paper.published_at,
            source_updated_at=paper.source_updated_at,
            url=paper.url,
            pdf_url=paper.pdf_url,
            relevance_score=paper.relevance_score,
            summary_zh=summary.one_sentence_summary if summary else paper.summary_zh,
            topic_id=topic.id,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_external_papers_source_id",
            set_={
                "title": stmt.excluded.title,
                "abstract": stmt.excluded.abstract,
                "source_updated_at": stmt.excluded.source_updated_at,
                "relevance_score": stmt.excluded.relevance_score,
                "summary_zh": stmt.excluded.summary_zh,
                "topic_id": stmt.excluded.topic_id,
            },
        )
        db.execute(stmt)
    db.commit()


def _generate_and_save_report(state: DailyResearchState) -> DailyResearchState:
    db = state["db"]
    topic = state["topic"]
    report_date = date.today()
    candidates = state.get("candidates", [])
    selected = state.get("selected", [])
    summaries = state.get("summaries", [])
    _persist_papers(db, topic, selected, summaries)

    markdown_text = render_daily_report(
        topic,
        report_date,
        candidates,
        selected,
        summaries,
        prompt_suffix=state.get("prompt_suffix"),
    )
    markdown_path = save_report_markdown(topic, report_date, markdown_text)

    title = f"每日科研进展简报：{topic.display_name} - {report_date.isoformat()}"
    report = (
        db.query(DailyReport)
        .filter(DailyReport.topic_id == topic.id, DailyReport.report_date == report_date)
        .one_or_none()
    )
    if report is None:
        report = DailyReport(
            topic_id=topic.id,
            title=title,
            report_date=report_date,
            markdown_path=str(markdown_path),
            email_status="pending",
        )
        db.add(report)
    else:
        report.title = title
        report.markdown_path = str(markdown_path)
        report.email_status = "pending"
    db.commit()

    enqueue_report_document_upsert(
        title=title,
        description=f"{topic.display_name} 的每日报告，自动写入公共向量库。",
        markdown_path=markdown_path,
        topic_name=topic.name,
        report_date=report_date.isoformat(),
        visibility="public",
    )

    return {
        "markdown_text": markdown_text,
        "report_result": DailyReportResult(
            topic_name=topic.name,
            report_date=report_date,
            title=title,
            markdown_path=markdown_path,
            selected_count=len(selected),
            email_status="pending",
        ),
    }


def _send_email(state: DailyResearchState) -> DailyResearchState:
    if not state.get("send_email", True):
        result = state["report_result"].model_copy(update={"email_status": "skipped"})
        return {"report_result": result}

    result = state["report_result"]
    try:
        email_result = send_markdown_email_sync(
            result.title,
            state["markdown_text"],
            recipients=state.get("email_recipients"),
            attachment_path=result.markdown_path,
        )
        status = "sent" if email_result.ok else "skipped"
    except Exception:
        logger.exception("Failed to send report email")
        status = "failed"

    db = state["db"]
    report = (
        db.query(DailyReport)
        .filter(
            DailyReport.topic.has(name=result.topic_name),
            DailyReport.report_date == result.report_date,
        )
        .one_or_none()
    )
    if report is not None:
        report.email_status = status
        db.commit()
    return {"report_result": result.model_copy(update={"email_status": status})}


def _finish_run(state: DailyResearchState) -> DailyResearchState:
    db = state["db"]
    run_id = state.get("agent_run_id")
    if run_id:
        run = db.get(AgentRun, run_id)
        if run is not None:
            result = state.get("report_result")
            run.status = "success"
            run.output = result.model_dump(mode="json") if result else {}
            run.finished_at = datetime.now().astimezone()
            db.commit()
    return state


def _mark_failed(state: DailyResearchState, error: Exception) -> None:
    db = state["db"]
    run_id = state.get("agent_run_id")
    if run_id:
        run = db.get(AgentRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = repr(error)
            run.finished_at = datetime.now().astimezone()
            db.commit()


def build_single_topic_graph():
    graph = StateGraph(DailyResearchState)
    graph.add_node("search_and_select", _search_and_select)
    graph.add_node("summarize", _summarize)
    graph.add_node("generate_and_save_report", _generate_and_save_report)
    graph.add_node("deliver_email", _send_email)
    graph.set_entry_point("search_and_select")
    graph.add_edge("search_and_select", "summarize")
    graph.add_edge("summarize", "generate_and_save_report")
    graph.add_edge("generate_and_save_report", "deliver_email")
    graph.add_edge("deliver_email", END)
    return graph.compile()


def run_daily_research(
    db: Session,
    topic_name: str | None = None,
    topic_names: list[str] | None = None,
    send_email: bool = True,
    email_recipients: list[str] | None = None,
    prompt_suffix: str | None = None,
) -> list[DailyReportResult]:
    base_state: DailyResearchState = {
        "db": db,
        "topic_name": topic_name,
        "topic_names": topic_names,
        "send_email": send_email,
        "email_recipients": email_recipients,
        "prompt_suffix": prompt_suffix,
    }
    base_state.update(_start_run(base_state))
    try:
        base_state.update(_load_topics(base_state))
        compiled = build_single_topic_graph()
        results: list[DailyReportResult] = []
        for topic in base_state["topics"]:
            state: DailyResearchState = {**base_state, "topic": topic}
            output: dict[str, Any] = compiled.invoke(state)
            results.append(output["report_result"])
        base_state["report_result"] = results[-1] if results else None
        _finish_run(base_state)
        return results
    except Exception as exc:
        _mark_failed(base_state, exc)
        raise

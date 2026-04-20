from fastapi import APIRouter

from app.agents.graphs.daily_research_graph import run_daily_research
from app.api.deps import DbSession
from app.schemas.report import RunDailyReportRequest
from app.services.reporting.report_query_service import (
    get_report_content_payload,
    jsonable_report,
    list_reports_payload,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/run-daily")
def run_daily_report(request: RunDailyReportRequest, db: DbSession) -> list[dict]:
    results = run_daily_research(
        db,
        topic_name=request.topic_name,
        topic_names=request.topic_names,
        send_email=request.send_email,
        email_recipients=request.recipients,
        prompt_suffix=request.prompt_suffix,
    )
    return [result.model_dump(mode="json") for result in results]


@router.get("")
def list_reports(db: DbSession) -> list[dict]:
    return list_reports_payload(db)


@router.get("/{report_id}")
def get_report(report_id: str, db: DbSession) -> dict:
    from app.models.report import DailyReport

    report = db.get(DailyReport, report_id)
    if report is None:
        return {"error": "report not found"}
    return jsonable_report(report)


@router.get("/{report_id}/content")
def get_report_content(report_id: str, db: DbSession) -> dict:
    return get_report_content_payload(db, report_id)

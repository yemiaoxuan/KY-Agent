from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import DailyReport


def jsonable_report(report: DailyReport) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "title": report.title,
        "report_date": report.report_date.isoformat(),
        "markdown_path": report.markdown_path,
        "email_status": report.email_status,
    }


def get_report_content_payload(db: Session, report_id: str) -> dict[str, Any]:
    report = db.get(DailyReport, report_id)
    if report is None:
        return {"error": "report not found"}
    markdown = Path(report.markdown_path).read_text(encoding="utf-8")
    return {**jsonable_report(report), "markdown": markdown}


def list_reports_payload(db: Session, limit: int | None = None) -> list[dict[str, Any]]:
    stmt = select(DailyReport).order_by(DailyReport.report_date.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    reports = db.scalars(stmt).all()
    return [jsonable_report(report) for report in reports]

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.report import DailyReport
from app.schemas.email import EmailConfigStatus, SendEmailRequest, SendReportEmailRequest
from app.services.notification.email_service import (
    get_email_config_status,
    send_email,
    send_markdown_email,
)

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/config-status", response_model=EmailConfigStatus)
def email_config_status() -> EmailConfigStatus:
    settings = get_settings()
    configured, message = get_email_config_status()
    return EmailConfigStatus(
        configured=configured,
        message=message,
        email_enabled=settings.email_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        email_from=settings.email_from,
        default_recipient=settings.email_to,
    )


@router.post("/send")
async def send_email_endpoint(request: SendEmailRequest) -> dict:
    result = await send_email(
        subject=request.subject,
        plain_text=request.plain_text or request.markdown_text or "",
        markdown_text=request.markdown_text,
        recipients=request.recipients,
    )
    return result.model_dump(mode="json")


@router.post("/send-report")
async def send_report_email_endpoint(request: SendReportEmailRequest, db: DbSession) -> dict:
    report = db.get(DailyReport, request.report_id)
    if report is None:
        return {"ok": False, "message": "report not found", "report_id": request.report_id}
    markdown_path = Path(report.markdown_path)
    markdown_text = markdown_path.read_text(encoding="utf-8")
    result = await send_markdown_email(
        subject=request.subject or report.title,
        markdown_text=markdown_text,
        recipients=request.recipients,
        attachment_path=markdown_path,
    )
    payload = result.model_dump(mode="json")
    payload["report_id"] = request.report_id
    return payload

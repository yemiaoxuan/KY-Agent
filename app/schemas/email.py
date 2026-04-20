from __future__ import annotations

from pydantic import BaseModel


class SendEmailRequest(BaseModel):
    subject: str
    plain_text: str = ""
    markdown_text: str | None = None
    recipients: list[str] | None = None


class SendReportEmailRequest(BaseModel):
    report_id: str
    subject: str | None = None
    recipients: list[str] | None = None


class EmailConfigStatus(BaseModel):
    configured: bool
    message: str
    email_enabled: bool
    smtp_host: str
    smtp_port: int
    email_from: str
    default_recipient: str

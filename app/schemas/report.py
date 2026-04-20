from datetime import date
from pathlib import Path

from pydantic import BaseModel


class DailyReportResult(BaseModel):
    topic_name: str
    report_date: date
    title: str
    markdown_path: Path
    selected_count: int
    email_status: str = "pending"


class RunDailyReportRequest(BaseModel):
    topic_name: str | None = None
    topic_names: list[str] | None = None
    send_email: bool = True
    recipients: list[str] | None = None
    prompt_suffix: str | None = None

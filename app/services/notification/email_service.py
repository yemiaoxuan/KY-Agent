from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from email.message import EmailMessage
from pathlib import Path
from typing import TypeVar

import aiosmtplib
import markdown as markdown_lib
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T")


class EmailSendResult(BaseModel):
    ok: bool
    message: str
    subject: str
    recipients: list[str] = Field(default_factory=list)
    attachment_paths: list[str] = Field(default_factory=list)


def _smtp_configured() -> tuple[bool, str]:
    settings = get_settings()
    missing: list[str] = []
    if not settings.email_enabled:
        missing.append("EMAIL_ENABLED")
    if settings.smtp_host == "smtp.example.com":
        missing.append("SMTP_HOST")
    if settings.smtp_user == "your-email@example.com":
        missing.append("SMTP_USER")
    if settings.smtp_password == "replace-me":
        missing.append("SMTP_PASSWORD")
    if settings.email_from == "your-email@example.com":
        missing.append("EMAIL_FROM")
    if not settings.email_to.strip():
        missing.append("EMAIL_TO")
    if missing:
        return False, f"SMTP 未完成配置，缺少或仍为默认值: {', '.join(missing)}"
    return True, "ok"


def get_email_config_status() -> tuple[bool, str]:
    return _smtp_configured()


async def send_markdown_email(
    subject: str,
    markdown_text: str,
    recipients: list[str] | None = None,
    attachment_path: Path | None = None,
) -> EmailSendResult:
    attachments = [attachment_path] if attachment_path else None
    return await send_email(
        subject=subject,
        plain_text=markdown_text,
        markdown_text=markdown_text,
        recipients=recipients,
        attachment_paths=attachments,
    )


def _run_async_from_sync(factory: Callable[[], Coroutine[object, object, T]]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    result: dict[str, T] = {}
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            result["value"] = asyncio.run(factory())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=_target, name="email-sync-bridge", daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result["value"]


def send_markdown_email_sync(
    subject: str,
    markdown_text: str,
    recipients: list[str] | None = None,
    attachment_path: Path | None = None,
) -> EmailSendResult:
    return _run_async_from_sync(
        lambda: send_markdown_email(
            subject=subject,
            markdown_text=markdown_text,
            recipients=recipients,
            attachment_path=attachment_path,
        )
    )


def send_email_sync(
    subject: str,
    plain_text: str,
    markdown_text: str | None = None,
    html_text: str | None = None,
    recipients: list[str] | None = None,
    attachment_paths: list[Path] | None = None,
) -> EmailSendResult:
    return _run_async_from_sync(
        lambda: send_email(
            subject=subject,
            plain_text=plain_text,
            markdown_text=markdown_text,
            html_text=html_text,
            recipients=recipients,
            attachment_paths=attachment_paths,
        )
    )


async def send_email(
    subject: str,
    plain_text: str,
    markdown_text: str | None = None,
    html_text: str | None = None,
    recipients: list[str] | None = None,
    attachment_paths: list[Path] | None = None,
) -> EmailSendResult:
    settings = get_settings()
    configured, reason = _smtp_configured()
    if not configured:
        logger.warning("SMTP is not configured; skipping email send. reason=%s", reason)
        return EmailSendResult(
            ok=False,
            message=reason,
            subject=subject,
            recipients=recipients or [settings.email_to],
        )

    message = EmailMessage()
    message["From"] = settings.email_from
    target_recipients = recipients or [settings.email_to]
    message["To"] = ", ".join(target_recipients)
    message["Subject"] = subject
    message.set_content(plain_text)
    rendered_html = html_text or (
        markdown_lib.markdown(markdown_text) if markdown_text is not None else None
    )
    if rendered_html:
        message.add_alternative(rendered_html, subtype="html")

    attached: list[str] = []
    for attachment_path in attachment_paths or []:
        if attachment_path.exists():
            subtype = "markdown" if attachment_path.suffix.lower() == ".md" else "plain"
            message.add_attachment(
                attachment_path.read_bytes(),
                maintype="text",
                subtype=subtype,
                filename=attachment_path.name,
            )
            attached.append(str(attachment_path))

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        start_tls=settings.smtp_starttls,
        timeout=30,
    )
    return EmailSendResult(
        ok=True,
        message="邮件发送成功",
        subject=subject,
        recipients=target_recipients,
        attachment_paths=attached,
    )

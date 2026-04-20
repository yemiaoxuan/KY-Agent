import logging
from datetime import date
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents.graphs.daily_research_graph import run_daily_research
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.runtime.runtime_config_service import load_runtime_config

logger = logging.getLogger(__name__)


def _job_state_path() -> Path:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings.storage_dir / "scheduler_daily_report.state"


def _job_key() -> str:
    runtime_config = load_runtime_config()
    recipients = ",".join(runtime_config.scheduler.email_recipients)
    topics = ",".join(runtime_config.scheduler.topic_names)
    return (
        f"{date.today().isoformat()}|{runtime_config.scheduler.daily_report_time}|"
        f"{runtime_config.scheduler.send_email}|{recipients}|{topics}"
    )


def _already_ran_today() -> bool:
    path = _job_state_path()
    if not path.exists():
        return False
    return path.read_text(encoding="utf-8").strip() == _job_key()


def _mark_ran_today() -> None:
    _job_state_path().write_text(_job_key(), encoding="utf-8")


def _run_scheduled_daily_report() -> None:
    if _already_ran_today():
        logger.info("Scheduled daily report already ran for current config; skipping")
        return
    db = SessionLocal()
    try:
        runtime_config = load_runtime_config()
        run_daily_research(
            db,
            topic_names=runtime_config.scheduler.topic_names or None,
            send_email=runtime_config.scheduler.send_email,
            email_recipients=runtime_config.scheduler.email_recipients or None,
        )
        _mark_ran_today()
    except Exception:
        logger.exception("Scheduled daily report failed")
    finally:
        db.close()


def _apply_scheduler_jobs(scheduler: BackgroundScheduler) -> None:
    settings = get_settings()
    runtime_config = load_runtime_config()
    scheduler.remove_all_jobs()
    if not runtime_config.scheduler.enabled:
        return
    try:
        hour, minute = runtime_config.scheduler.daily_report_time.split(":", maxsplit=1)
        hour_int = int(hour)
        minute_int = int(minute)
    except ValueError:
        logger.error(
            "Invalid daily_report_time=%s; scheduler job not registered",
            runtime_config.scheduler.daily_report_time,
        )
        return
    scheduler.add_job(
        _run_scheduled_daily_report,
        CronTrigger(hour=hour_int, minute=minute_int, timezone=settings.timezone),
        id="daily_research_report",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60,
    )


def create_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    _apply_scheduler_jobs(scheduler)
    return scheduler


def reload_scheduler(scheduler: BackgroundScheduler) -> None:
    _apply_scheduler_jobs(scheduler)

from datetime import date
from uuid import uuid4

from app.models.topic import Topic
from app.services.reporting.report_service import render_daily_report


def test_render_daily_report_without_papers() -> None:
    topic = Topic(
        id=uuid4(),
        name="test",
        display_name="Test Topic",
        query="test",
        include_keywords=[],
        exclude_keywords=[],
        arxiv_categories=[],
    )
    report = render_daily_report(topic, date(2026, 4, 16), [], [], [])
    assert "# 每日科研进展简报：Test Topic" in report
    assert "今日未筛选出足够相关的新论文" in report

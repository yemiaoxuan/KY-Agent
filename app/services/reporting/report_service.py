from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.models.topic import Topic
from app.schemas.paper import PaperCandidate, PaperSummary


def render_daily_report(
    topic: Topic,
    report_date: date,
    candidates: list[PaperCandidate],
    selected: list[PaperCandidate],
    summaries: list[PaperSummary],
    prompt_suffix: str | None = None,
) -> str:
    lines: list[str] = [
        f"# 每日科研进展简报：{topic.display_name}",
        "",
        f"- 日期：{report_date.isoformat()}",
        "- 数据源：arXiv",
        f"- 候选论文数：{len(candidates)}",
        f"- 入选论文数：{len(selected)}",
        "",
        "## 今日概览",
        "",
    ]
    if summaries:
        lines.append(
            f"今日筛选出 {len(summaries)} 篇与 `{topic.display_name}` 相关的论文。"
            "以下摘要基于 arXiv 标题和摘要生成，请以原文链接为准。"
        )
    else:
        lines.append("今日未筛选出足够相关的新论文。")

    if topic.report_prompt_hint or prompt_suffix:
        lines.extend(["", "## 本日报告偏好", ""])
        if topic.report_prompt_hint:
            lines.append(f"- 主题偏好：{topic.report_prompt_hint}")
        if prompt_suffix:
            lines.append(f"- 本次附加要求：{prompt_suffix}")

    lines.extend(["", "## 重点论文", ""])
    summary_by_id = {summary.source_id: summary for summary in summaries}
    for index, paper in enumerate(selected, start=1):
        summary = summary_by_id.get(paper.source_id)
        published_at = paper.published_at.date().isoformat() if paper.published_at else "未知"
        lines.extend(
            [
                f"### {index}. {paper.title}",
                "",
                f"- 作者：{', '.join(paper.authors[:8])}{' 等' if len(paper.authors) > 8 else ''}",
                f"- 发布时间：{published_at}",
                f"- arXiv：{paper.url}",
                f"- PDF：{paper.pdf_url or '无'}",
                f"- 相关性评分：{paper.relevance_score or 0:.2f}",
                "",
            ]
        )
        if summary is None:
            lines.extend([paper.abstract, ""])
            continue
        lines.extend(
            [
                f"**一句话总结：** {summary.one_sentence_summary}",
                "",
                "**核心贡献：**",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in summary.contributions)
        lines.extend(["", "**可能局限：**", ""])
        lines.extend(f"- {item}" for item in summary.limitations)
        lines.extend(
            [
                "",
                f"**为什么值得关注：** {summary.why_it_matters}",
                "",
                f"**相关性说明：** {summary.relevance_reason}",
                "",
            ]
        )

    lines.extend(
        [
            "## 趋势观察",
            "",
            "MVP 阶段暂以单日筛选结果为主。后续可将历史 arXiv 数据写入向量库后生成趋势分析。",
            "",
            "## 建议行动",
            "",
            "- 优先阅读评分最高的 3 篇论文。",
            "- 将与你当前项目相关的笔记上传到系统，便于后续 RAG 检索和研究对接。",
            "- 对误报关键词调整 `configs/topics.yaml` 中的 include/exclude 规则。",
            "",
        ]
    )
    return "\n".join(lines)


def save_report_markdown(topic: Topic, report_date: date, markdown_text: str) -> Path:
    settings = get_settings()
    topic_dir = settings.reports_dir / topic.name
    topic_dir.mkdir(parents=True, exist_ok=True)
    path = topic_dir / f"{report_date.isoformat()}.md"
    path.write_text(markdown_text, encoding="utf-8")
    return path

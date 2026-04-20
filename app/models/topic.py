from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Topic(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    include_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    arxiv_categories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    max_results: Mapped[int] = mapped_column(default=30, nullable=False)
    report_top_k: Mapped[int] = mapped_column(default=10, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    report_prompt_hint: Mapped[str | None] = mapped_column(Text)

    papers = relationship("ExternalPaper", back_populates="topic")
    reports = relationship("DailyReport", back_populates="topic")

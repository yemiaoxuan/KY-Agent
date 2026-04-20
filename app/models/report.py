from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class DailyReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("topic_id", "report_date", name="uq_daily_reports_topic_date"),
    )

    topic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    markdown_path: Mapped[str] = mapped_column(Text, nullable=False)
    email_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")

    topic = relationship("Topic", back_populates="reports")

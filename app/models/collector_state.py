"""열람실 수집기의 마지막 처리 상태를 저장하는 모델이다."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CollectorState(Base):
    """단일 행으로 collector와 보관 정리 상태를 기록한다."""

    __tablename__ = "collector_state"
    __table_args__ = (CheckConstraint("id = 1", name="singleton_id"),)

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        server_default=text("1"),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_cleanup_date: Mapped[date | None] = mapped_column(Date)
    last_cleanup_error_code: Mapped[str | None] = mapped_column(String(64))

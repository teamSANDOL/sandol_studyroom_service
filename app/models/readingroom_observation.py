"""열람실의 분 단위 혼잡도 관측을 저장하는 모델이다."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.readingroom import Readingroom


class ReadingroomObservation(Base):
    """열람실 한 곳의 한 분 단위 관측값이다."""

    __tablename__ = "readingroom_observations"
    __table_args__ = (
        CheckConstraint("total > 0", name="total_positive"),
        CheckConstraint("used >= 0", name="used_nonnegative"),
        CheckConstraint("available >= 0", name="available_nonnegative"),
        CheckConstraint("used + available = total", name="capacity_balances"),
        CheckConstraint(
            "date_trunc('minute', observed_at AT TIME ZONE 'UTC') "
            "= observed_minute AT TIME ZONE 'UTC'",
            name="minute_matches_observed_at",
        ),
        Index("ix_readingroom_observations_observed_minute", "observed_minute"),
    )

    readingroom_code: Mapped[str] = mapped_column(
        ForeignKey("readingrooms.code", ondelete="RESTRICT"),
        primary_key=True,
    )
    observed_minute: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)

    readingroom: Mapped["Readingroom"] = relationship(back_populates="observations")

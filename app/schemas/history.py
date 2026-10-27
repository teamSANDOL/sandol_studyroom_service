"""열람실 혼잡도 이력 API schema다."""

import datetime
from datetime import timedelta
from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import APISchema, UTCDateTime


class HistoryRoomCode(str, Enum):
    """혼잡도 이력을 제공하는 운영 열람실 코드다."""

    A1 = "A1"
    A2 = "A2"
    E1 = "E1"


class DailyHistoryReason(str, Enum):
    """일간 사용률을 계산할 수 없는 구간의 원인이다."""

    CLOSED = "closed"
    MISSING = "missing"
    FUTURE = "future"


class WeeklyHistoryReason(str, Enum):
    """주간 사용률을 계산할 수 없는 구간의 원인이다."""

    CLOSED = "closed"
    MISSING = "missing"
    FUTURE = "future"
    OUTSIDE_RETENTION = "outside_retention"


class MonthlyHistoryReason(str, Enum):
    """월간 사용률을 계산할 수 없는 구간의 원인이다."""

    CLOSED = "closed"
    MISSING = "missing"
    FUTURE = "future"
    OUTSIDE_RETENTION = "outside_retention"


class OccupancySummary(APISchema):
    """사용률과 집계 표본 수, 계산 불가 사유다."""

    percent: int | None = Field(ge=0, le=100)
    samples: int = Field(ge=0)
    reason: DailyHistoryReason | None

    @model_validator(mode="after")
    def require_consistent_summary(self) -> "OccupancySummary":
        """사용률 유무에 따라 표본 수와 사유를 맞춘다."""
        if self.reason is None:
            if self.percent is None or self.samples == 0:
                raise ValueError("a calculated percent requires at least one sample")
        elif self.percent is not None or self.samples != 0:
            raise ValueError("an unavailable percent requires zero samples")
        return self


class HourlyOccupancy(OccupancySummary):
    """일간 추이의 한 시간 구간이다."""

    hour: int = Field(ge=0, le=23)


class WeeklyOccupancySummary(OccupancySummary):
    """주간 집계에서 보관 범위 밖 사유도 표현한다."""

    reason: WeeklyHistoryReason | None  # type: ignore[assignment]


class TwoHourOccupancy(WeeklyOccupancySummary):
    """주간 추이의 한 시간 구간 시작점이다."""

    hour: int = Field(ge=0, le=22)


class HistoryMetadata(APISchema):
    """수집 상태와 이력 응답의 기준 시각이다."""

    first_date: datetime.date | None = Field(alias="firstDate")
    interval_seconds: int = Field(alias="intervalSeconds", gt=0)
    retention_days: int = Field(alias="retentionDays", gt=0)
    last_stored_at: UTCDateTime | None = Field(alias="lastStoredAt")
    collection_error: str | None = Field(alias="collectionError")
    collection_delayed: bool = Field(alias="collectionDelayed")
    updated_at: UTCDateTime = Field(alias="updatedAt")


class DailyHistoryResponse(HistoryMetadata):
    """선택 날짜의 요약과 24개 시간별 사용률이다."""

    room: HistoryRoomCode
    date: datetime.date
    summary: OccupancySummary
    hours: list[HourlyOccupancy] = Field(min_length=24, max_length=24)
    last_at: UTCDateTime | None = Field(alias="lastAt")

    @model_validator(mode="after")
    def require_all_hours_in_order(self) -> "DailyHistoryResponse":
        """0시부터 23시까지의 시간 구간을 요구한다."""
        if [item.hour for item in self.hours] != list(range(24)):
            raise ValueError("hours must contain 0 through 23 in order")
        return self


class WeeklyHistoryDay(APISchema):
    """요일 하나의 평균과 12개 두 시간 구간이다."""

    date: datetime.date
    summary: WeeklyOccupancySummary
    slots: list[TwoHourOccupancy] = Field(min_length=12, max_length=12)
    last_at: UTCDateTime | None = Field(alias="lastAt")

    @model_validator(mode="after")
    def require_all_slots_in_order(self) -> "WeeklyHistoryDay":
        """하루의 두 시간 구간 시작점 12개를 요구한다."""
        if [item.hour for item in self.slots] != list(range(0, 24, 2)):
            raise ValueError("slots must contain even hours from 0 through 22")
        return self


class WeeklyHistoryResponse(HistoryMetadata):
    """월요일부터 일요일까지의 주간 혼잡도다."""

    room: HistoryRoomCode
    date: datetime.date
    week_start: datetime.date = Field(alias="weekStart")
    week_end: datetime.date = Field(alias="weekEnd")
    summary: WeeklyOccupancySummary
    days: list[WeeklyHistoryDay] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def require_calendar_week(self) -> "WeeklyHistoryResponse":
        """주간 경계와 요일 목록이 월요일부터 이어지는지 확인한다."""
        if self.week_start.weekday() != 0:
            raise ValueError("weekStart must be a Monday")
        if self.week_end != self.week_start + timedelta(days=6):
            raise ValueError("weekEnd must be the Sunday after weekStart")
        if not self.week_start <= self.date <= self.week_end:
            raise ValueError("date must fall within weekStart and weekEnd")
        expected_dates = [
            self.week_start + timedelta(days=offset) for offset in range(7)
        ]
        if [item.date for item in self.days] != expected_dates:
            raise ValueError("days must cover weekStart through weekEnd in order")
        return self


class MonthlyOccupancySummary(OccupancySummary):
    """월간 집계에서 보관 범위 밖 사유도 표현한다."""

    reason: MonthlyHistoryReason | None  # type: ignore[assignment]


class MonthlyDay(MonthlyOccupancySummary):
    """월간 추이에서 날짜 하나의 일평균이다."""

    date: datetime.date


class MonthlyHour(MonthlyOccupancySummary):
    """월간 추이에서 시간대 하나의 월평균이다."""

    hour: int = Field(ge=0, le=23)


class MonthlyHistoryResponse(HistoryMetadata):
    """한 달의 날짜별 일평균과 시간대별 월평균이다."""

    room: HistoryRoomCode
    date: datetime.date
    month_start: datetime.date = Field(alias="monthStart")
    month_end: datetime.date = Field(alias="monthEnd")
    summary: MonthlyOccupancySummary
    days: list[MonthlyDay] = Field(min_length=28, max_length=31)
    hours: list[MonthlyHour] = Field(min_length=24, max_length=24)

    @model_validator(mode="after")
    def require_calendar_month(self) -> "MonthlyHistoryResponse":
        """달 경계와 날짜, 시간 목록이 달력과 맞는지 확인한다."""
        if self.month_start.day != 1:
            raise ValueError("monthStart must be the first day of the month")
        if (self.month_start.year, self.month_start.month) != (
            self.date.year,
            self.date.month,
        ):
            raise ValueError("date must fall within the month")
        if (self.month_end + timedelta(days=1)).day != 1:
            raise ValueError("monthEnd must be the last day of the month")
        span = (self.month_end - self.month_start).days + 1
        expected_dates = [
            self.month_start + timedelta(days=offset) for offset in range(span)
        ]
        if [item.date for item in self.days] != expected_dates:
            raise ValueError("days must cover the month in order")
        if [item.hour for item in self.hours] != list(range(24)):
            raise ValueError("hours must contain 0 through 23 in order")
        return self

"""열람실 혼잡도 이력 API schema다."""

from datetime import date, timedelta
from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import APISchema, UTCDateTime


class HistoryRoomCode(str, Enum):
    """혼잡도 이력을 제공하는 운영 열람실 코드다."""

    A1 = "A1"
    A2 = "A2"
    C1 = "C1"
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

    reason: WeeklyHistoryReason | None


class TwoHourOccupancy(WeeklyOccupancySummary):
    """주간 추이의 한 시간 구간 시작점이다."""

    hour: int = Field(ge=0, le=22)


class HistoryMetadata(APISchema):
    """수집 상태와 이력 응답의 기준 시각이다."""

    first_date: date | None = Field(alias="firstDate")
    interval_seconds: int = Field(alias="intervalSeconds", gt=0)
    retention_days: int = Field(alias="retentionDays", gt=0)
    last_stored_at: UTCDateTime | None = Field(alias="lastStoredAt")
    collection_error: str | None = Field(alias="collectionError")
    collection_delayed: bool = Field(alias="collectionDelayed")
    updated_at: UTCDateTime = Field(alias="updatedAt")


class DailyHistoryResponse(HistoryMetadata):
    """선택 날짜의 요약과 24개 시간별 사용률이다."""

    room: HistoryRoomCode
    date: date
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

    date: date
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
    date: date
    week_start: date = Field(alias="weekStart")
    week_end: date = Field(alias="weekEnd")
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
        expected_dates = [self.week_start + timedelta(days=offset) for offset in range(7)]
        if [item.date for item in self.days] != expected_dates:
            raise ValueError("days must cover weekStart through weekEnd in order")
        return self

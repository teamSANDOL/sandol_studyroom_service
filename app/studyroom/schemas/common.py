"""열람실과 스터디룸 schema 가 공유하는 운영 정책 형식이다."""

from datetime import date
from enum import Enum

from pydantic import Field

from app.core.schemas import APISchema


class PolicyDayKind(str, Enum):
    """적용한 운영 정책의 달력 구분이다."""

    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class OperationTimes(APISchema):
    """시작 시각과 종료 시각을 제공한다."""

    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class CalendarOperationTimes(OperationTimes):
    """주말 또는 공휴일의 개실 여부와 운영 시각이다."""

    enabled: bool


class OperatingPolicy(APISchema):
    """시설에 적용한 현재 운영 정책과 주간 정책이다."""

    enabled: bool
    allowed: bool
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    kind: PolicyDayKind
    weekday: OperationTimes
    weekend: CalendarOperationTimes
    holiday: CalendarOperationTimes
    notebook: bool
    hours: int = Field(gt=0)
    extend: bool
    gate: bool
    effective_date: date = Field(alias="effectiveDate")

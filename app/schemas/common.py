"""모든 API schema에서 재사용하는 검증 규칙이다."""

from datetime import date, timedelta
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


def _require_utc(value: AwareDatetime) -> AwareDatetime:
    """UTC offset이 아닌 timestamp를 거부한다."""
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return value


UTCDateTime = Annotated[AwareDatetime, AfterValidator(_require_utc)]


class APISchema(BaseModel):
    """모르는 응답 필드를 거부하고 Python 이름 입력도 허용한다."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


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

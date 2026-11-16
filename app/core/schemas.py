"""모든 도메인 API schema 가 공유하는 기반과 오류 응답 형식이다."""

from datetime import timedelta
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


class ErrorResponse(APISchema):
    """오류 설명과 기계 판독 코드를 제공한다."""

    error: str = Field(min_length=1)
    code: str = Field(min_length=1)
    details: list[object] | None = None

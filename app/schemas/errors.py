"""API 전체에서 공유하는 오류 응답 형식이다."""

from pydantic import Field

from app.schemas.common import APISchema


class ErrorResponse(APISchema):
    """오류 설명과 기계 판독 코드를 제공한다."""

    error: str = Field(min_length=1)
    code: str = Field(min_length=1)
    details: list[object] | None = None

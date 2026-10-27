"""공식 도서관 안내 API schema다."""

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from app.schemas.common import APISchema, UTCDateTime


class GuideSectionFailure(APISchema):
    """도서관 안내의 일부를 조회하지 못한 결과다."""

    ok: Literal[False]
    error: str = Field(min_length=1)


class LibraryHoursRow(APISchema):
    """한 층의 학기 및 방학 운영시간이다."""

    floor: str = Field(min_length=1)
    name: str = Field(min_length=1)
    semester: str
    vacation: str


class LibraryHoursSuccess(APISchema):
    """공식 운영시간을 성공적으로 읽은 결과다."""

    ok: Literal[True]
    updated_at: UTCDateTime = Field(alias="updatedAt")
    rows: list[LibraryHoursRow]
    source: str = Field(min_length=1)


class LibrarySpace(APISchema):
    """공식 공간 안내의 한 항목이다."""

    name: str = Field(min_length=1)
    floor: str = Field(min_length=1)
    usage: str
    hours: str
    phone: str
    source: str = Field(min_length=1)
    seats: int | None = Field(ge=0)


class LibrarySpacesSuccess(APISchema):
    """공식 공간 안내를 성공적으로 읽은 결과다."""

    ok: Literal[True]
    updated_at: UTCDateTime = Field(alias="updatedAt")
    spaces: list[LibrarySpace]
    source: str = Field(min_length=1)


class LibraryNotice(APISchema):
    """공개 운영 공지 목록의 한 항목이다."""

    id: int = Field(gt=0)
    title: str = Field(min_length=1)
    date: date
    updated: str = Field(min_length=1)
    url: str = Field(min_length=1)


class ExamPeriodSummary(APISchema):
    """원문을 검토해 확인한 시험기간 요약이다."""

    start: date
    end: date
    message: str = Field(min_length=1)
    source: str = Field(min_length=1)
    verified_at: UTCDateTime = Field(alias="verifiedAt")

    @model_validator(mode="after")
    def validate_period(self) -> "ExamPeriodSummary":
        """시험 종료일이 시작일보다 빠르지 않은지 확인한다."""
        if self.end < self.start:
            raise ValueError("end must not precede start")
        return self


class LibraryNoticesSuccess(APISchema):
    """공개 공지와 확인한 시험기간을 성공적으로 읽은 결과다."""

    ok: Literal[True]
    updated_at: UTCDateTime = Field(alias="updatedAt")
    items: list[LibraryNotice] = Field(alias="list", max_length=6)
    exam: ExamPeriodSummary | None
    scanned: int = Field(ge=0)
    source: str = Field(min_length=1)


HoursSection = Annotated[
    Union[LibraryHoursSuccess, GuideSectionFailure], Field(discriminator="ok")
]
SpacesSection = Annotated[
    Union[LibrarySpacesSuccess, GuideSectionFailure], Field(discriminator="ok")
]
NoticesSection = Annotated[
    Union[LibraryNoticesSuccess, GuideSectionFailure], Field(discriminator="ok")
]


class LibraryGuideResponse(APISchema):
    """운영시간, 공간, 공지의 성공 또는 부분 실패를 반환한다."""

    hours: HoursSection
    spaces: SpacesSection
    notices: NoticesSection

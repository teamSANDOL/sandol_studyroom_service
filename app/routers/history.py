"""열람실 혼잡도 이력 API다."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.errors import HistoryUnavailableError
from app.schemas.errors import ErrorResponse
from app.schemas.history import (
    DailyHistoryResponse,
    MonthlyHistoryResponse,
    WeeklyHistoryResponse,
)
from app.services.history import HistoryService
from app.services.readingroom import to_room_code

router = APIRouter(
    prefix="/api/readingrooms",
    tags=["history"],
    responses={
        503: {"model": ErrorResponse, "description": "이력 제공 불가"},
        404: {"model": ErrorResponse, "description": "지원하지 않는 열람실 코드"},
    },
)

RoomCode = Annotated[str, Path(description="열람실 코드. A1, A2, E1", examples=["A1"])]
# 범위 밖 날짜는 UTC 변환에서 overflow 가 나므로 경계에서 거른다.
MIN_DATE = date(1970, 1, 1)
MAX_DATE = date(2100, 12, 31)
TargetDate = Annotated[
    date | None,
    Query(
        ge=MIN_DATE,
        le=MAX_DATE,
        description=(
            "기준 날짜(YYYY-MM-DD). 1970-01-01부터 2100-12-31까지다. "
            "생략하면 오늘(한국 시각)이다."
        ),
    ),
]


def get_history(request: Request) -> HistoryService:
    service: HistoryService | None = request.app.state.history
    if service is None:
        raise HistoryUnavailableError
    return service


History = Annotated[HistoryService, Depends(get_history)]


@router.get("/{code}/history/daily", response_model=DailyHistoryResponse)
async def daily_history(
    code: RoomCode, service: History, date: TargetDate = None
) -> DailyHistoryResponse:
    """기준 날짜의 24시간 사용률 추이를 반환한다."""
    return await service.daily(to_room_code(code), date)


@router.get("/{code}/history/weekly", response_model=WeeklyHistoryResponse)
async def weekly_history(
    code: RoomCode, service: History, date: TargetDate = None
) -> WeeklyHistoryResponse:
    """기준 날짜가 속한 주의 요일별 2시간 구간 사용률을 반환한다."""
    return await service.weekly(to_room_code(code), date)


@router.get("/{code}/history/monthly", response_model=MonthlyHistoryResponse)
async def monthly_history(
    code: RoomCode, service: History, date: TargetDate = None
) -> MonthlyHistoryResponse:
    """기준 날짜가 속한 달의 날짜별 일평균과 시간대별 월평균을 반환한다."""
    return await service.monthly(to_room_code(code), date)

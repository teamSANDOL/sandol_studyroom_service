"""빈 강의실과 강의실 시간표 API 의 경로다. 파라미터와 본문은 담당자가 채운다."""

from fastapi import APIRouter

from app.core.errors import ServiceError
from app.core.schemas import ErrorResponse


class EndpointNotImplementedError(ServiceError):
    status_code = 501
    code = "not_implemented"
    message = "아직 구현하지 않은 API입니다."


router = APIRouter(
    prefix="/api/classrooms",
    tags=["classroom"],
    responses={501: {"model": ErrorResponse, "description": "구현 전"}},
)


@router.get("/available/time")
async def available_by_time() -> None:
    """시각 구간 동안 수업이 없는 강의실을 건물별로 반환한다."""
    raise EndpointNotImplementedError


@router.get("/available/periods")
async def available_by_periods() -> None:
    """교시 구간 동안 수업이 없는 강의실을 건물별로 반환한다."""
    raise EndpointNotImplementedError


@router.get("")
async def list_classrooms() -> None:
    """수업이 배정된 강의실 전체를 건물별로 반환한다."""
    raise EndpointNotImplementedError


@router.get("/timetable")
async def classroom_timetable() -> None:
    """강의실 하나의 수업 목록을 반환한다."""
    raise EndpointNotImplementedError

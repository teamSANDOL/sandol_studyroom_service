"""열람실 현황 API다."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request

from app.schemas.errors import ErrorResponse
from app.schemas.readingroom import (
    ReadingroomDetailResponse,
    ReadingroomListResponse,
    ReadingroomSeatResponse,
    ReadingroomSeatsResponse,
)
from app.services.readingroom import ReadingroomService, to_room_code

router = APIRouter(
    prefix="/api/readingrooms",
    tags=["readingrooms"],
    responses={502: {"model": ErrorResponse, "description": "학교 시스템 오류"}},
)
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "열람실 또는 좌석 없음"}
}

RoomCode = Annotated[str, Path(description="열람실 코드. A1, A2, E1", examples=["A1"])]
SeatNumber = Annotated[
    str, Path(pattern=r"^\d{1,4}$", description="좌석 번호", examples=["24"])
]


def get_service(request: Request) -> ReadingroomService:
    service: ReadingroomService = request.app.state.readingrooms
    return service


Service = Annotated[ReadingroomService, Depends(get_service)]


@router.get("", response_model=ReadingroomListResponse)
async def list_readingrooms(service: Service) -> ReadingroomListResponse:
    """열람실별 전체, 사용, 여유 좌석 수와 운영 상태를 반환한다."""
    return await service.list_rooms()


@router.get("/{code}", response_model=ReadingroomDetailResponse, responses=NOT_FOUND)
async def get_readingroom(
    code: RoomCode, service: Service
) -> ReadingroomDetailResponse:
    """열람실 정보와 30분 안에 이용이 끝나는 좌석을 반환한다."""
    return await service.room_detail(to_room_code(code))


@router.get(
    "/{code}/seats", response_model=ReadingroomSeatsResponse, responses=NOT_FOUND
)
async def list_seats(code: RoomCode, service: Service) -> ReadingroomSeatsResponse:
    """열람실의 전체 좌석 상태를 좌석 번호 순서로 반환한다."""
    return await service.seats(to_room_code(code))


@router.get(
    "/{code}/seats/{number}",
    response_model=ReadingroomSeatResponse,
    responses=NOT_FOUND,
)
async def get_seat(
    code: RoomCode, number: SeatNumber, service: Service
) -> ReadingroomSeatResponse:
    """좌석 하나의 상태, 남은 시간, 추정 종료 시각을 반환한다."""
    return await service.seat(to_room_code(code), number)

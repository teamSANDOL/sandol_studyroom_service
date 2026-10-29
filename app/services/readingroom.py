"""열람실 현황 조회를 조합한다."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from app.clients.school import SchoolClient
from app.errors import ReadingroomNotFoundError, SeatNotFoundError
from app.schemas.readingroom import (
    EndingSoonSeats,
    ReadingroomCode,
    ReadingroomDetail,
    ReadingroomDetailResponse,
    ReadingroomListResponse,
    ReadingroomSeat,
    ReadingroomSeatResponse,
    ReadingroomSeatsResponse,
    ReadingroomSeatStatus,
    ReadingroomSnapshot,
    ReadingroomSummary,
)
from app.services.live_cache import LiveCache
from app.services.readingroom_parser import parse_counts, parse_seats

ENDING_SOON_MINUTES = 30


def to_room_code(value: str) -> ReadingroomCode:
    try:
        return ReadingroomCode(value.upper())
    except ValueError:
        raise ReadingroomNotFoundError from None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def is_ending_soon(seat: ReadingroomSeat, within_minutes: int) -> bool:
    """사용 중이고 남은 시간이 기준 이하인 좌석이다. 0분도 아직 사용 중이다."""
    return (
        seat.status == ReadingroomSeatStatus.OCCUPIED
        and seat.remaining_minutes is not None
        and seat.remaining_minutes <= within_minutes
    )


class ReadingroomService:
    def __init__(
        self,
        school: SchoolClient,
        cache: LiveCache,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._school = school
        self._cache = cache
        self._clock = clock

    async def list_rooms(self) -> ReadingroomListResponse:
        snapshot = await self._snapshot()
        return ReadingroomListResponse(
            updatedAt=snapshot.updated_at,
            rooms=[
                ReadingroomSummary.model_validate(room.model_dump(exclude={"policy"}))
                for room in snapshot.rooms
            ],
        )

    async def room_detail(self, code: ReadingroomCode) -> ReadingroomDetailResponse:
        snapshot, seats = await asyncio.gather(self._snapshot(), self.seats(code))
        ending = sorted(
            (seat for seat in seats.seats if is_ending_soon(seat, ENDING_SOON_MINUTES)),
            key=lambda seat: (seat.remaining_minutes, int(seat.number)),
        )
        return ReadingroomDetailResponse(
            updatedAt=snapshot.updated_at,
            room=self._room(snapshot, code),
            endingSoon=EndingSoonSeats(
                withinMinutes=ENDING_SOON_MINUTES,
                updatedAt=seats.updated_at,
                seats=ending,
            ),
        )

    async def seats(self, code: ReadingroomCode) -> ReadingroomSeatsResponse:
        async def load() -> ReadingroomSeatsResponse:
            now = self._clock()
            payload = await self._school.fetch_seats(code.value)
            return ReadingroomSeatsResponse(
                roomCode=code,
                updatedAt=now,
                seats=parse_seats(payload, code, now),
            )

        return await self._cache.get_or_load(
            f"seats:{code.value}", ReadingroomSeatsResponse, load
        )

    async def seat(self, code: ReadingroomCode, number: str) -> ReadingroomSeatResponse:
        seats = await self.seats(code)
        wanted = str(int(number))
        for seat in seats.seats:
            if seat.number == wanted:
                return ReadingroomSeatResponse(
                    roomCode=code, updatedAt=seats.updated_at, seat=seat
                )
        raise SeatNotFoundError

    async def _snapshot(self) -> ReadingroomSnapshot:
        async def load() -> ReadingroomSnapshot:
            now = self._clock()
            return parse_counts(await self._school.fetch_counts(), now)

        return await self._cache.get_or_load("rooms", ReadingroomSnapshot, load)

    @staticmethod
    def _room(
        snapshot: ReadingroomSnapshot, code: ReadingroomCode
    ) -> ReadingroomDetail:
        return next(room for room in snapshot.rooms if room.code == code)

"""열람실 현황과 배치도 응답 schema다."""

from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import APISchema, OperatingPolicy, UTCDateTime


class ReadingroomCode(str, Enum):
    """열람실 현황 API가 지원하는 공간 코드다."""

    A1 = "A1"
    A2 = "A2"
    E1 = "E1"


class ReadingroomOperation(str, Enum):
    """열람실의 관측 시점 운영 상태다."""

    OPEN = "open"
    DISABLED = "disabled"
    OUTSIDE_HOURS = "outside_hours"
    CLOSED = "closed"


class ReadingroomSeatStatus(str, Enum):
    """좌석 원문 상태를 정규화한 값이다."""

    OCCUPIED = "occupied"
    AVAILABLE = "available"
    UNKNOWN = "unknown"


SEAT_STATUS_BY_SOURCE = {
    "U": ReadingroomSeatStatus.OCCUPIED,
    "D": ReadingroomSeatStatus.AVAILABLE,
}


class ReadingroomSeat(APISchema):
    """열람실 좌석 하나와 원문 상태다."""

    number: str = Field(pattern=r"^\d{1,4}$")
    name: str = Field(min_length=1)
    status: ReadingroomSeatStatus
    source_status: str = Field(alias="sourceStatus", min_length=1)
    remaining_minutes: int | None = Field(alias="remainingMinutes", ge=0)
    estimated_end_at: UTCDateTime | None = Field(alias="estimatedEndAt")

    @model_validator(mode="after")
    def require_status_mapping(self) -> "ReadingroomSeat":
        """정규화 상태가 좌석 원문 상태와 일치하는지 확인한다."""
        expected = SEAT_STATUS_BY_SOURCE.get(
            self.source_status, ReadingroomSeatStatus.UNKNOWN
        )
        if self.status != expected:
            raise ValueError("status must match sourceStatus")
        is_occupied = self.status == ReadingroomSeatStatus.OCCUPIED
        if self.remaining_minutes is not None and not is_occupied:
            raise ValueError("only occupied seats have remaining minutes")
        if (self.remaining_minutes is None) != (self.estimated_end_at is None):
            raise ValueError("remainingMinutes and estimatedEndAt go together")
        return self


class ReadingroomSummary(APISchema):
    """열람실 한 곳의 좌석 집계와 운영 상태다."""

    code: ReadingroomCode
    name: str = Field(min_length=1)
    total: int = Field(gt=0)
    used: int = Field(ge=0)
    available: int = Field(ge=0)
    operation: ReadingroomOperation

    @model_validator(mode="after")
    def require_consistent_counts(self) -> "ReadingroomSummary":
        """좌석 집계가 전체 수와 일치하는지 확인한다."""
        if self.used + self.available != self.total:
            raise ValueError("used plus available must equal total")
        return self


class ReadingroomDetail(ReadingroomSummary):
    """집계에 운영 정책을 더한 열람실 정보다."""

    policy: OperatingPolicy


def _require_room_order(codes: list[ReadingroomCode]) -> None:
    if codes != list(ReadingroomCode):
        raise ValueError("rooms must contain A1, A2, E1 in order")


class ReadingroomListResponse(APISchema):
    """대상 열람실 전체의 집계를 명세 순서로 반환한다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    rooms: list[ReadingroomSummary]

    @model_validator(mode="after")
    def require_all_rooms_in_order(self) -> "ReadingroomListResponse":
        """누락, 중복, 순서 변경이 있는 방 목록을 거부한다."""
        _require_room_order([room.code for room in self.rooms])
        return self


class ReadingroomSnapshot(APISchema):
    """정책까지 포함한 전체 열람실 조회 결과다. cache에 그대로 저장한다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    rooms: list[ReadingroomDetail]

    @model_validator(mode="after")
    def require_all_rooms_in_order(self) -> "ReadingroomSnapshot":
        """누락, 중복, 순서 변경이 있는 방 목록을 거부한다."""
        _require_room_order([room.code for room in self.rooms])
        return self


class ReadingroomSeatsResponse(APISchema):
    """열람실 한 곳의 전체 좌석 상태다."""

    room_code: ReadingroomCode = Field(alias="roomCode")
    updated_at: UTCDateTime = Field(alias="updatedAt")
    seats: list[ReadingroomSeat]


class EndingSoonSeats(APISchema):
    """기준 시간 안에 이용이 끝나는 사용 중 좌석이다."""

    within_minutes: int = Field(alias="withinMinutes", gt=0)
    updated_at: UTCDateTime = Field(alias="updatedAt")
    seats: list[ReadingroomSeat]


class ReadingroomDetailResponse(APISchema):
    """열람실 정보와 곧 반납되는 좌석 목록이다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    room: ReadingroomDetail
    ending_soon: EndingSoonSeats = Field(alias="endingSoon")


class ReadingroomSeatResponse(APISchema):
    """좌석 하나의 상태와 남은 시간이다."""

    room_code: ReadingroomCode = Field(alias="roomCode")
    updated_at: UTCDateTime = Field(alias="updatedAt")
    seat: ReadingroomSeat


class LayoutCell(APISchema):
    """좌석 또는 안내 문구 하나의 격자 위치다."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    seat: str | None
    label: str | None


class ReadingroomLayout(APISchema):
    """한 열람실의 좌석 배치 격자다."""

    columns: int = Field(gt=0)
    rows: int = Field(gt=0)
    cells: list[LayoutCell]

    @model_validator(mode="after")
    def validate_cells(self) -> "ReadingroomLayout":
        """cell 범위와 좌석 번호 중복을 검사한다."""
        seats: set[str] = set()
        for cell in self.cells:
            if cell.x + cell.w > self.columns or cell.y + cell.h > self.rows:
                raise ValueError("cell must fit within the layout grid")
            if cell.seat is not None:
                if cell.seat in seats:
                    raise ValueError("seat numbers must be unique within a layout")
                seats.add(cell.seat)
        return self


class ReadingroomLayoutsResponse(APISchema):
    """다섯 열람실의 배치도를 최상위 코드 key로 반환한다."""

    a1: ReadingroomLayout = Field(alias="A1")
    a2: ReadingroomLayout = Field(alias="A2")
    c1: ReadingroomLayout = Field(alias="C1")
    e1: ReadingroomLayout = Field(alias="E1")
    d1: ReadingroomLayout = Field(alias="D1")

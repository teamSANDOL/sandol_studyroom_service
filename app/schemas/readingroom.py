"""열람실 현황과 배치도 응답 schema다."""

from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import APISchema, OperatingPolicy, UTCDateTime


class ReadingroomCode(str, Enum):
    """열람실 현황 API가 지원하는 공간 코드다."""

    A1 = "A1"
    A2 = "A2"
    C1 = "C1"
    E1 = "E1"
    D1 = "D1"


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


class ReadingroomSeat(APISchema):
    """열람실 좌석 하나와 원문 상태다."""

    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: ReadingroomSeatStatus
    source_status: str = Field(alias="sourceStatus", min_length=1)
    remaining: int | None = Field(ge=0)

    @model_validator(mode="after")
    def require_status_mapping(self) -> "ReadingroomSeat":
        """정규화 상태가 좌석 원문 상태와 일치하는지 확인한다."""
        expected = {
            "U": ReadingroomSeatStatus.OCCUPIED,
            "D": ReadingroomSeatStatus.AVAILABLE,
        }.get(self.source_status, ReadingroomSeatStatus.UNKNOWN)
        if self.status != expected:
            raise ValueError("status must match sourceStatus")
        return self


class ReadingroomRoom(APISchema):
    """집계, 운영 정책, 좌석 목록을 묶은 열람실이다."""

    code: ReadingroomCode
    name: str = Field(min_length=1)
    total: int = Field(gt=0)
    used: int = Field(ge=0)
    available: int = Field(ge=0)
    operation: ReadingroomOperation
    policy: OperatingPolicy
    seats: list[ReadingroomSeat]

    @model_validator(mode="after")
    def require_consistent_counts(self) -> "ReadingroomRoom":
        """좌석 집계가 전체 수와 일치하는지 확인한다."""
        if self.used + self.available != self.total:
            raise ValueError("used plus available must equal total")
        return self


class ReadingroomRoomsResponse(APISchema):
    """다섯 열람실의 현황을 명세 순서로 반환한다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    rooms: list[ReadingroomRoom] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def require_all_rooms_in_order(self) -> "ReadingroomRoomsResponse":
        """누락, 중복, 순서 변경이 있는 방 목록을 거부한다."""
        expected = ["A1", "A2", "C1", "E1", "D1"]
        if [room.code.value for room in self.rooms] != expected:
            raise ValueError("rooms must contain A1, A2, C1, E1, D1 in order")
        return self


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

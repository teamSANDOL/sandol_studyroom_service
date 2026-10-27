"""스터디룸 현재 상태 API의 응답 형식이다."""

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from app.schemas.common import APISchema, OperatingPolicy, UTCDateTime


class StudyroomStatus(str, Enum):
    """클라이언트에 제공하는 정규화된 스터디룸 상태다."""

    OCCUPIED = "occupied"
    RESERVED = "reserved"
    AVAILABLE = "available"
    UNKNOWN = "unknown"


class StudyroomRoom(APISchema):
    """스터디룸 한 곳의 현재 상태와 학교 원문 상태다."""

    number: str = Field(pattern="^[1-6]$")
    status: StudyroomStatus
    source_status: str = Field(alias="sourceStatus", min_length=1)

    @model_validator(mode="after")
    def require_status_mapping(self) -> "StudyroomRoom":
        """정규화 상태가 학교 원문 상태와 일치하는지 확인한다."""
        expected = {
            "1": StudyroomStatus.OCCUPIED,
            "2": StudyroomStatus.RESERVED,
            "3": StudyroomStatus.AVAILABLE,
        }.get(self.source_status, StudyroomStatus.UNKNOWN)
        if self.status != expected:
            raise ValueError("status must match sourceStatus")
        return self


class StudyroomRoomsResponse(APISchema):
    """여섯 방의 상태를 번호순으로 반환한다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    rooms: list[StudyroomRoom] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def require_all_rooms_in_order(self) -> "StudyroomRoomsResponse":
        """누락, 중복, 순서 변경이 있는 방 목록을 거부한다."""
        if [room.number for room in self.rooms] != list("123456"):
            raise ValueError("rooms must contain numbers 1 through 6 in order")
        return self


class ReservationRecordType(str, Enum):
    """예약 자료의 해석 상태다."""

    RESERVATION = "reservation"
    UNCLASSIFIED = "unclassified"


class StudyroomReservation(APISchema):
    """스터디룸 한 건의 예약 시간과 원문 flag다."""

    room: str = Field(pattern="^[1-6]$")
    start: int = Field(ge=0, le=23)
    end: int = Field(ge=1, le=24)
    record_type: ReservationRecordType = Field(alias="recordType")
    source_flag: str = Field(alias="sourceFlag", min_length=1)

    @model_validator(mode="after")
    def require_positive_duration(self) -> "StudyroomReservation":
        """예약 종료 slot이 시작 slot보다 뒤인지 확인한다."""
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self

    @model_validator(mode="after")
    def require_record_classification(self) -> "StudyroomReservation":
        """원문 flag가 N일 때만 reservation으로 분류한다."""
        expected = (
            ReservationRecordType.RESERVATION
            if self.source_flag == "N"
            else ReservationRecordType.UNCLASSIFIED
        )
        if self.record_type != expected:
            raise ValueError("recordType must match sourceFlag")
        return self


class StudyroomReservationsResponse(APISchema):
    """하루의 운영 정책과 예약 기록 목록이다."""

    updated_at: UTCDateTime = Field(alias="updatedAt")
    date: date
    policy: OperatingPolicy
    reservations: list[StudyroomReservation]

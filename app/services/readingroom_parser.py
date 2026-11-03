"""학교 좌석 시스템 원문을 서비스 schema로 바꾼다.

필드 의미와 판정 규칙의 근거는 docs/studyroom-info.md 에 있다.
"""

import logging
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta, timezone

from pydantic import ValidationError

from app.errors import SchoolResponseError
from app.schemas.common import (
    CalendarOperationTimes,
    OperatingPolicy,
    OperationTimes,
    PolicyDayKind,
)
from app.schemas.readingroom import (
    SEAT_STATUS_BY_SOURCE,
    ReadingroomCode,
    ReadingroomDetail,
    ReadingroomOperation,
    ReadingroomSeat,
    ReadingroomSeatStatus,
    ReadingroomSnapshot,
)

logger = logging.getLogger(__name__)

# 한국은 일광절약시간이 없으므로 tzdata 없이 고정 offset을 쓴다.
KST = timezone(timedelta(hours=9))
_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_COMPACT_TIME = re.compile(r"^\d{4}$")
_DIGITS = re.compile(r"^\d+$")
_TARGET_CODES = frozenset(code.value for code in ReadingroomCode)


class _InvalidField(ValueError):
    pass


def _field(raw: Mapping[str, object], name: str) -> object:
    if name not in raw:
        raise _InvalidField(name)
    return raw[name]


def _text(raw: Mapping[str, object], name: str) -> str:
    value = _field(raw, name)
    if not isinstance(value, str | int) or isinstance(value, bool):
        raise _InvalidField(name)
    text = str(value).strip()
    if not text:
        raise _InvalidField(name)
    return text


def _count(raw: Mapping[str, object], name: str) -> int:
    text = _text(raw, name)
    if not _DIGITS.fullmatch(text):
        raise _InvalidField(name)
    return int(text)


def _flag(raw: Mapping[str, object], name: str) -> bool:
    return _text(raw, name) == "Y"


def _time(raw: Mapping[str, object], name: str) -> str:
    text = _text(raw, name)
    if _COMPACT_TIME.fullmatch(text):
        text = f"{text[:2]}:{text[2:]}"
    if not _TIME.fullmatch(text):
        raise _InvalidField(name)
    return text


def _policy_date(raw: Mapping[str, object], name: str) -> date:
    try:
        return datetime.strptime(_text(raw, name), "%Y/%m/%d").date()
    except ValueError:
        raise _InvalidField(name) from None


def parse_policy(raw: Mapping[str, object]) -> OperatingPolicy:
    """평일 기준에 주말, 휴일 순서로 덮어써 당일 정책을 정한다."""
    enabled = _flag(raw, "USE_YN")
    weekday = OperationTimes(start=_time(raw, "START_TIME"), end=_time(raw, "END_TIME"))
    weekend = CalendarOperationTimes(
        enabled=_flag(raw, "WEEKEND_YN"),
        start=_time(raw, "WEEKEND_START"),
        end=_time(raw, "WEEKEND_END"),
    )
    holiday = CalendarOperationTimes(
        enabled=_flag(raw, "HOLIDAY_YN"),
        start=_time(raw, "HOLIDAY_START"),
        end=_time(raw, "HOLIDAY_END"),
    )
    kind, today, allowed = PolicyDayKind.WEEKDAY, weekday, enabled
    if _flag(raw, "TODAY_WEEKEND_YN"):
        kind, today, allowed = (
            PolicyDayKind.WEEKEND,
            weekend,
            enabled and weekend.enabled,
        )
    if _flag(raw, "TODAY_HOLIDAY_YN"):
        kind, today, allowed = (
            PolicyDayKind.HOLIDAY,
            holiday,
            enabled and holiday.enabled,
        )
    hours = _count(raw, "ASSIGN_HOUR")
    if hours <= 0:
        raise _InvalidField("ASSIGN_HOUR")
    return OperatingPolicy(
        enabled=enabled,
        allowed=allowed and today.start != today.end,
        start=today.start,
        end=today.end,
        kind=kind,
        weekday=weekday,
        weekend=weekend,
        holiday=holiday,
        notebook=_flag(raw, "NOTEBOOK_YN"),
        hours=hours,
        extend=_flag(raw, "EXTEND_YN"),
        gate=_flag(raw, "SYNC_WITH_GATE"),
        effectiveDate=_policy_date(raw, "START_DATE"),
    )


def decide_operation(policy: OperatingPolicy, now: datetime) -> ReadingroomOperation:
    """관측 시각의 한국 시각으로 운영 상태를 판정한다."""
    if not policy.enabled:
        return ReadingroomOperation.DISABLED
    if not policy.allowed:
        return ReadingroomOperation.CLOSED
    current = now.astimezone(KST).strftime("%H:%M")
    if policy.start < policy.end:
        is_open = policy.start <= current <= policy.end
    else:
        is_open = current >= policy.start or current <= policy.end
    return ReadingroomOperation.OPEN if is_open else ReadingroomOperation.OUTSIDE_HOURS


def _parse_room(raw: Mapping[str, object], now: datetime) -> ReadingroomDetail:
    policy = parse_policy(raw)
    return ReadingroomDetail(
        code=ReadingroomCode(_text(raw, "ROOM_CODE")),
        name=_text(raw, "ROOM_NAME"),
        total=_count(raw, "TOTAL_COUNT"),
        used=_count(raw, "INUSE_COUNT"),
        available=_count(raw, "NOTINUSE_COUNT"),
        operation=decide_operation(policy, now),
        policy=policy,
    )


def parse_counts(payload: list[object], now: datetime) -> ReadingroomSnapshot:
    """전체 집계 응답에서 대상 열람실만 골라 명세 순서로 정렬한다."""
    by_code: dict[str, Mapping[str, object]] = {}
    for item in payload:
        if isinstance(item, Mapping) and item.get("ROOM_CODE") in _TARGET_CODES:
            by_code[str(item["ROOM_CODE"])] = item
    try:
        rooms = [_parse_room(by_code[code.value], now) for code in ReadingroomCode]
        return ReadingroomSnapshot(updatedAt=now.astimezone(UTC), rooms=rooms)
    except KeyError as error:
        logger.warning("school counts missing room %s", error)
    except (_InvalidField, ValidationError) as error:
        logger.warning("school counts invalid: %s", _describe(error))
    raise SchoolResponseError


def _remaining(raw: Mapping[str, object], status: ReadingroomSeatStatus) -> int | None:
    if status != ReadingroomSeatStatus.OCCUPIED:
        return None
    value = raw.get("SEAT_TIME_GAP")
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    try:
        minutes = int(float(value))
    except ValueError:
        return None
    return minutes if minutes >= 0 else None


def _parse_seat(raw: Mapping[str, object], now: datetime) -> ReadingroomSeat:
    # 개인정보 필드(SEAT_USER_*)는 읽지 않는다.
    source_status = _text(raw, "SEAT_STATUS")
    status = SEAT_STATUS_BY_SOURCE.get(source_status, ReadingroomSeatStatus.UNKNOWN)
    remaining = _remaining(raw, status)
    return ReadingroomSeat(
        number=str(_count(raw, "SEAT_CODE")),
        name=_text(raw, "SEAT_NAME"),
        status=status,
        sourceStatus=source_status,
        remainingMinutes=remaining,
        estimatedEndAt=None
        if remaining is None
        else now + timedelta(minutes=remaining),
    )


def parse_seats(
    payload: list[object], room_code: ReadingroomCode, now: datetime
) -> list[ReadingroomSeat]:
    """좌석 응답을 좌석 번호 순서로 정규화한다."""
    now = now.astimezone(UTC)
    try:
        seats = []
        for item in payload:
            if (
                not isinstance(item, Mapping)
                or item.get("ROOM_CODE") != room_code.value
            ):
                raise _InvalidField("ROOM_CODE")
            seats.append(_parse_seat(item, now))
    except (_InvalidField, ValidationError) as error:
        logger.warning(
            "school seats invalid for %s: %s", room_code.value, _describe(error)
        )
        raise SchoolResponseError from None
    if not seats or len({seat.number for seat in seats}) != len(seats):
        logger.warning("school seats empty or duplicated for %s", room_code.value)
        raise SchoolResponseError
    return sorted(seats, key=lambda seat: int(seat.number))


def _describe(error: Exception) -> str:
    # ValidationError 문자열에는 입력값이 들어가므로 위치만 남긴다.
    if isinstance(error, ValidationError):
        return ", ".join(".".join(map(str, e["loc"])) for e in error.errors())
    return f"field {error}"

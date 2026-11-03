"""관측 기록을 일간, 주간, 월간 혼잡도 통계로 집계한다.

집계 규칙은 순수 함수(build_daily 등)에 두어 DB 없이 검증한다.
HistoryService 는 구간에 맞는 관측을 읽어 그 함수에 넘긴다.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import cached_property
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import Settings
from app.errors import HistoryUnavailableError
from app.models import CollectorState, ReadingroomObservation
from app.schemas.history import (
    DailyHistoryResponse,
    HistoryRoomCode,
    MonthlyHistoryResponse,
    WeeklyHistoryResponse,
)
from app.schemas.readingroom import ReadingroomCode
from app.services.live_cache import LiveCache
from app.services.readingroom_parser import KST

logger = logging.getLogger(__name__)

_Response = TypeVar("_Response")
_Model = TypeVar("_Model", bound=BaseModel)

# 사유가 있으면 사용률은 없다. 네 enum 이 같은 문자열을 공유한다.
_FUTURE = "future"
_CLOSED = "closed"
_MISSING = "missing"
_OUTSIDE_RETENTION = "outside_retention"


@dataclass(frozen=True)
class ObservationPoint:
    """집계에 필요한 한 관측의 최소 정보다. 시각은 UTC다."""

    observed_minute: datetime
    total: int
    used: int
    is_open: bool

    # 집계가 같은 관측의 local 을 수만 번 다시 읽으므로 한 번만 계산한다.
    @cached_property
    def local(self) -> datetime:
        return self.observed_minute.astimezone(KST)


@dataclass(frozen=True)
class HistoryContext:
    """응답 메타데이터와 사유 판정에 쓰는 수집 상태다."""

    now: datetime
    first_date: date | None
    interval_seconds: int
    retention_days: int
    stale_after_minutes: int
    last_stored_at: datetime | None
    collection_error: str | None


def _metadata(ctx: HistoryContext) -> dict[str, Any]:
    now = ctx.now.astimezone(UTC)
    stale = timedelta(minutes=ctx.stale_after_minutes)
    delayed = (
        ctx.last_stored_at is None or now - ctx.last_stored_at.astimezone(UTC) > stale
    )
    return {
        "firstDate": ctx.first_date,
        "intervalSeconds": ctx.interval_seconds,
        "retentionDays": ctx.retention_days,
        "lastStoredAt": ctx.last_stored_at,
        "collectionError": ctx.collection_error,
        "collectionDelayed": delayed,
        "updatedAt": now,
    }


def _summary(
    points: list[ObservationPoint], *, future: bool, empty: str
) -> dict[str, Any]:
    """구간의 관측을 사용률, 표본 수, 불가 사유, 관측 존재로 요약한다."""
    if future:
        return {"percent": None, "samples": 0, "reason": _FUTURE, "is_collected": False}
    open_points = [p for p in points if p.is_open and p.total > 0]
    if open_points:
        ratio = sum(p.used / p.total for p in open_points) / len(open_points)
        return {
            "percent": round(ratio * 100),
            "samples": len(open_points),
            "reason": None,
            "is_collected": True,
        }
    if points:
        # 관측은 있으나 모두 휴실이다. 관측 자체는 존재한다.
        return {"percent": None, "samples": 0, "reason": _CLOSED, "is_collected": True}
    return {"percent": None, "samples": 0, "reason": empty, "is_collected": False}


def _at(day: date, hour: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=KST)


def _empty_reason(day: date, ctx: HistoryContext, today: date) -> str:
    """관측이 없는 과거 구간을 보관 범위 밖인지 수집 누락인지 가른다."""
    cutoff = today - timedelta(days=ctx.retention_days)
    if day < cutoff:
        return _OUTSIDE_RETENTION
    if ctx.first_date is not None and day < ctx.first_date:
        return _OUTSIDE_RETENTION
    return _MISSING


def _last_at(points: list[ObservationPoint]) -> datetime | None:
    return max((p.observed_minute for p in points), default=None)


def build_daily(
    points: list[ObservationPoint],
    room: HistoryRoomCode,
    target: date,
    ctx: HistoryContext,
) -> DailyHistoryResponse:
    """선택 날짜의 요약과 24개 시간별 사용률을 만든다."""
    now_local = ctx.now.astimezone(KST)
    day_points = [p for p in points if p.local.date() == target]
    by_hour: dict[int, list[ObservationPoint]] = {hour: [] for hour in range(24)}
    for point in day_points:
        by_hour[point.local.hour].append(point)

    hours = [
        {
            "hour": hour,
            **_summary(
                by_hour[hour], future=_at(target, hour) > now_local, empty=_MISSING
            ),
        }
        for hour in range(24)
    ]
    summary = _summary(day_points, future=_at(target) > now_local, empty=_MISSING)
    return DailyHistoryResponse(
        room=room,
        date=target,
        summary=summary,  # type: ignore[arg-type]
        hours=hours,  # type: ignore[arg-type]
        lastAt=_last_at(day_points),
        **_metadata(ctx),
    )


def build_weekly(
    points: list[ObservationPoint],
    room: HistoryRoomCode,
    target: date,
    ctx: HistoryContext,
) -> WeeklyHistoryResponse:
    """선택 날짜가 속한 월요일부터 일요일까지를 요일x12구간으로 만든다."""
    now_local = ctx.now.astimezone(KST)
    today = now_local.date()
    week_start = target - timedelta(days=target.weekday())
    week_end = week_start + timedelta(days=6)

    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        day_points = [p for p in points if p.local.date() == day]
        empty = _empty_reason(day, ctx, today)
        slots = [
            {
                "hour": hour,
                **_summary(
                    [p for p in day_points if hour <= p.local.hour < hour + 2],
                    future=_at(day, hour) > now_local,
                    empty=empty,
                ),
            }
            for hour in range(0, 24, 2)
        ]
        days.append(
            {
                "date": day,
                "summary": _summary(
                    day_points, future=_at(day) > now_local, empty=empty
                ),
                "slots": slots,
                "lastAt": _last_at(day_points),
            }
        )

    week_points = [p for p in points if week_start <= p.local.date() <= week_end]
    summary = _summary(
        week_points,
        future=_at(week_start) > now_local,
        empty=_empty_reason(week_end, ctx, today),
    )
    return WeeklyHistoryResponse(
        room=room,
        date=target,
        weekStart=week_start,
        weekEnd=week_end,
        summary=summary,  # type: ignore[arg-type]
        days=days,  # type: ignore[arg-type]
        **_metadata(ctx),
    )


def _month_bounds(target: date) -> tuple[date, date]:
    start = target.replace(day=1)
    if start.month == 12:
        next_first = date(start.year + 1, 1, 1)
    else:
        next_first = date(start.year, start.month + 1, 1)
    return start, next_first - timedelta(days=1)


def build_monthly(
    points: list[ObservationPoint],
    room: HistoryRoomCode,
    target: date,
    ctx: HistoryContext,
) -> MonthlyHistoryResponse:
    """선택 날짜가 속한 달의 날짜별 일평균과 시간대별 월평균을 만든다."""
    now_local = ctx.now.astimezone(KST)
    today = now_local.date()
    month_start, month_end = _month_bounds(target)
    month_points = [p for p in points if month_start <= p.local.date() <= month_end]
    month_future = _at(month_start) > now_local

    days = []
    span = (month_end - month_start).days + 1
    for offset in range(span):
        day = month_start + timedelta(days=offset)
        day_points = [p for p in month_points if p.local.date() == day]
        days.append(
            {
                "date": day,
                **_summary(
                    day_points,
                    future=_at(day) > now_local,
                    empty=_empty_reason(day, ctx, today),
                ),
            }
        )

    hour_empty = _empty_reason(month_end, ctx, today)
    hours = [
        {
            "hour": hour,
            **_summary(
                [p for p in month_points if p.local.hour == hour],
                future=month_future,
                empty=hour_empty,
            ),
        }
        for hour in range(24)
    ]
    summary = _summary(month_points, future=month_future, empty=hour_empty)
    return MonthlyHistoryResponse(
        room=room,
        date=target,
        monthStart=month_start,
        monthEnd=month_end,
        summary=summary,  # type: ignore[arg-type]
        days=days,  # type: ignore[arg-type]
        hours=hours,  # type: ignore[arg-type]
        **_metadata(ctx),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _window(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    """KST 날짜 범위를 조회용 UTC 반열린 구간으로 바꾼다."""
    start = _at(start_day).astimezone(UTC)
    end = (_at(end_day) + timedelta(days=1)).astimezone(UTC)
    return start, end


class HistoryService:
    """구간에 맞는 관측을 읽어 통계 응답으로 집계한다."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        clock: Callable[[], datetime] = _utc_now,
        cache: LiveCache | None = None,
    ) -> None:
        self._factory = session_factory
        self._settings = settings
        self._clock = clock
        self._cache = cache

    async def daily(
        self, room: ReadingroomCode, target: date | None
    ) -> DailyHistoryResponse:
        now = self._clock()
        day = target or now.astimezone(KST).date()
        return await self._cached(
            f"daily:{room.value}:{day}",
            DailyHistoryResponse,
            now,
            day,
            lambda: self._run(
                room,
                now,
                _window(day, day),
                build_daily,
                HistoryRoomCode(room.value),
                day,
            ),
        )

    async def weekly(
        self, room: ReadingroomCode, target: date | None
    ) -> WeeklyHistoryResponse:
        now = self._clock()
        day = target or now.astimezone(KST).date()
        start = day - timedelta(days=day.weekday())
        return await self._cached(
            f"weekly:{room.value}:{start}",
            WeeklyHistoryResponse,
            now,
            day,
            lambda: self._run(
                room,
                now,
                _window(start, start + timedelta(days=6)),
                build_weekly,
                HistoryRoomCode(room.value),
                day,
            ),
        )

    async def monthly(
        self, room: ReadingroomCode, target: date | None
    ) -> MonthlyHistoryResponse:
        now = self._clock()
        day = target or now.astimezone(KST).date()
        start, end = _month_bounds(day)
        return await self._cached(
            f"monthly:{room.value}:{start:%Y-%m}",
            MonthlyHistoryResponse,
            now,
            day,
            lambda: self._run(
                room,
                now,
                _window(start, end),
                build_monthly,
                HistoryRoomCode(room.value),
                day,
            ),
        )

    async def _cached(
        self,
        key: str,
        model: type[_Model],
        now: datetime,
        day: date,
        load: Callable[[], Awaitable[_Model]],
    ) -> _Model:
        # 보관 기간 밖 날짜는 cache 하지 않는다. 요청마다 key 가 늘어 Redis 가 커진다.
        today = now.astimezone(KST).date()
        oldest = today - timedelta(days=self._settings.history_retention_days)
        if self._cache is None or not oldest <= day <= today:
            return await load()
        cached = await self._cache.get_or_load(key, model, load)
        # 주와 달은 key 를 기간 시작으로 묶으므로 응답의 date 를 요청 값으로 되돌린다.
        return cached.model_copy(update={"date": day})

    async def _run(
        self,
        room: ReadingroomCode,
        now: datetime,
        window: tuple[datetime, datetime],
        build: Callable[
            [list[ObservationPoint], HistoryRoomCode, date, HistoryContext],
            _Response,
        ],
        room_code: HistoryRoomCode,
        target: date,
    ) -> _Response:
        try:
            async with self._factory() as session:
                points = await self._fetch(session, room, window)
                ctx = await self._context(session, now)
        except SQLAlchemyError:
            logger.warning("history query failed for %s", room.value)
            raise HistoryUnavailableError from None
        # 한 달 집계가 수백 ms 걸리므로 event loop 를 막지 않게 thread 로 보낸다.
        return await asyncio.to_thread(build, points, room_code, target, ctx)

    @staticmethod
    async def _fetch(
        session: AsyncSession,
        room: ReadingroomCode,
        window: tuple[datetime, datetime],
    ) -> list[ObservationPoint]:
        start, end = window
        rows = await session.execute(
            select(
                ReadingroomObservation.observed_minute,
                ReadingroomObservation.total,
                ReadingroomObservation.used,
                ReadingroomObservation.is_open,
            ).where(
                ReadingroomObservation.readingroom_code == room.value,
                ReadingroomObservation.observed_minute >= start,
                ReadingroomObservation.observed_minute < end,
            )
        )
        return [
            ObservationPoint(
                observed_minute=row.observed_minute,
                total=row.total,
                used=row.used,
                is_open=row.is_open,
            )
            for row in rows
        ]

    async def _context(self, session: AsyncSession, now: datetime) -> HistoryContext:
        first = await session.scalar(
            select(func.min(ReadingroomObservation.observed_minute))
        )
        state = await session.get(CollectorState, 1)
        return HistoryContext(
            now=now,
            first_date=first.astimezone(KST).date() if first is not None else None,
            interval_seconds=self._settings.collection_interval_minutes * 60,
            retention_days=self._settings.history_retention_days,
            stale_after_minutes=self._settings.collection_stale_after_minutes,
            last_stored_at=state.last_stored_at if state is not None else None,
            collection_error=state.last_error_code if state is not None else None,
        )

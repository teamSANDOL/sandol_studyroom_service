"""혼잡도 통계 집계와 조회 서비스를 검증한다."""

import os
import threading
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import Settings
from app.main import create_app
from app.models import Base, CollectorState, Readingroom, ReadingroomObservation
from app.schemas.history import (
    DailyHistoryReason,
    HistoryRoomCode,
    MonthlyHistoryReason,
    WeeklyHistoryReason,
)
from app.schemas.readingroom import ReadingroomCode
from app.services import history as history_module
from app.services.history import (
    HistoryContext,
    HistoryService,
    ObservationPoint,
    build_daily,
    build_monthly,
    build_weekly,
)
from app.services.live_cache import LiveCache

KST = timezone(timedelta(hours=9))


def point(
    local: datetime, used: int, *, total: int = 100, is_open: bool = True
) -> ObservationPoint:
    return ObservationPoint(
        observed_minute=local.astimezone(UTC), total=total, used=used, is_open=is_open
    )


def context(
    now: datetime,
    *,
    first_date: date | None = None,
    retention_days: int = 90,
    last_stored_at: datetime | None = None,
    error: str | None = None,
    stale: int = 7,
) -> HistoryContext:
    return HistoryContext(
        now=now.astimezone(UTC),
        first_date=first_date,
        interval_seconds=180,
        retention_days=retention_days,
        stale_after_minutes=stale,
        last_stored_at=last_stored_at,
        collection_error=error,
    )


def test_daily_averages_open_and_marks_closed_future_missing() -> None:
    target = date(2026, 10, 13)
    now = datetime(2026, 10, 13, 12, 30, tzinfo=KST)
    points = [
        point(datetime(2026, 10, 13, 9, 5, tzinfo=KST), 40),
        point(datetime(2026, 10, 13, 9, 50, tzinfo=KST), 60),
        point(datetime(2026, 10, 13, 10, 10, tzinfo=KST), 70, is_open=False),
    ]

    result = build_daily(points, HistoryRoomCode.A1, target, context(now))

    nine = result.hours[9]
    assert (nine.percent, nine.samples, nine.reason) == (50, 2, None)
    assert nine.is_collected is True
    assert result.hours[10].reason == DailyHistoryReason.CLOSED
    assert result.hours[10].is_collected is True  # 휴실도 관측은 있었다
    assert result.hours[11].reason == DailyHistoryReason.MISSING
    assert result.hours[11].is_collected is False
    assert result.hours[13].reason == DailyHistoryReason.FUTURE
    assert result.hours[13].is_collected is False
    assert (result.summary.percent, result.summary.samples) == (50, 2)
    # last_at 은 열림, 닫힘을 가리지 않고 그날 마지막 관측 시각이다.
    assert result.last_at == datetime(2026, 10, 13, 10, 10, tzinfo=KST).astimezone(UTC)


def test_daily_percent_rounds_to_zero_still_counts_samples() -> None:
    target = date(2026, 10, 13)
    now = datetime(2026, 10, 13, 23, 59, tzinfo=KST)
    points = [point(datetime(2026, 10, 13, 8, 0, tzinfo=KST), 0)]

    result = build_daily(points, HistoryRoomCode.A1, target, context(now))

    eight = result.hours[8]
    assert (eight.percent, eight.samples, eight.reason) == (0, 1, None)
    # 진짜 빈 열람실(0%)도 관측이 있었으므로 is_collected 는 참이다.
    assert eight.is_collected is True


def test_weekly_covers_monday_to_sunday_with_two_hour_slots() -> None:
    target = date(2026, 10, 14)  # 수요일
    now = datetime(2026, 10, 14, 12, 0, tzinfo=KST)
    points = [point(datetime(2026, 10, 12, 14, 30, tzinfo=KST), 30)]  # 월요일 14시

    result = build_weekly(points, HistoryRoomCode.A2, target, context(now))

    assert result.week_start == date(2026, 10, 12)
    assert result.week_end == date(2026, 10, 18)
    assert [day.date for day in result.days] == [
        date(2026, 10, 12) + timedelta(days=offset) for offset in range(7)
    ]
    monday = result.days[0]
    assert [slot.hour for slot in monday.slots] == list(range(0, 24, 2))
    slot14 = monday.slots[7]  # 14시 구간
    assert (slot14.hour, slot14.percent, slot14.samples, slot14.reason) == (
        14,
        30,
        1,
        None,
    )
    # 목요일부터는 아직 오지 않았다.
    assert result.days[2].slots[-1].reason == WeeklyHistoryReason.FUTURE
    assert result.days[3].summary.reason == WeeklyHistoryReason.FUTURE


def test_weekly_flags_days_outside_retention() -> None:
    target = date(2026, 10, 18)  # 일요일
    now = datetime(2026, 10, 18, 23, 0, tzinfo=KST)
    result = build_weekly(
        [], HistoryRoomCode.A1, target, context(now, retention_days=3)
    )

    # 보관 기간 3일이면 목요일(10/15) 이전은 범위 밖이다.
    assert result.days[0].summary.reason == WeeklyHistoryReason.OUTSIDE_RETENTION  # 월
    assert result.days[4].summary.reason == WeeklyHistoryReason.MISSING  # 금(10/16)


def test_monthly_has_day_axis_and_hour_axis() -> None:
    target = date(2026, 10, 13)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=KST)
    points = [
        point(datetime(2026, 10, 5, 14, 10, tzinfo=KST), 20),
        point(datetime(2026, 10, 5, 15, 40, tzinfo=KST), 40),
    ]

    result = build_monthly(points, HistoryRoomCode.E1, target, context(now))

    assert result.month_start == date(2026, 10, 1)
    assert result.month_end == date(2026, 10, 31)
    assert len(result.days) == 31
    assert len(result.hours) == 24
    day5 = result.days[4]
    assert (day5.date, day5.percent, day5.samples) == (date(2026, 10, 5), 30, 2)
    assert result.hours[14].percent == 20
    assert result.hours[15].percent == 40
    assert result.hours[3].reason == MonthlyHistoryReason.MISSING
    # 20일 이후는 미래다.
    assert result.days[25].reason == MonthlyHistoryReason.FUTURE
    assert (result.summary.percent, result.summary.samples) == (30, 2)


def test_metadata_reports_collection_delay() -> None:
    target = date(2026, 10, 13)
    now = datetime(2026, 10, 13, 12, 0, tzinfo=KST)

    fresh = build_daily(
        [],
        HistoryRoomCode.A1,
        target,
        context(now, last_stored_at=now.astimezone(UTC) - timedelta(minutes=2)),
    )
    assert fresh.collection_delayed is False

    stale = build_daily(
        [],
        HistoryRoomCode.A1,
        target,
        context(now, last_stored_at=now.astimezone(UTC) - timedelta(minutes=20)),
    )
    assert stale.collection_delayed is True

    never = build_daily([], HistoryRoomCode.A1, target, context(now))
    assert never.collection_delayed is True
    assert never.first_date is None
    assert never.interval_seconds == 180


# ---------- DB 없이: 비동기 실행, cache, date 범위 ----------

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=KST)


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def set(self, name: str, value: str, ex: int) -> bool:
        self.values[name] = value
        return True


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"_env_file": None, "postgres_password": "test-password"}
    return Settings(**base, **overrides)


def offline_service(
    monkeypatch: pytest.MonkeyPatch, cache: LiveCache | None = None
) -> HistoryService:
    """DB 조회를 빈 결과로 바꾼 서비스다. 집계와 cache 동작만 본다."""
    service = HistoryService(
        FakeSession,  # type: ignore[arg-type]
        make_settings(),
        clock=lambda: NOW.astimezone(UTC),
        cache=cache,
    )

    async def no_points(*_: object) -> list[ObservationPoint]:
        return []

    async def fixed_context(_: object, now: datetime) -> HistoryContext:
        return context(now, first_date=date(2026, 7, 1), last_stored_at=now)

    monkeypatch.setattr(service, "_fetch", no_points)
    monkeypatch.setattr(service, "_context", fixed_context)
    return service


def spy_on(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
    """집계 함수가 불린 thread 이름을 모은다."""
    threads: list[str] = []
    original = getattr(history_module, name)

    def spy(*args: Any, **kwargs: Any) -> Any:
        threads.append(threading.current_thread().name)
        return original(*args, **kwargs)

    monkeypatch.setattr(history_module, name, spy)
    return threads


async def test_aggregation_runs_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = offline_service(monkeypatch)
    threads = spy_on(monkeypatch, "build_monthly")

    await service.monthly(ReadingroomCode.A1, date(2026, 10, 13))

    assert threads
    assert threads[0] != threading.current_thread().name


async def test_repeated_request_is_served_from_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = offline_service(monkeypatch, LiveCache(MemoryBackend(), "t", 180))
    threads = spy_on(monkeypatch, "build_daily")

    first = await service.daily(ReadingroomCode.A1, date(2026, 10, 13))
    second = await service.daily(ReadingroomCode.A1, date(2026, 10, 13))

    assert len(threads) == 1
    assert second.model_dump(by_alias=True) == first.model_dump(by_alias=True)


async def test_dates_outside_retention_bypass_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = MemoryBackend()
    service = offline_service(monkeypatch, LiveCache(backend, "t", 180))
    threads = spy_on(monkeypatch, "build_daily")

    for _ in range(2):
        await service.daily(ReadingroomCode.A1, date(2000, 1, 1))

    assert len(threads) == 2
    assert backend.values == {}


@pytest.mark.parametrize(
    ("period", "builder", "first_day", "second_day"),
    [
        ("weekly", "build_weekly", date(2026, 10, 12), date(2026, 10, 13)),
        ("monthly", "build_monthly", date(2026, 10, 1), date(2026, 10, 13)),
    ],
)
async def test_period_cache_is_shared_but_echoes_each_requested_date(
    monkeypatch: pytest.MonkeyPatch,
    period: str,
    builder: str,
    first_day: date,
    second_day: date,
) -> None:
    service = offline_service(monkeypatch, LiveCache(MemoryBackend(), "t", 180))
    threads = spy_on(monkeypatch, builder)
    call = getattr(service, period)

    first = await call(ReadingroomCode.A1, first_day)
    second = await call(ReadingroomCode.A1, second_day)

    assert len(threads) == 1
    assert (first.date, second.date) == (first_day, second_day)


@pytest.mark.parametrize("target", [date(1970, 1, 1), date(2100, 12, 31)])
async def test_service_handles_boundary_dates(
    monkeypatch: pytest.MonkeyPatch, target: date
) -> None:
    service = offline_service(monkeypatch)

    for call in (service.daily, service.weekly, service.monthly):
        result = await call(ReadingroomCode.A1, target)
        assert result.date == target


class StubHistory:
    """라우터가 서비스까지 요청을 넘겼는지만 센다."""

    def __init__(self) -> None:
        self.calls = 0

    async def _respond(self, build: Any, room: ReadingroomCode, target: date) -> Any:
        self.calls += 1
        return build([], HistoryRoomCode(room.value), target, context(NOW))

    async def daily(self, room: ReadingroomCode, target: date) -> Any:
        return await self._respond(build_daily, room, target)

    async def weekly(self, room: ReadingroomCode, target: date) -> Any:
        return await self._respond(build_weekly, room, target)

    async def monthly(self, room: ReadingroomCode, target: date) -> Any:
        return await self._respond(build_monthly, room, target)


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
@pytest.mark.parametrize(
    ("value", "status"),
    [
        ("1969-12-31", 422),
        ("1970-01-01", 200),
        ("2100-12-31", 200),
        ("2101-01-01", 422),
    ],
)
async def test_date_query_is_limited_to_1970_through_2100(
    period: str, value: str, status: int
) -> None:
    app = create_app(make_settings(collection_enabled=False))
    stub = StubHistory()
    app.state.history = stub
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/studyroom/api/readingrooms/A1/history/{period}", params={"date": value}
        )

    assert response.status_code == status
    assert stub.calls == (1 if status == 200 else 0)


# ---------- DB 통합: TEST_DATABASE_URL 이 있을 때만 ----------

DB_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(
    DB_URL is None, reason="TEST_DATABASE_URL 이 있어야 history 통합 테스트를 돈다"
)


@pytest.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(str(DB_URL))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    value: async_sessionmaker[AsyncSession] = async_sessionmaker(engine)
    async with value() as session:
        session.add(Readingroom(code="A1", name="1일반열람실"))
        minute = datetime(2026, 10, 13, 5, 0, tzinfo=UTC)  # 한국 14시
        session.add(
            ReadingroomObservation(
                readingroom_code="A1",
                observed_minute=minute,
                observed_at=minute,
                total=100,
                used=45,
                available=55,
                is_open=True,
            )
        )
        session.add(CollectorState(id=1, last_stored_at=minute))
        await session.commit()
    yield value
    await engine.dispose()


@needs_db
async def test_service_daily_reads_seeded_observation(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = Settings(_env_file=None, postgres_password="test-password")
    service = HistoryService(
        factory, settings, clock=lambda: datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    )

    result = await service.daily(ReadingroomCode.A1, date(2026, 10, 13))

    assert (result.hours[14].percent, result.hours[14].samples) == (45, 1)
    assert result.first_date == date(2026, 10, 13)
    assert result.last_stored_at == datetime(2026, 10, 13, 5, 0, tzinfo=UTC)

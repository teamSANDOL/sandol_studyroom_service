"""collector의 적재와 정리 동작을 임시 DB로 검증한다."""

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clients.school import COUNTS_PATH, SchoolClient
from app.models import Base, CollectorState, Readingroom, ReadingroomObservation
from app.services.collector import cleanup_once, collect_once

BASE_URL = "http://school.test"
COUNTS_URL = f"{BASE_URL}{COUNTS_PATH}"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "school_2026-10-13.json").read_text("utf-8")
)
DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    DB_URL is None, reason="TEST_DATABASE_URL 이 있어야 collector 통합 테스트를 돈다"
)
NOW = datetime(2026, 10, 13, 7, 18, 40, tzinfo=UTC)
MINUTE = NOW.replace(second=0, microsecond=0)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(str(DB_URL))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine)
    async with factory() as value:
        for code, name in [
            ("A1", "1일반열람실"),
            ("A2", "2일반열람실"),
            ("E1", "노트북열람실"),
        ]:
            value.add(Readingroom(code=code, name=name))
        await value.commit()
        yield value
    await engine.dispose()


@pytest.fixture
def router() -> AsyncIterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as value:
        yield value


@pytest.fixture
def client() -> SchoolClient:
    return SchoolClient(httpx.AsyncClient(base_url=BASE_URL))


async def test_collect_stores_one_row_per_target_room(
    session: AsyncSession, router: respx.MockRouter, client: SchoolClient
) -> None:
    router.get(COUNTS_URL).respond(json=FIXTURE["counts"])

    assert await collect_once(session, client, NOW) is True

    rows = (
        (
            await session.execute(
                select(ReadingroomObservation).order_by(
                    ReadingroomObservation.readingroom_code
                )
            )
        )
        .scalars()
        .all()
    )
    assert [row.readingroom_code for row in rows] == ["A1", "A2", "E1"]
    a1 = rows[0]
    assert a1.observed_minute == MINUTE
    assert (a1.total, a1.used, a1.available, a1.is_open) == (92, 25, 67, True)

    state = await session.get(CollectorState, 1)
    assert state is not None
    assert state.last_stored_at == MINUTE
    assert state.last_error_code is None


async def test_second_collect_in_same_minute_keeps_first(
    session: AsyncSession, router: respx.MockRouter, client: SchoolClient
) -> None:
    changed = [dict(room) for room in FIXTURE["counts"]]
    a1 = next(r for r in changed if r["ROOM_CODE"] == "A1")
    a1["INUSE_COUNT"], a1["NOTINUSE_COUNT"] = "40", "52"
    router.get(COUNTS_URL).mock(
        side_effect=[
            httpx.Response(200, json=FIXTURE["counts"]),
            httpx.Response(200, json=changed),
        ]
    )

    await collect_once(session, client, NOW)
    await collect_once(session, client, NOW.replace(second=55))

    stored = await session.get(ReadingroomObservation, ("A1", MINUTE))
    assert stored is not None
    assert stored.used == 25  # 첫 관측을 유지한다


async def test_failed_collect_records_error(
    session: AsyncSession, router: respx.MockRouter, client: SchoolClient
) -> None:
    router.get(COUNTS_URL).respond(json={"rooms": []})

    assert await collect_once(session, client, NOW) is False

    count = await session.scalar(
        select(func.count()).select_from(ReadingroomObservation)
    )
    assert count == 0
    state = await session.get(CollectorState, 1)
    assert state is not None
    assert state.last_error_code == "school_response_invalid"


async def _add_observation(session: AsyncSession, minute: datetime) -> None:
    session.add(
        ReadingroomObservation(
            readingroom_code="A1",
            observed_minute=minute,
            observed_at=minute,
            total=92,
            used=10,
            available=82,
            is_open=True,
        )
    )


async def test_cleanup_removes_old_and_runs_once_per_day(
    session: AsyncSession,
) -> None:
    old = MINUTE - timedelta(days=100)
    recent = MINUTE - timedelta(days=10)
    await _add_observation(session, old)
    await _add_observation(session, recent)
    session.add(CollectorState(id=1))
    await session.commit()

    await cleanup_once(session, NOW, retention_days=90)

    remaining = (
        (await session.execute(select(ReadingroomObservation.observed_minute)))
        .scalars()
        .all()
    )
    assert remaining == [recent]
    state = await session.get(CollectorState, 1)
    assert state is not None and state.last_cleanup_date == NOW.date()

    # 같은 날 다시 불러도 추가 삭제가 없다.
    await _add_observation(session, old)
    await session.commit()
    await cleanup_once(session, NOW, retention_days=90)
    count = await session.scalar(
        select(func.count()).select_from(ReadingroomObservation)
    )
    assert count == 2

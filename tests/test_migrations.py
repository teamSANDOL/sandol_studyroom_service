"""migration 이 모델과 맞고 기존 public 테이블을 데이터째 옮기는지 검증한다."""

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.database import run_migrations
from app.studyroom.models import Base as StudyroomBase
from tests.conftest import TEST_DATABASE_URL, reset_database

pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL 이 있어야 migration 테스트를 돈다",
)

# alembic 도입 전 create_all 이 public 에 만들던 테이블이다.
LEGACY_DDL = """
CREATE TABLE public.readingrooms (
    code VARCHAR(2) PRIMARY KEY,
    name VARCHAR(80) NOT NULL
);
CREATE TABLE public.readingroom_observations (
    readingroom_code VARCHAR(2) REFERENCES public.readingrooms (code),
    observed_minute TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    total INTEGER NOT NULL,
    used INTEGER NOT NULL,
    available INTEGER NOT NULL,
    is_open BOOLEAN NOT NULL,
    PRIMARY KEY (readingroom_code, observed_minute)
);
CREATE TABLE public.collector_state (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_stored_at TIMESTAMPTZ,
    last_error_code VARCHAR(64),
    last_cleanup_date DATE,
    last_cleanup_error_code VARCHAR(64)
);
"""


def _diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection, opts={"include_schemas": True, "compare_type": True}
    )
    return list(compare_metadata(context, StudyroomBase.metadata))


async def _table_schemas(engine: AsyncEngine, name: str) -> list[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = :n"
            ),
            {"n": name},
        )
        return sorted(row[0] for row in rows)


@pytest.fixture
async def engine() -> AsyncEngine:
    value = create_async_engine(str(TEST_DATABASE_URL))
    await reset_database(value)
    return value


async def test_fresh_database_matches_models(engine: AsyncEngine) -> None:
    await run_migrations(engine)

    async with engine.connect() as conn:
        diff = await conn.run_sync(_diff)

    assert diff == []
    await engine.dispose()


async def test_legacy_public_tables_move_with_data(engine: AsyncEngine) -> None:
    minute = datetime(2026, 10, 13, 5, 0, tzinfo=UTC)
    async with engine.begin() as conn:
        for statement in LEGACY_DDL.split(";"):
            if statement.strip():
                await conn.execute(text(statement))
        await conn.execute(
            text("INSERT INTO readingrooms VALUES ('A1', '1일반열람실')")
        )
        await conn.execute(
            text(
                "INSERT INTO readingroom_observations "
                "VALUES ('A1', :m, :m, 100, 45, 55, true)"
            ),
            {"m": minute},
        )

    await run_migrations(engine)

    assert await _table_schemas(engine, "readingroom_observations") == ["studyroom"]
    async with engine.connect() as conn:
        used = await conn.scalar(
            text("SELECT used FROM studyroom.readingroom_observations")
        )
    assert used == 45
    await engine.dispose()


async def test_running_twice_is_a_no_op(engine: AsyncEngine) -> None:
    await run_migrations(engine)
    await run_migrations(engine)

    assert await _table_schemas(engine, "readingrooms") == ["studyroom"]
    await engine.dispose()

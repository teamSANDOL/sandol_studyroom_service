"""DB 통합 테스트가 공유하는 fixture 다. TEST_DATABASE_URL 이 있을 때만 쓴다."""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.database import run_migrations

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
DOMAIN_SCHEMAS = ("studyroom", "classroom")


async def reset_database(engine: AsyncEngine) -> None:
    """도메인 스키마와 migration 기록을 지워 빈 DB 로 돌린다."""
    async with engine.begin() as conn:
        for schema in DOMAIN_SCHEMAS:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """빈 DB 에 migration 을 적용한 engine 이다."""
    engine = create_async_engine(str(TEST_DATABASE_URL))
    await reset_database(engine)
    await run_migrations(engine)
    yield engine
    await engine.dispose()

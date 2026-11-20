"""앱 수명 동안 사용할 DB 연결과 스키마 migration 실행 도구다."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_db_engine(url: URL) -> AsyncEngine:
    """설정이 검증한 URL로 비동기 연결 pool을 준비한다."""
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """요청과 collector가 쓸 세션 팩토리를 만든다."""
    return async_sessionmaker(engine, expire_on_commit=False)


def _upgrade(connection: Connection) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # env.py 가 새 연결을 만들지 않고 이 연결을 쓰게 한다.
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def run_migrations(engine: AsyncEngine) -> None:
    """모든 도메인 스키마를 최신 migration 으로 올린다."""
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade)

"""앱 수명 동안 사용할 DB 연결 도구를 생성한다."""

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(url: URL) -> AsyncEngine:
    """설정이 검증한 URL로 비동기 연결 pool을 준비한다."""
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """요청과 collector가 쓸 세션 팩토리를 만든다."""
    return async_sessionmaker(engine, expire_on_commit=False)

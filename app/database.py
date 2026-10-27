"""앱 수명 동안 사용할 DB 연결 도구를 생성한다."""

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_db_engine(url: URL) -> AsyncEngine:
    """설정이 검증한 URL로 비동기 연결 pool을 준비한다."""
    return create_async_engine(url, pool_pre_ping=True)

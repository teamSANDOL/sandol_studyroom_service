"""앱 수명 동안 사용할 DB 연결 도구를 생성한다."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base, Readingroom

# 서비스가 다루는 열람실 기준 정보다. 배포 이력이 없어 migration 없이 여기서 심는다.
SEED_READINGROOMS = (
    ("A1", "1일반열람실"),
    ("A2", "2일반열람실"),
    ("E1", "노트북열람실"),
)


def create_db_engine(url: URL) -> AsyncEngine:
    """설정이 검증한 URL로 비동기 연결 pool을 준비한다."""
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """요청과 collector가 쓸 세션 팩토리를 만든다."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_database(engine: AsyncEngine) -> None:
    """모델 정의로 테이블을 만들고 대상 열람실을 심는다. 이미 있으면 그대로 둔다."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for code, name in SEED_READINGROOMS:
            await conn.execute(
                insert(Readingroom)
                .values(code=code, name=name)
                .on_conflict_do_nothing(index_elements=["code"])
            )

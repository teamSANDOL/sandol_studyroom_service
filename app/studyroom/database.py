"""열람실 테이블을 만들고 기준 정보를 심는다."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.studyroom.models import Base, Readingroom

# 서비스가 다루는 열람실 기준 정보다. 배포 이력이 없어 migration 없이 여기서 심는다.
SEED_READINGROOMS = (
    ("A1", "1일반열람실"),
    ("A2", "2일반열람실"),
    ("E1", "노트북열람실"),
)


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

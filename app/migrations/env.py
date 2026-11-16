"""alembic 이 앱 시작 시와 CLI 에서 공통으로 쓰는 실행 환경이다."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.classroom.models import Base as ClassroomBase
from app.core.config import Settings
from app.studyroom.models import Base as StudyroomBase

# 도메인을 추가하면 그 Base.metadata 를 여기에 더한다.
target_metadata = [StudyroomBase.metadata, ClassroomBase.metadata]


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_cli() -> None:
    engine = create_async_engine(Settings().sqlalchemy_url)
    async with engine.begin() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    asyncio.run(_run_cli())

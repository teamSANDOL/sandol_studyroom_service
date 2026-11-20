"""강의 시간 구간 constraint 가 잘못된 값을 DB 에서 거부하는지 검증한다."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL 이 있어야 DB 테스트를 돈다",
)

INSERT_SLOT = """
INSERT INTO classroom.lecture_slots
    (lecture_id, day, start_minute, end_minute, period_start, period_end)
VALUES (1, 0, 540, 590, :start, :end)
"""


async def test_period_start_after_period_end_is_rejected(
    db_engine: AsyncEngine,
) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO classroom.lectures (id, course_code, division, name) "
                "VALUES (1, 'C1', '01', 'test')"
            )
        )
        await conn.execute(text(INSERT_SLOT), {"start": 2, "end": 3})

    with pytest.raises(IntegrityError, match="ck_lecture_slots_period_range"):
        async with db_engine.begin() as conn:
            await conn.execute(text(INSERT_SLOT), {"start": 3, "end": 2})

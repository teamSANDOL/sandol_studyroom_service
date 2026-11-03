"""주기적으로 열람실 현황을 조회해 DB에 분 단위로 적재한다."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.school import SchoolClient
from app.errors import ServiceError
from app.models import CollectorState, ReadingroomObservation
from app.schemas.readingroom import ReadingroomOperation
from app.services.readingroom_parser import parse_counts

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _ensure_state(session: AsyncSession) -> None:
    """collector_state 단일 행이 없으면 만든다."""
    await session.execute(
        insert(CollectorState)
        .values(id=1)
        .on_conflict_do_nothing(index_elements=["id"])
    )


async def collect_once(
    session: AsyncSession, school: SchoolClient, now: datetime
) -> bool:
    """현황을 한 번 조회해 그 분의 관측으로 적재한다. 성공 여부를 반환한다."""
    minute = now.astimezone(UTC).replace(second=0, microsecond=0)
    await _ensure_state(session)
    await session.execute(
        update(CollectorState).where(CollectorState.id == 1).values(last_attempt_at=now)
    )
    try:
        snapshot = parse_counts(await school.fetch_counts(), now)
    except ServiceError as error:
        logger.warning("collection failed: %s", error.code)
        await session.execute(
            update(CollectorState)
            .where(CollectorState.id == 1)
            .values(last_error_code=error.code)
        )
        await session.commit()
        return False

    rows = [
        {
            "readingroom_code": room.code.value,
            "observed_minute": minute,
            "observed_at": now,
            "total": room.total,
            "used": room.used,
            "available": room.available,
            "is_open": room.operation == ReadingroomOperation.OPEN,
        }
        for room in snapshot.rooms
    ]
    # 같은 분을 다시 수집해도 첫 관측을 유지한다.
    await session.execute(
        insert(ReadingroomObservation)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["readingroom_code", "observed_minute"])
    )
    await session.execute(
        update(CollectorState)
        .where(CollectorState.id == 1)
        .values(last_success_at=now, last_stored_at=minute, last_error_code=None)
    )
    await session.commit()
    return True


async def cleanup_once(
    session: AsyncSession, now: datetime, retention_days: int
) -> None:
    """보관 기간 밖 관측을 지우고 정리 날짜를 기록한다. 하루 한 번만 수행한다."""
    today = now.astimezone(UTC).date()
    state = await session.get(CollectorState, 1)
    if state is not None and state.last_cleanup_date == today:
        return
    cutoff = now.astimezone(UTC) - timedelta(days=retention_days)
    try:
        await session.execute(
            delete(ReadingroomObservation).where(
                ReadingroomObservation.observed_minute < cutoff
            )
        )
        await session.execute(
            update(CollectorState)
            .where(CollectorState.id == 1)
            .values(last_cleanup_date=today, last_cleanup_error_code=None)
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("history cleanup failed")
        await session.execute(
            update(CollectorState)
            .where(CollectorState.id == 1)
            .values(last_cleanup_error_code="cleanup_failed")
        )
        await session.commit()


async def run_collector(
    session_factory: async_sessionmaker[AsyncSession],
    school: SchoolClient,
    interval_minutes: int,
    retention_days: int,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """서비스가 사는 동안 주기적으로 수집한다. 취소될 때까지 멈추지 않는다."""
    interval = interval_minutes * 60
    while True:
        try:
            async with session_factory() as session:
                now = clock()
                if await collect_once(session, school, now):
                    await cleanup_once(session, now, retention_days)
        except asyncio.CancelledError:
            raise
        except Exception:
            # 한 주기의 실패가 수집 루프 전체를 멈추지 않게 한다.
            logger.exception("collection cycle crashed")
        await asyncio.sleep(interval)

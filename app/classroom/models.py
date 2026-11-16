"""건물, 강의실, 강의와 수업 시간 테이블이다."""

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.models import domain_metadata

SCHEMA = "classroom"


class Base(DeclarativeBase):
    """classroom 스키마에 테이블을 두는 모델 기반이다."""

    metadata = domain_metadata(SCHEMA)


class Building(Base):
    """강의실이 있는 건물과 사용자가 부르는 별칭이다."""

    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # 강의실 이름의 앞부분이다. 예: A동, 중앙
    name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, server_default=text("'{}'")
    )


class Classroom(Base):
    """건물 안의 강의실 하나다."""

    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("building_id", "room"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="RESTRICT"), nullable=False
    )
    # 건물명을 뺀 나머지다. 예: 218호, 416-A호
    room: Mapped[str] = mapped_column(String(20), nullable=False)


class Lecture(Base):
    """학수번호와 분반으로 구분하는 강의 하나다."""

    __tablename__ = "lectures"
    __table_args__ = (UniqueConstraint("course_code", "division"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(String(16), nullable=False)
    division: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    professor: Mapped[str | None] = mapped_column(String(50))


class LectureSlot(Base):
    """강의가 한 요일에 한 장소를 쓰는 시간 구간이다."""

    __tablename__ = "lecture_slots"
    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 6", name="day_range"),
        CheckConstraint(
            "0 <= start_minute AND start_minute < end_minute AND end_minute <= 1440",
            name="minute_range",
        ),
        Index("ix_lecture_slots_classroom_id_day", "classroom_id", "day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False
    )
    # 온라인 강좌, 미배정처럼 강의실이 아닌 장소는 NULL 이다.
    classroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT")
    )
    # 0 은 월요일, 6 은 일요일이다.
    day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # 그날 0시부터 지난 분이다.
    start_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    period_start: Mapped[int | None] = mapped_column(SmallInteger)
    period_end: Mapped[int | None] = mapped_column(SmallInteger)

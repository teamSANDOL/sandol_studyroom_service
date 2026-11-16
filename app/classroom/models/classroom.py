"""건물 안의 강의실을 저장하는 모델이다."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.classroom.models.base import Base


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

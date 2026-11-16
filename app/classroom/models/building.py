"""건물과 별칭을 저장하는 모델이다."""

from sqlalchemy import ARRAY, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.classroom.models.base import Base


class Building(Base):
    """강의실이 있는 건물과 사용자가 부르는 별칭이다."""

    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # 강의실 이름의 앞부분이다. 예: A동, 중앙
    name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, server_default=text("'{}'")
    )

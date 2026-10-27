"""열람실 기준 정보를 저장하는 모델이다."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.readingroom_observation import ReadingroomObservation


class Readingroom(Base):
    """서비스에서 사용하는 열람실 기준 정보다."""

    __tablename__ = "readingrooms"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    observations: Mapped[list["ReadingroomObservation"]] = relationship(
        back_populates="readingroom",
        passive_deletes=True,
    )

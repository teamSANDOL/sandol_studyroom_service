"""열람실과 스터디룸 모델의 기반이다."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.core.models import NAMING_CONVENTION


class Base(DeclarativeBase):
    """모델 metadata와 constraint 이름 규칙을 공유한다."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

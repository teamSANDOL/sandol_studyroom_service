"""SQLAlchemy 모델의 공통 기반을 정의한다."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모델 metadata와 constraint 이름 규칙을 공유한다."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
        }
    )

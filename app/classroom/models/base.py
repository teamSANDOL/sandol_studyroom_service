"""강의실 모델의 기반이다."""

from sqlalchemy.orm import DeclarativeBase

from app.core.models import domain_metadata

SCHEMA = "classroom"


class Base(DeclarativeBase):
    """classroom 스키마에 테이블을 두는 모델 기반이다."""

    metadata = domain_metadata(SCHEMA)

"""열람실과 스터디룸 모델의 기반이다."""

from sqlalchemy.orm import DeclarativeBase

from app.core.models import domain_metadata

SCHEMA = "studyroom"


class Base(DeclarativeBase):
    """studyroom 스키마에 테이블을 두는 모델 기반이다."""

    metadata = domain_metadata(SCHEMA)

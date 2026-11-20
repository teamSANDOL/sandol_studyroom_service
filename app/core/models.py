"""도메인 모델이 공유하는 constraint 이름 규칙이다."""

from sqlalchemy import MetaData

# 도메인마다 PostgreSQL 스키마를 따로 쓰므로 Base 도 도메인마다 하나씩 만든다.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}


def domain_metadata(schema: str) -> MetaData:
    """도메인 스키마에 테이블을 두는 metadata 를 만든다."""
    return MetaData(schema=schema, naming_convention=NAMING_CONVENTION)

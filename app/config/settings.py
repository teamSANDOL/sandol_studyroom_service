"""실행 설정을 검증하고 DB 연결 정보를 구성한다."""

from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """환경 변수와 로컬 .env에서 실행 설정을 읽는다."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    api_docs_enabled: bool = False
    # 참이면 개발용 프론트엔드(/studyroom/ 과 static)를 제공한다. 운영에서는 끈다.
    development_frontend_mode: bool = False
    cors_allowed_origins: list[str] = Field(default_factory=list)

    postgres_db: str = Field(default="studyroom_service", min_length=1)
    postgres_user: str = Field(default="studyroom", min_length=1)
    postgres_password: SecretStr | None = None
    postgres_host: str = Field(default="studyroom-db", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    database_url: SecretStr | None = None

    redis_url: SecretStr = SecretStr("redis://studyroom-redis:6379/0")
    redis_key_prefix: str = Field(default="sandol:studyroom:v1", min_length=1)
    live_cache_ttl_seconds: int = Field(default=20, gt=0)
    guide_cache_ttl_seconds: int = Field(default=300, gt=0)

    school_base_url: AnyHttpUrl = AnyHttpUrl("http://smart.tukorea.ac.kr")
    library_base_url: AnyHttpUrl = AnyHttpUrl("https://library.tukorea.ac.kr")
    school_request_timeout_seconds: float = Field(default=3, gt=0)
    guide_request_timeout_seconds: float = Field(default=12, gt=0)
    # 참이면 lifespan 에서 주기 수집 태스크를 띄운다. DB 없이 띄울 때는 끈다.
    collection_enabled: bool = True
    # 학교 좌석 시스템을 수집해 DB에 적재하는 주기다.
    collection_interval_minutes: int = Field(default=3, gt=0)
    history_retention_days: int = Field(default=90, gt=0)
    collection_stale_after_minutes: int = Field(default=7, gt=0)

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url_is_unset(cls, value: object) -> object:
        """빈 URL은 POSTGRES 설정으로 구성한다."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        """잘못된 연결과 수집 주기 설정을 시작 전에 거부한다."""
        _ = self.sqlalchemy_url
        redis = urlsplit(self.redis_url.get_secret_value())
        if redis.scheme not in {"redis", "rediss"} or not redis.hostname:
            raise ValueError("REDIS_URL must use redis:// or rediss:// with a host")
        if self.collection_stale_after_minutes <= self.collection_interval_minutes:
            raise ValueError(
                "COLLECTION_STALE_AFTER_MINUTES must exceed COLLECTION_INTERVAL_MINUTES"
            )
        return self

    @property
    def sqlalchemy_url(self) -> URL:
        """명시한 URL을 우선하며 비밀번호를 URL 객체로 전달한다."""
        if self.database_url is not None:
            try:
                url = make_url(self.database_url.get_secret_value())
            except (ArgumentError, ValueError):
                raise ValueError("DATABASE_URL is not a valid PostgreSQL URL") from None
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+asyncpg")
            if url.drivername != "postgresql+asyncpg":
                raise ValueError("DATABASE_URL must use the PostgreSQL asyncpg driver")
            return url

        if (
            self.postgres_password is None
            or not self.postgres_password.get_secret_value()
        ):
            raise ValueError("POSTGRES_PASSWORD is required when DATABASE_URL is unset")
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

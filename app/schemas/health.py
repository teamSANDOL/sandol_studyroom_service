"""서비스 상태 확인 API schema다."""

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import APISchema, UTCDateTime


class HealthResponse(APISchema):
    """프로세스 생존 확인 응답이다."""

    status: Literal["ok"]


class ReadinessStatus(str, Enum):
    """서비스 준비 상태의 요약값이다."""

    OK = "ok"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


class DependencyStatus(str, Enum):
    """DB 또는 Redis의 연결 상태다."""

    OK = "ok"
    UNAVAILABLE = "unavailable"


class CollectorStatus(str, Enum):
    """collector의 관측 상태다."""

    OK = "ok"
    DELAYED = "delayed"
    UNKNOWN = "unknown"


class HealthReadyResponse(APISchema):
    """DB, Redis, collector의 준비 상태다."""

    status: ReadinessStatus
    database: DependencyStatus
    redis: DependencyStatus
    collector: CollectorStatus
    last_stored_at: UTCDateTime | None = Field(alias="lastStoredAt")

    @model_validator(mode="after")
    def require_consistent_readiness(self) -> "HealthReadyResponse":
        """요약 상태가 dependency와 collector 상태에 맞는지 확인한다."""
        if self.database is DependencyStatus.UNAVAILABLE:
            if self.status is not ReadinessStatus.NOT_READY:
                raise ValueError("database unavailability requires not_ready")
            if (
                self.collector is not CollectorStatus.UNKNOWN
                or self.last_stored_at is not None
            ):
                raise ValueError("collector state must be unknown when DB is unavailable")
            return self

        if self.status is ReadinessStatus.NOT_READY:
            raise ValueError("not_ready requires an unavailable database or schema")
        degraded_condition = (
            self.redis is DependencyStatus.UNAVAILABLE
            or self.collector is CollectorStatus.DELAYED
        )
        if degraded_condition != (self.status is ReadinessStatus.DEGRADED):
            raise ValueError("degraded must match Redis failure or collector delay")
        return self

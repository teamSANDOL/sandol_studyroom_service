"""실행 설정과 API 시작 동작을 검증한다."""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config.settings import Settings

    for name in tuple(os.environ):
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)


def test_component_database_url_preserves_password() -> None:
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        database_url=None,
        postgres_password="p@ss:/?#%word",
        postgres_host="studyroom-db",
        postgres_db="studyroom_service",
    )

    url = settings.sqlalchemy_url
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "studyroom-db"
    assert url.database == "studyroom_service"
    assert url.password == "p@ss:/?#%word"


def test_explicit_database_url_takes_precedence() -> None:
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        database_url="postgresql://external:password@db.example:5433/external_db",
        postgres_host="ignored-db",
        postgres_db="ignored_db",
    )

    url = settings.sqlalchemy_url
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "db.example"
    assert url.port == 5433
    assert url.database == "external_db"


def test_missing_database_password_is_rejected() -> None:
    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        Settings(_env_file=None, database_url=None, postgres_password=None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("live_cache_ttl_seconds", 0),
        ("collection_interval_seconds", 0),
        ("school_request_timeout_seconds", -1),
        ("postgres_port", 65536),
    ],
)
def test_invalid_runtime_limits_are_rejected(field: str, value: int) -> None:
    from app.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_password="test-password", **{field: value})


def test_collection_delay_must_exceed_interval() -> None:
    from app.config.settings import Settings

    with pytest.raises(ValidationError, match="COLLECTION_STALE_AFTER_SECONDS"):
        Settings(
            _env_file=None,
            postgres_password="test-password",
            collection_interval_seconds=60,
            collection_stale_after_seconds=60,
        )


async def test_health_does_not_require_dependency_connections() -> None:
    from app.config.settings import Settings
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        postgres_host="unreachable.invalid",
        redis_url="redis://unreachable.invalid:6379/0",
        api_docs_enabled=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/studyroom/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert (await client.get("/studyroom/openapi.json")).status_code == 404
        assert (await client.get("/studyroom/docs")).status_code == 404


async def test_api_docs_can_be_enabled() -> None:
    from app.config.settings import Settings
    from app.main import create_app

    settings = Settings(
        _env_file=None, postgres_password="test-password", api_docs_enabled=True
    )
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        assert (await client.get("/studyroom/openapi.json")).status_code == 200
        assert (await client.get("/studyroom/docs")).status_code == 200


async def test_cors_accepts_only_the_configured_frontend() -> None:
    from app.config.settings import Settings
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        cors_allowed_origins=["http://localhost:3080"],
    )
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        headers = {
            "Origin": "http://localhost:3080",
            "Access-Control-Request-Method": "GET",
        }
        response = await client.options("/studyroom/health", headers=headers)
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3080"
        )

        headers["Origin"] = "https://other.example"
        response = await client.options("/studyroom/health", headers=headers)
        assert "access-control-allow-origin" not in response.headers

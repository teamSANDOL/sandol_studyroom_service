"""강의실 API 가 /classroom 아래에 선언되고 구현 전에는 501 을 내는지 검증한다."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

ENDPOINTS = [
    "/classroom/api/classrooms/available/time",
    "/classroom/api/classrooms/available/periods",
    "/classroom/api/classrooms",
    "/classroom/api/classrooms/timetable",
]


@pytest.fixture
def app() -> FastAPI:
    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        postgres_host="unreachable.invalid",
        redis_url="redis://unreachable.invalid:6379/0",
        collection_enabled=False,
        api_docs_enabled=True,
    )
    return create_app(settings)


@pytest.mark.parametrize("url", ENDPOINTS)
async def test_declared_endpoint_returns_501_until_implemented(
    app: FastAPI, url: str
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(url)

    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"


def test_classroom_routes_are_not_under_studyroom(app: FastAPI) -> None:
    paths = set(app.openapi()["paths"])

    assert {p for p in paths if "classrooms" in p} == set(ENDPOINTS)

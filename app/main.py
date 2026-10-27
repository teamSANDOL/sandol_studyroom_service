"""FastAPI 프로세스의 기초 진입점이다."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.clients.school import SchoolClient, create_school_http
from app.config.settings import Settings
from app.errors import ServiceError
from app.routers.readingroom import router as readingroom_router
from app.routers.web import router as web_router
from app.services.live_cache import LiveCache
from app.services.readingroom import ReadingroomService

# gateway 가 경로를 그대로 넘기므로 서비스가 prefix 를 직접 가진다.
PATH_PREFIX = "/studyroom"


async def handle_service_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ServiceError)
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.message, "code": error.code},
        headers={"Cache-Control": "no-store"},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """검증한 설정으로 API를 생성한다."""
    config = settings if settings is not None else Settings()
    logging.basicConfig(level=config.log_level)

    # client는 연결을 지연하므로 여기서 만들어도 외부 연결이 생기지 않는다.
    school_http = create_school_http(
        str(config.school_base_url), config.school_request_timeout_seconds
    )
    redis = Redis.from_url(config.redis_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await school_http.aclose()
        await redis.aclose()

    app = FastAPI(
        title="Sandol Studyroom Service",
        version="0.1.0",
        debug=config.debug,
        docs_url=f"{PATH_PREFIX}/docs" if config.api_docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{PATH_PREFIX}/openapi.json" if config.api_docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.readingrooms = ReadingroomService(
        SchoolClient(school_http),
        LiveCache(redis, config.redis_key_prefix, config.live_cache_ttl_seconds),
    )
    app.add_exception_handler(ServiceError, handle_service_error)
    app.mount(
        f"{PATH_PREFIX}/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )
    app.include_router(web_router, prefix=PATH_PREFIX)
    app.include_router(readingroom_router, prefix=PATH_PREFIX)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @app.get(f"{PATH_PREFIX}/health", tags=["health"])
    async def health() -> dict[str, str]:
        """외부 연결 없이 프로세스 생존을 반환한다."""
        return {"status": "ok"}

    return app

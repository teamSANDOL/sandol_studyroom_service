"""FastAPI 프로세스의 기초 진입점이다."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.clients.school import SchoolClient, create_school_http
from app.config.settings import Settings
from app.database import create_db_engine, create_session_factory, init_database
from app.errors import ServiceError
from app.routers.history import router as history_router
from app.routers.readingroom import router as readingroom_router
from app.routers.web import router as web_router
from app.services.collector import run_collector
from app.services.history import HistoryService
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
    school_client = SchoolClient(school_http)
    redis = Redis.from_url(config.redis_url.get_secret_value())
    # DB 연결은 수집을 켠 경우에만 만든다. 통계 API 도 이 연결에 의존한다.
    engine = (
        create_db_engine(config.sqlalchemy_url) if config.collection_enabled else None
    )
    session_factory = create_session_factory(engine) if engine is not None else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if engine is not None:
            await init_database(engine)
        if session_factory is not None:
            task = asyncio.create_task(
                run_collector(
                    session_factory,
                    school_client,
                    config.collection_interval_minutes,
                    config.history_retention_days,
                )
            )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await school_http.aclose()
            await redis.aclose()
            if engine is not None:
                await engine.dispose()

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
        school_client,
        LiveCache(redis, config.redis_key_prefix, config.live_cache_ttl_seconds),
    )
    # 응답 cache 수명은 수집 주기와 같다. 새 관측이 들어오기 전에는 답이 바뀌지 않는다.
    history_cache = LiveCache(
        redis,
        f"{config.redis_key_prefix}:history",
        config.collection_interval_minutes * 60,
    )
    app.state.history = (
        HistoryService(session_factory, config, cache=history_cache)
        if session_factory is not None
        else None
    )
    app.add_exception_handler(ServiceError, handle_service_error)
    # 개발용 프론트엔드는 모드가 켜진 경우에만 등록한다. 꺼지면 경로가 없어 404다.
    if config.development_frontend_mode:
        app.mount(
            f"{PATH_PREFIX}/static",
            StaticFiles(directory=Path(__file__).resolve().parent / "static"),
            name="static",
        )
        app.include_router(web_router, prefix=PATH_PREFIX)
    app.include_router(readingroom_router, prefix=PATH_PREFIX)
    app.include_router(history_router, prefix=PATH_PREFIX)
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

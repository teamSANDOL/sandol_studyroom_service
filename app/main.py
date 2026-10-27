"""FastAPI 프로세스의 기초 진입점이다."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import Settings
from app.routers.web import router as web_router

# gateway 가 경로를 그대로 넘기므로 서비스가 prefix 를 직접 가진다.
PATH_PREFIX = "/studyroom"


def create_app(settings: Settings | None = None) -> FastAPI:
    """검증한 설정으로 API를 생성한다."""
    config = settings if settings is not None else Settings()
    logging.basicConfig(level=config.log_level)
    app = FastAPI(
        title="Sandol Studyroom Service",
        version="0.1.0",
        debug=config.debug,
        docs_url=f"{PATH_PREFIX}/docs" if config.api_docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{PATH_PREFIX}/openapi.json" if config.api_docs_enabled else None,
    )
    app.state.settings = config
    app.mount(
        f"{PATH_PREFIX}/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )
    app.include_router(web_router, prefix=PATH_PREFIX)
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

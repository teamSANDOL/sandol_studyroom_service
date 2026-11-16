"""도메인 오류의 기반 클래스와 JSON 응답 변환이다."""

from fastapi import Request
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """HTTP 상태와 기계 판독 코드를 가진 오류다."""

    status_code = 500
    code = "internal_error"
    message = "요청을 처리하지 못했다."


async def handle_service_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ServiceError)
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.message, "code": error.code},
        headers={"Cache-Control": "no-store"},
    )

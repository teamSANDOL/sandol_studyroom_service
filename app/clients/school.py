"""학교 좌석 시스템의 공개 조회 endpoint를 호출한다."""

import logging

import httpx

from app.errors import SchoolResponseError, SchoolUnavailableError

logger = logging.getLogger(__name__)

COUNTS_PATH = "/library2014/Library_Seat_Count.php"
SEATS_PATH = "/library2014/getSeatInfoSql.php"


def create_school_http(base_url: str, timeout_seconds: float) -> httpx.AsyncClient:
    """공식 페이지와 같은 Referer로 요청하는 HTTP client를 만든다."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; sandol-studyroom-service)",
            "Referer": f"{base_url.rstrip('/')}/lib/index.html",
        },
    )


class SchoolClient:
    """원문 JSON 배열을 그대로 돌려준다. 해석은 parser가 맡는다."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_counts(self) -> list[object]:
        return await self._get_list(COUNTS_PATH, {"test": "N"})

    async def fetch_seats(self, room_code: str) -> list[object]:
        return await self._get_list(SEATS_PATH, {"test": "N", "room_code": room_code})

    async def _get_list(self, path: str, params: dict[str, str]) -> list[object]:
        # 좌석 응답에 이용자 개인정보가 있으므로 본문은 로그에 남기지 않는다.
        try:
            response = await self._http.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning("school request failed: %s %s", path, type(error).__name__)
            raise SchoolUnavailableError from None
        try:
            payload = response.json()
        except ValueError:
            logger.warning("school response is not JSON: %s", path)
            raise SchoolResponseError from None
        if not isinstance(payload, list):
            logger.warning("school response is not a list: %s", path)
            raise SchoolResponseError
        return payload

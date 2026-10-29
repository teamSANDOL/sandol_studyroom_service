"""열람실 현황 API와 학교 응답 해석을 검증한다."""

import copy
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.clients.school import COUNTS_PATH, SEATS_PATH, SchoolClient
from app.config.settings import Settings
from app.main import create_app
from app.schemas.readingroom import ReadingroomCode, ReadingroomOperation
from app.services.live_cache import LiveCache
from app.services.readingroom import ReadingroomService
from app.services.readingroom_parser import decide_operation, parse_policy, parse_seats

BASE_URL = "http://school.test"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "school_2026-10-13.json").read_text("utf-8")
)
# fixture를 수집한 시각이다. 한국 시각 화요일 16:18이다.
OBSERVED_AT = datetime(2026, 10, 13, 7, 18, 32, tzinfo=UTC)


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def set(self, name: str, value: str, ex: int) -> bool:
        self.values[name] = value
        return True


class BrokenBackend:
    async def get(self, name: str) -> str | None:
        raise RedisConnectionError("down")

    async def set(self, name: str, value: str, ex: int) -> bool:
        raise RedisConnectionError("down")


def mock_school(
    router: respx.MockRouter,
    counts: Any = None,
    seats: dict[str, Any] | None = None,
) -> tuple[respx.Route, respx.Route]:
    counts_route = router.get(f"{BASE_URL}{COUNTS_PATH}").respond(
        json=FIXTURE["counts"] if counts is None else counts,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
    by_room = FIXTURE["seats"] if seats is None else seats
    seats_route = router.get(f"{BASE_URL}{SEATS_PATH}").mock(
        side_effect=lambda request: httpx.Response(
            200, json=by_room[request.url.params["room_code"]]
        )
    )
    return counts_route, seats_route


def make_client(backend: Any = None) -> AsyncClient:
    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        redis_url="redis://unreachable.invalid:6379/0",
    )
    app = create_app(settings)
    app.state.readingrooms = ReadingroomService(
        SchoolClient(httpx.AsyncClient(base_url=BASE_URL)),
        LiveCache(backend or MemoryBackend(), "test", 20),
        clock=lambda: OBSERVED_AT,
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with make_client() as value:
        yield value


@pytest.fixture
def school() -> AsyncIterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


async def test_list_returns_counts_for_target_rooms(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    mock_school(school)

    body = (await client.get("/studyroom/api/readingrooms")).json()

    assert body["updatedAt"] == "2026-10-13T07:18:32Z"
    assert [room["code"] for room in body["rooms"]] == ["A1", "A2", "E1"]
    assert body["rooms"][0] == {
        "code": "A1",
        "name": "1일반열람실",
        "total": 92,
        "used": 25,
        "available": 67,
        "operation": "open",
    }


async def test_detail_lists_seats_ending_within_30_minutes(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    mock_school(school)
    expected = sorted(
        (int(seat["SEAT_TIME_GAP"]), int(seat["SEAT_CODE"]))
        for seat in FIXTURE["seats"]["E1"]
        if seat["SEAT_STATUS"] == "U" and int(seat["SEAT_TIME_GAP"]) <= 30
    )

    response = await client.get("/studyroom/api/readingrooms/e1")

    body = response.json()
    assert response.status_code == 200
    assert body["room"]["code"] == "E1"
    assert body["room"]["policy"]["notebook"] is True
    assert body["endingSoon"]["withinMinutes"] == 30
    ending = [
        (seat["remainingMinutes"], int(seat["number"]))
        for seat in body["endingSoon"]["seats"]
    ]
    assert ending == expected


async def test_seat_returns_remaining_and_estimated_end(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    mock_school(school)

    body = (await client.get("/studyroom/api/readingrooms/A1/seats/003")).json()

    assert body["roomCode"] == "A1"
    assert body["seat"] == {
        "number": "3",
        "name": "A1-003",
        "status": "occupied",
        "sourceStatus": "U",
        "remainingMinutes": 187,
        "estimatedEndAt": (OBSERVED_AT + timedelta(minutes=187))
        .isoformat()
        .replace("+00:00", "Z"),
    }
    available = (await client.get("/studyroom/api/readingrooms/A1/seats/1")).json()
    assert available["seat"]["status"] == "available"
    assert available["seat"]["remainingMinutes"] is None


async def test_seats_lists_every_seat_in_number_order(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    mock_school(school)

    body = (await client.get("/studyroom/api/readingrooms/A2/seats")).json()

    numbers = [int(seat["number"]) for seat in body["seats"]]
    assert numbers == list(range(1, 61))


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/studyroom/api/readingrooms/C1", 404, "readingroom_not_found"),
        ("/studyroom/api/readingrooms/A1/seats/999", 404, "seat_not_found"),
    ],
)
async def test_unknown_room_or_seat_is_404(
    client: AsyncClient, school: respx.MockRouter, path: str, status: int, code: str
) -> None:
    mock_school(school)

    response = await client.get(path)

    assert response.status_code == status
    assert response.json()["code"] == code


async def test_invalid_seat_number_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/studyroom/api/readingrooms/A1/seats/abc")
    assert response.status_code == 422


async def test_personal_fields_never_reach_the_response(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    seats = copy.deepcopy(FIXTURE["seats"])
    for seat in seats["A1"]:
        seat.update(SEAT_USER_NAME="홍길동", SEAT_USER_SNO="2026123456")
    mock_school(school, seats=seats)

    for path in ("A1", "A1/seats", "A1/seats/3"):
        text = (await client.get(f"/studyroom/api/readingrooms/{path}")).text
        assert "홍길동" not in text
        assert "2026123456" not in text


async def test_cache_reuses_school_response(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    counts_route, seats_route = mock_school(school)

    for _ in range(3):
        assert (await client.get("/studyroom/api/readingrooms")).status_code == 200
        assert (await client.get("/studyroom/api/readingrooms/A1")).status_code == 200

    assert counts_route.call_count == 1
    assert seats_route.call_count == 1


async def test_redis_failure_falls_back_to_school(school: respx.MockRouter) -> None:
    counts_route, _ = mock_school(school)

    async with make_client(BrokenBackend()) as client:
        assert (await client.get("/studyroom/api/readingrooms")).status_code == 200
        assert (await client.get("/studyroom/api/readingrooms")).status_code == 200

    assert counts_route.call_count == 2


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(500), "school_unavailable"),
        (httpx.ConnectTimeout("timeout"), "school_unavailable"),
        (httpx.Response(200, text="<html>점검 중</html>"), "school_response_invalid"),
        (httpx.Response(200, json={"rooms": []}), "school_response_invalid"),
    ],
)
async def test_school_failures_return_502(
    client: AsyncClient,
    school: respx.MockRouter,
    response: httpx.Response | Exception,
    code: str,
) -> None:
    route = school.get(f"{BASE_URL}{COUNTS_PATH}")
    if isinstance(response, Exception):
        route.mock(side_effect=response)
    else:
        route.mock(return_value=response)

    result = await client.get("/studyroom/api/readingrooms")

    assert result.status_code == 502
    assert result.json()["code"] == code


@pytest.mark.parametrize(
    "broken",
    [
        {"TOTAL_COUNT": "많음"},
        {"START_TIME": "25:00"},
        {"INUSE_COUNT": "30"},
    ],
)
async def test_invalid_counts_return_502(
    client: AsyncClient, school: respx.MockRouter, broken: dict[str, str]
) -> None:
    counts = copy.deepcopy(FIXTURE["counts"])
    next(room for room in counts if room["ROOM_CODE"] == "A1").update(broken)
    mock_school(school, counts=counts)

    result = await client.get("/studyroom/api/readingrooms")

    assert result.json()["code"] == "school_response_invalid"


async def test_missing_target_room_returns_502(
    client: AsyncClient, school: respx.MockRouter
) -> None:
    counts = [room for room in FIXTURE["counts"] if room["ROOM_CODE"] != "E1"]
    mock_school(school, counts=counts)

    result = await client.get("/studyroom/api/readingrooms")

    assert result.json()["code"] == "school_response_invalid"


def room(**changes: str) -> dict[str, Any]:
    raw = copy.deepcopy(
        next(item for item in FIXTURE["counts"] if item["ROOM_CODE"] == "C1")
    )
    raw.update(changes)
    return raw


def kst(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 13, hour, minute, tzinfo=UTC) - timedelta(hours=9)


@pytest.mark.parametrize(
    ("changes", "now", "expected"),
    [
        ({}, kst(9, 30), ReadingroomOperation.OPEN),
        ({}, kst(22, 1), ReadingroomOperation.OUTSIDE_HOURS),
        ({"USE_YN": "N"}, kst(12), ReadingroomOperation.DISABLED),
        ({"TODAY_WEEKEND_YN": "Y"}, kst(12), ReadingroomOperation.CLOSED),
        ({"TODAY_HOLIDAY_YN": "Y"}, kst(12), ReadingroomOperation.CLOSED),
        ({"START_TIME": "2200", "END_TIME": "0600"}, kst(1), ReadingroomOperation.OPEN),
        (
            {"START_TIME": "2200", "END_TIME": "0600"},
            kst(12),
            ReadingroomOperation.OUTSIDE_HOURS,
        ),
    ],
)
def test_operation_follows_school_policy(
    changes: dict[str, str], now: datetime, expected: ReadingroomOperation
) -> None:
    assert decide_operation(parse_policy(room(**changes)), now) == expected


def test_weekend_policy_uses_weekend_hours() -> None:
    policy = parse_policy(
        room(TODAY_WEEKEND_YN="Y", WEEKEND_YN="Y", WEEKEND_START="10:00")
    )
    assert (policy.kind.value, policy.start, policy.allowed) == (
        "weekend",
        "10:00",
        True,
    )


def test_unknown_seat_status_has_no_remaining_time() -> None:
    raw = dict(FIXTURE["seats"]["A1"][2], SEAT_STATUS="X")

    seat = parse_seats([raw], ReadingroomCode.A1, OBSERVED_AT)[0]

    assert (seat.status.value, seat.remaining_minutes) == ("unknown", None)

# API 문서

모든 경로는 `/studyroom` 아래에 있다. 통합 환경에서는 gateway가 같은 경로를 서비스로 넘긴다. `API_DOCS_ENABLED=true`이면 `/studyroom/docs`에서 OpenAPI 화면을 볼 수 있다.

시각은 모두 UTC ISO 8601(`2026-10-13T07:18:32Z`)이다. 운영시간(`start`, `end`)만 한국 시각 `HH:MM`이다. 좌석 값의 근거와 해석 범위는 [수집 정보](studyroom-info.md)에 있다.

## 공통

### 열람실 코드

| 코드 | 이름 |
|---|---|
| A1 | 1일반열람실 |
| A2 | 2일반열람실 |
| E1 | 노트북열람실 |

경로의 코드는 대소문자를 구분하지 않는다. 다른 코드는 404 `readingroom_not_found`다.

### cache

서비스는 학교 응답을 Redis에 `LIVE_CACHE_TTL_SECONDS`(기본 20초) 동안 보관한다. 같은 시간 안의 요청은 같은 `updatedAt`을 받는다. 집계(`updatedAt`)와 좌석 목록(`endingSoon.updatedAt`, 좌석 API의 `updatedAt`)은 따로 조회하므로 시각과 수치가 조금 다를 수 있다. Redis에 연결하지 못해도 학교에 직접 요청해 응답한다.

### 오류 응답

```json
{ "error": "학교 좌석 시스템에 연결하지 못했다.", "code": "school_unavailable" }
```

| HTTP | code | 상황 |
|---|---|---|
| 404 | `readingroom_not_found` | 지원하지 않는 열람실 코드 |
| 404 | `seat_not_found` | 열람실에 없는 좌석 번호 |
| 422 | (FastAPI 기본 형식) | 좌석 번호가 1자리부터 4자리 숫자가 아니다 |
| 502 | `school_unavailable` | 학교 서버 연결 실패, timeout, HTTP 오류 |
| 502 | `school_response_invalid` | 학교 응답이 JSON이 아니거나 필드가 빠졌거나 집계가 맞지 않는다 |

### 값 정의

`operation`은 조회 시각 기준 운영 상태다.

| 값 | 뜻 |
|---|---|
| `open` | 운영 중 |
| `outside_hours` | 오늘 운영하지만 지금은 운영시간 밖 |
| `closed` | 오늘(주말 또는 휴일) 운영하지 않는다 |
| `disabled` | 학교가 공간 사용을 껐다 |

`status`는 좌석 상태다. `occupied`(원문 U), `available`(원문 D), `unknown`(그 밖의 값)이다. `sourceStatus`는 원문 값이다.

`remainingMinutes`는 사용 중 좌석의 남은 이용 시간(분)이다. 다른 상태면 `null`이다. `estimatedEndAt`은 좌석 목록을 조회한 시각에 `remainingMinutes`를 더한 추정 시각이다. 연장이나 조기 반납이 있으면 달라진다.

## GET /studyroom/api/readingrooms

열람실별 전체, 사용, 여유 좌석 수와 운영 상태를 반환한다. `rooms`는 항상 A1, A2, E1 순서다.

```json
{
  "updatedAt": "2026-10-13T07:18:32Z",
  "rooms": [
    { "code": "A1", "name": "1일반열람실", "total": 92, "used": 25, "available": 67, "operation": "open" },
    { "code": "A2", "name": "2일반열람실", "total": 60, "used": 20, "available": 40, "operation": "open" },
    { "code": "E1", "name": "노트북열람실", "total": 83, "used": 49, "available": 34, "operation": "open" }
  ]
}
```

## GET /studyroom/api/readingrooms/{code}

열람실 정보, 오늘 적용되는 운영 정책, 30분 안에 이용이 끝나는 좌석을 반환한다. `endingSoon.seats`는 남은 시간이 짧은 순서다. 남은 시간 0분도 아직 사용 중이므로 포함한다.

```json
{
  "updatedAt": "2026-10-13T07:18:32Z",
  "room": {
    "code": "E1", "name": "노트북열람실", "total": 83, "used": 49, "available": 34, "operation": "open",
    "policy": {
      "enabled": true, "allowed": true, "start": "06:30", "end": "23:00", "kind": "weekday",
      "weekday": { "start": "06:30", "end": "23:00" },
      "weekend": { "enabled": true, "start": "06:30", "end": "23:00" },
      "holiday": { "enabled": true, "start": "06:30", "end": "23:00" },
      "notebook": true, "hours": 4, "extend": true, "gate": true, "effectiveDate": "2026-06-01"
    }
  },
  "endingSoon": {
    "withinMinutes": 30,
    "updatedAt": "2026-10-13T07:18:32Z",
    "seats": [
      { "number": "82", "name": "E1-082", "status": "occupied", "sourceStatus": "U", "remainingMinutes": 5, "estimatedEndAt": "2026-10-13T07:23:32Z" },
      { "number": "83", "name": "E1-083", "status": "occupied", "sourceStatus": "U", "remainingMinutes": 6, "estimatedEndAt": "2026-10-13T07:24:32Z" },
      { "number": "24", "name": "E1-024", "status": "occupied", "sourceStatus": "U", "remainingMinutes": 16, "estimatedEndAt": "2026-10-13T07:34:32Z" }
    ]
  }
}
```

`policy`의 `start`, `end`, `kind`, `allowed`는 오늘 적용되는 값이다. `kind`는 `weekday`, `weekend`, `holiday` 중 하나다. `hours`는 1회 배정 시간(시간), `notebook`은 노트북 허용 여부, `extend`는 연장 가능 여부, `gate`는 출입 연동 여부다.

## GET /studyroom/api/readingrooms/{code}/seats

열람실의 전체 좌석을 좌석 번호 순서로 반환한다.

```json
{
  "roomCode": "A1",
  "updatedAt": "2026-10-13T07:18:32Z",
  "seats": [
    { "number": "1", "name": "A1-001", "status": "available", "sourceStatus": "D", "remainingMinutes": null, "estimatedEndAt": null },
    { "number": "3", "name": "A1-003", "status": "occupied", "sourceStatus": "U", "remainingMinutes": 187, "estimatedEndAt": "2026-10-13T10:25:32Z" }
  ]
}
```

## GET /studyroom/api/readingrooms/{code}/seats/{number}

좌석 하나의 상태와 남은 시간을 반환한다. `number`는 1자리부터 4자리 숫자다. 앞자리 0은 무시하므로 `3`과 `003`은 같은 좌석이다.

```json
{
  "roomCode": "A1",
  "updatedAt": "2026-10-13T07:18:32Z",
  "seat": { "number": "3", "name": "A1-003", "status": "occupied", "sourceStatus": "U", "remainingMinutes": 187, "estimatedEndAt": "2026-10-13T10:25:32Z" }
}
```

## GET /studyroom/health

외부 연결 없이 프로세스 생존만 확인한다. 응답은 `{"status": "ok"}`다.

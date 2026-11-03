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
| 503 | `history_unavailable` | 수집 또는 DB 연결이 꺼져 혼잡도 이력을 줄 수 없다 |

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

## 혼잡도 이력

수집한 관측을 일간, 주간, 월간으로 집계한다. 세 경로 모두 공통 메타데이터와 요약(`summary`)을 가진다. 수집이나 DB 연결이 꺼져 있으면 503 `history_unavailable`이다.

시간 구간은 한국 시각 기준이다. `date` 질의는 `YYYY-MM-DD`이며, 생략하면 한국 시각 오늘이다.

### 공통 필드

| 필드 | 뜻 |
|---|---|
| `firstDate` | 가장 이른 관측 날짜. 없으면 `null` |
| `intervalSeconds` | 수집 주기(초) |
| `retentionDays` | 보관 기간(일) |
| `lastStoredAt` | 마지막 적재 시각(UTC). 없으면 `null` |
| `collectionError` | 마지막 수집 오류 코드. 없으면 `null` |
| `collectionDelayed` | 마지막 적재가 지연 기준보다 오래됐으면 `true` |
| `updatedAt` | 응답 생성 시각(UTC) |

각 구간은 `{ "percent": 0~100 또는 null, "samples": 표본 수, "reason": 사유 또는 null, "isCollected": true 또는 false }`이다. `percent`가 있으면 `reason`은 `null`이고 `samples`는 1 이상이다. 사유가 있으면 `percent`는 `null`, `samples`는 0이다.

`isCollected`는 그 구간에 관측이 있었는지다. 휴실이라 사용률을 못 구한 경우도 관측 자체는 있었으므로 `true`다. 그래서 `percent`가 `0`인 진짜 빈 열람실과, 관측이 아예 없는 구간을 이 값으로 가른다.

| `reason` | `isCollected` | 상황 |
|---|---|---|
| `null` | `true` | 개실 상태 관측이 있어 사용률을 구했다(0% 포함) |
| `closed` | `true` | 관측은 있으나 모두 휴실 상태다 |
| `missing` | `false` | 보관 범위 안인데 관측이 없다 |
| `future` | `false` | 아직 오지 않은 구간이다 |
| `outside_retention` | `false` | 보관 기간 밖이거나 수집 시작 이전이다(주간, 월간만) |

`percent`는 개실 상태 관측의 사용률(`used / total`) 평균을 반올림한 값이다.

## GET /studyroom/api/readingrooms/{code}/history/daily

기준 날짜의 요약과 24개 시간별(`hours`, 0시부터 23시) 사용률을 반환한다. `lastAt`은 그날 마지막 관측 시각이다.

```json
{
  "firstDate": "2026-10-19", "intervalSeconds": 180, "retentionDays": 90,
  "lastStoredAt": "2026-10-27T12:50:00Z", "collectionError": null,
  "collectionDelayed": false, "updatedAt": "2026-10-27T13:00:00Z",
  "room": "A1", "date": "2026-10-27", "lastAt": "2026-10-27T12:50:00Z",
  "summary": { "percent": 65, "samples": 84, "reason": null, "isCollected": true },
  "hours": [ { "hour": 0, "percent": null, "samples": 0, "reason": "closed", "isCollected": true } ]
}
```

## GET /studyroom/api/readingrooms/{code}/history/weekly

기준 날짜가 속한 월요일부터 일요일까지를 반환한다. `days`는 7개이고, 각 요일은 `summary`와 12개 두 시간 구간(`slots`, 0, 2, ... , 22시 시작)을 가진다.

```json
{
  "room": "A1", "date": "2026-10-27",
  "weekStart": "2026-10-26", "weekEnd": "2026-11-01",
  "summary": { "percent": 61, "samples": 900, "reason": null, "isCollected": true },
  "days": [
    {
      "date": "2026-10-26",
      "summary": { "percent": 58, "samples": 120, "reason": null, "isCollected": true },
      "lastAt": "2026-10-26T12:50:00Z",
      "slots": [ { "hour": 0, "percent": null, "samples": 0, "reason": "closed", "isCollected": true } ]
    }
  ]
}
```

## GET /studyroom/api/readingrooms/{code}/history/monthly

기준 날짜가 속한 달을 두 축으로 반환한다. `days`는 그달 날짜별 일평균(길이 28부터 31), `hours`는 시간대별 월평균(24개, 0시부터 23시)이다.

```json
{
  "room": "A1", "date": "2026-10-27",
  "monthStart": "2026-10-01", "monthEnd": "2026-10-31",
  "summary": { "percent": 63, "samples": 4000, "reason": null, "isCollected": true },
  "days": [ { "date": "2026-10-01", "percent": null, "samples": 0, "reason": "outside_retention", "isCollected": false } ],
  "hours": [ { "hour": 0, "percent": null, "samples": 0, "reason": "closed", "isCollected": true } ]
}
```

## GET /studyroom/health

외부 연결 없이 프로세스 생존만 확인한다. 응답은 `{"status": "ok"}`다.

# 학교 좌석 시스템 수집 정보

이 문서는 서비스가 [학교 좌석배정 페이지](http://smart.tukorea.ac.kr/lib/index.html)에서 열람실 현황을 읽는 방법을 정리한다. 내용은 2026년 10월 13일 16:18에 확인한 공개 응답과 페이지 JavaScript를 근거로 한다. 2026년 10월 27일에는 개발 PC에서 사이트가 응답하지 않아(80 포트 timeout) 다시 대조하지 못했다. 응답 형식이 바뀌면 이 문서와 `app/services/readingroom_parser.py`를 함께 고친다.

## 대상 공간

서비스는 일반 열람실 두 곳과 노트북열람실을 다룬다.

| 코드 | 원문 이름 | 2026-10-13 좌석 수 |
|---|---|---:|
| A1 | 1일반열람실 | 92 |
| A2 | 2일반열람실 | 60 |
| E1 | 노트북열람실 | 83 |

원문은 C1(자료열람실), D1(멀티미디어실), B1(그룹스터디룸)도 반환한다. 서비스는 이 세 공간을 응답에서 뺀다. D1은 `USE_YN=N`으로 운영이 꺼져 있고, B1은 좌석 상태가 숫자 코드라 D/U 해석을 적용할 수 없다.

## 요청 방법

두 endpoint 모두 로그인과 쿠키 없이 HTTP 200을 반환한다. Content-Type은 `text/html`이지만 본문은 JSON 배열이다. 응답은 `Cache-Control`로 캐시를 금지한다. 서비스는 공식 페이지와 같은 `Referer: http://smart.tukorea.ac.kr/lib/index.html`과 브라우저 `User-Agent`를 붙인다. HTTPS(443)는 열려 있지 않으므로 HTTP를 사용한다.

| 용도 | 요청 |
|---|---|
| 공간별 집계와 운영 정책 | `GET /library2014/Library_Seat_Count.php?test=N` |
| 공간 하나의 좌석 목록 | `GET /library2014/getSeatInfoSql.php?test=N&room_code=A1` |

공식 페이지는 열람실 현황을 30초마다 다시 조회한다. 서비스는 Redis에 `LIVE_CACHE_TTL_SECONDS`(기본 20초) 동안 결과를 보관해 학교 요청 횟수를 제한한다. 집계 요청과 좌석 요청은 한 transaction이 아니므로 두 응답의 사용 좌석 수가 잠깐 어긋날 수 있다.

## 집계 응답 필드

`Library_Seat_Count.php`는 공간마다 아래 필드를 반환한다. 숫자 집계는 `"92"`처럼 문자열이다.

- `ROOM_CODE`, `ROOM_NAME`은 공간 코드와 이름이다.
- `TOTAL_COUNT`, `INUSE_COUNT`, `NOTINUSE_COUNT`는 전체, 사용 중, 미사용 좌석 수다.
- `START_TIME`, `END_TIME`은 평일 운영시간이다. `HH:MM` 또는 `HHMM` 형식이다.
- `WEEKEND_YN`, `WEEKEND_START`, `WEEKEND_END`는 주말 운영 여부와 시간이다.
- `HOLIDAY_YN`, `HOLIDAY_START`, `HOLIDAY_END`는 휴일 운영 여부와 시간이다.
- `TODAY_WEEKEND_YN`, `TODAY_HOLIDAY_YN`은 조회일이 주말 또는 휴일인지 나타낸다.
- `USE_YN`은 공간 활성 여부다. 공식 페이지는 N인 공간을 숨긴다.
- `NOTEBOOK_YN`은 노트북 허용 여부다. A1은 N, A2와 E1은 Y였다.
- `ASSIGN_HOUR`는 1회 배정 시간(시간 단위)이다. 세 공간 모두 4였다.
- `EXTEND_YN`은 연장 기능 여부, `SYNC_WITH_GATE`는 출입 연동 여부다.
- `START_DATE`는 정책 시작일이다. `2025/09/01` 형식이다.
- `RESERVE_YN`, `RESERVE_COUNT`, `RESERVE_DELAY`는 의미를 확인하지 못했다. 서비스는 쓰지 않는다.

### 운영 상태 판정

서비스는 공식 페이지의 판정 순서를 따른다.

- 기본값은 평일 시간이다. `TODAY_WEEKEND_YN=Y`이면 주말 시간과 `WEEKEND_YN`을 쓴다.
- `TODAY_HOLIDAY_YN=Y`이면 휴일 시간과 `HOLIDAY_YN`으로 다시 덮어쓴다.
- `USE_YN=N`이면 `disabled`다.
- 해당 일자의 flag가 N이거나 시작과 종료가 같으면(`00:00`부터 `00:00`) `closed`다.
- 한국 시각이 시작과 종료 사이면 `open`, 아니면 `outside_hours`다. 종료가 시작보다 이르면 자정을 넘는 구간으로 본다.

## 좌석 응답 필드

`getSeatInfoSql.php`는 좌석마다 아래 필드를 반환한다.

- `SEAT_CODE`는 좌석 번호다. `"1"`처럼 앞자리 0이 없는 문자열이다.
- `SEAT_NAME`은 좌석명이다. A1과 A2는 `A1-001`, E1은 `E1-01` 형식이 섞여 있다.
- `SEAT_STATUS`는 `U`(사용 중)와 `D`(미사용)다. 다른 값은 `unknown`으로 둔다.
- `SEAT_TIME_GAP`은 남은 이용 시간(분)이다. 사용 중 좌석은 `"187"` 같은 문자열, 미사용 좌석은 숫자 0이다.
- `SEAT_TIME_LEFT`는 남은 시간 문자열이다. 사용 중 좌석은 `03:06`, 미사용 좌석은 `0-3:0-4` 같은 의미 없는 값이다. 서비스는 쓰지 않는다.
- `SEAT_START`, `SEAT_END`, `SEAT_DELAY_START`, `SEAT_DELAY_END`는 `26/10/13` 같은 날짜만 담는다. 시각 계산에 쓰지 않는다.
- `SEAT_CLASS`(M, N, O 등), `SEAT_DIV`(T, B)는 의미를 확인하지 못했다.
- `SEAT_LEFT`, `SEAT_TOP`, `SEAT_WIDTH`, `SEAT_HEIGHT`는 좌표와 크기다. 공식 HTML 배치표와 일치하지 않는다.

서비스는 사용 중 좌석의 `SEAT_TIME_GAP`을 `remainingMinutes`로 내보내고, 조회 시각에 더한 값을 `estimatedEndAt`으로 계산한다. 연장과 조기 반납이 있으므로 이 시각은 추정값이다. 공식 페이지는 만료 60분 전부터 연장 버튼을 보여 준다.

## 개인정보

좌석 응답에는 `SEAT_USER_NAME`, `SEAT_USER_SNO`, `SEAT_USER_DEPT`, `SEAT_USER_POSITION`, `SEAT_USER_STATUS`가 함께 내려온다. 이용자의 이름, 학번, 학과다. 서비스는 parser에서 필요한 필드만 골라 내고 원문 응답을 로그, cache, DB 어디에도 남기지 않는다. 테스트 fixture도 이 다섯 필드를 지운 사본을 쓴다.

## 수집하지 않는 것

공식 페이지 JavaScript에는 로그인, 좌석 배정, 반납, 연장, 스터디룸 예약과 취소, 문 잠금 요청이 있다. 서비스는 조회 endpoint 두 개만 호출한다. robots.txt는 404였으며 이는 수집 허가나 금지의 근거가 아니다.

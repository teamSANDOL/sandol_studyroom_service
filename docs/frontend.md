# 테스트용 페이지

FastAPI는 `/studyroom/`에서 API 동작을 확인하는 개발용 페이지를 제공한다. 사용자에게 보여 줄 화면이 아니므로 디자인 없이 API 응답만 표시한다. 모든 값은 서비스 API를 거쳐 학교 좌석 시스템에서 가져온다.

## 파일 역할

- `app/routers/web.py`는 HTML 파일을 응답한다.
- `app/template/index.html`은 API별 확인 영역을 정의한다.
- `app/static/js/app.js`는 API를 요청하고 결과를 표와 문장으로 표시한다.
- `app/static/css/style.css`는 표와 좌석 칸의 최소 스타일이다.

## 기능

열람실 현황 표는 `GET api/readingrooms`를 페이지 진입 시와 새로고침 버튼으로 요청한다. 행을 누르면 `GET api/readingrooms/{code}`와 `GET api/readingrooms/{code}/seats`를 함께 요청해 운영 정책, 30분 안에 반납 예정인 좌석, 좌석 칸을 표시한다. 좌석 칸은 상태별 색으로 구분하고 마우스를 올리면 남은 시간을 보여 준다.

좌석 조회 form은 `GET api/readingrooms/{code}/seats/{number}` 응답 JSON을 그대로 출력한다. 서버 상태 버튼은 `GET health`를 요청한다. 모든 요청은 5초 timeout을 두고 실패하면 HTTP 상태와 오류 코드를 표시한다.

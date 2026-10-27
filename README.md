이 repo는 스터디룸/열람실 현황 서비스를 위한 저장소다.

## 현재 구성

Docker Compose는 FastAPI, PostgreSQL 15, Redis 7.4를 실행한다. FastAPI는 환경 변수를 검증하고 `/studyroom/health`를 제공한다. 열람실 및 스터디룸 조회, collector와 DB migration은 후속 구현 대상이다.

API는 localhost의 8000 포트를 사용하고 모든 경로를 `/studyroom` 아래에 둔다. 통합 gateway 가 경로를 그대로 넘기기 때문이다. DB와 Redis는 Compose 내부 네트워크에서 연결하며 DB 기록은 named volume에 보관한다. Redis는 재시작하면 cache를 비운다.

FastAPI는 `/studyroom/`에서 테스트용 페이지를 제공한다. 페이지는 예시 현황을 표시하고 서버 상태 확인 버튼으로 실제 `/studyroom/health`를 요청한다. 파일별 역할과 동작은 [frontend 설명](docs/frontend.md)에 기록한다.

## 실행

개발자는 저장소 root에서 환경 파일을 준비한다.

```bash
cp .env.example .env
```

개발자는 `.env`의 `POSTGRES_PASSWORD`와 필요한 설정을 채운 뒤 서비스를 실행한다. `API_PORT`는 host 포트를 변경한다. `API_DOCS_ENABLED`는 `/studyroom/docs`와 `/studyroom/openapi.json` 제공 여부를 정한다.

```bash
docker compose up --build --wait
curl --fail http://127.0.0.1:8000/studyroom/health
```

정상 생존 응답은 `{"status":"ok"}`다. 이 endpoint는 학교, DB와 Redis의 준비 상태를 검사하지 않는다. Compose는 DB와 Redis의 자체 healthcheck가 통과한 뒤 API를 시작한다.

`POSTGRES_HOST`와 `REDIS_URL`의 예시 hostname은 Compose 내부용이다. 명시한 `DATABASE_URL`은 `POSTGRES_*`보다 우선하며 빈 값이면 앱이 해당 필드로 연결 URL을 구성한다.

## 개발 검증

프로젝트는 Python 3.11과 uv를 사용한다. 개발자는 lock 기준으로 의존성을 설치하고 검증한다.

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## 종료

개발자는 다음 명령으로 컨테이너를 중지하고 네트워크를 정리한다. Compose는 DB volume을 유지한다.

```bash
docker compose down
```

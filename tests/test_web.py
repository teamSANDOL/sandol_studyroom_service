"""테스트용 페이지와 연결된 정적 파일을 검증한다."""

from html.parser import HTMLParser
from urllib.parse import urljoin

from httpx import ASGITransport, AsyncClient

from app.config.settings import Settings
from app.main import create_app


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "stylesheet":
            path = values.get("href")
        elif tag == "script":
            path = values.get("src")
        else:
            return
        if path is not None:
            self.assets.append(path)


async def test_page_serves_linked_assets_without_external_connections() -> None:
    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        postgres_host="unreachable.invalid",
        redis_url="redis://unreachable.invalid:6379/0",
        development_frontend_mode=True,
    )
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        response = await client.get("/studyroom/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["cache-control"] == "no-store"
        assert "열람실 현황" in response.text
        parser = AssetParser()
        parser.feed(response.text)
        assert len(parser.assets) == 2
        for path in parser.assets:
            asset = await client.get(urljoin("/studyroom/", path))
            assert asset.status_code == 200
            assert asset.content
        assert (await client.get("/studyroom/static/missing.js")).status_code == 404
        assert (await client.get("/studyroom/health")).json() == {"status": "ok"}


async def test_frontend_is_hidden_when_development_mode_is_off() -> None:
    settings = Settings(
        _env_file=None,
        postgres_password="test-password",
        postgres_host="unreachable.invalid",
        redis_url="redis://unreachable.invalid:6379/0",
        development_frontend_mode=False,
    )
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://test"
    ) as client:
        assert (await client.get("/studyroom/")).status_code == 404
        assert (await client.get("/studyroom/static/js/app.js")).status_code == 404
        # API 와 health 는 모드와 무관하게 열려 있다.
        assert (await client.get("/studyroom/health")).json() == {"status": "ok"}

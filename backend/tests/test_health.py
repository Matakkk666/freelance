from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_unavailable_database(settings: Settings) -> None:
    broken = settings.model_copy(
        update={"database_url": SecretStr("postgresql+asyncpg://app:app@127.0.0.1:1/app")}
    )
    app = create_app(broken)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_asgi_entrypoint_exposes_app() -> None:
    from app import asgi  # noqa: PLC0415  # import builds the app from env, keep it test-local

    assert isinstance(asgi.app, FastAPI)

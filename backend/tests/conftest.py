"""Test fixtures. Tests run against a real PostgreSQL database that is recreated per run."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

from app.config import REPO_ROOT, Settings, get_settings
from app.main import create_app


def _test_database_url() -> str:
    settings = get_settings()
    if settings.test_database_url is not None:
        return settings.test_database_url.get_secret_value()
    url = make_url(settings.database_url.get_secret_value())
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


async def _recreate_database(url: str) -> None:
    sa_url = make_url(url)
    name = sa_url.database
    assert name is not None
    assert name.endswith("_test"), f"Refusing to recreate non-test database {name!r}"
    admin_engine = create_async_engine(
        sa_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin_engine.dispose()


def alembic_config(url: str) -> Config:
    config = Config(REPO_ROOT / "backend" / "alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    """Recreate the test database and migrate it to head once per test run."""
    url = _test_database_url()
    asyncio.run(_recreate_database(url))
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def settings(database_url: str) -> Settings:
    return get_settings().model_copy(
        update={"app_env": "test", "database_url": SecretStr(database_url)}
    )


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        yield conn


@pytest.fixture
async def db_session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is rolled back after the test.

    Code under test may call commit(): it only releases a savepoint.
    Tests that need real commits or several connections (locks, concurrency)
    should use `engine` directly and clean up after themselves.
    """
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

import pytest
from pydantic import SecretStr

from app.config import Settings


def test_secrets_are_hidden_in_repr() -> None:
    settings = Settings(database_url=SecretStr("postgresql+asyncpg://u:topsecret@h/db"))

    assert "topsecret" not in repr(settings)
    assert "topsecret" not in str(settings.model_dump())


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")

    assert Settings().cors_origins == ["http://a.test", "http://b.test"]

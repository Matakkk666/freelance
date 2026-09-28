"""Migrations must apply, roll back and match the models (no forgotten autogenerate)."""

from alembic import command

from tests.conftest import alembic_config


def test_migrations_roundtrip_and_match_models(database_url: str) -> None:
    config = alembic_config(database_url)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    # Raises if models and the migrated schema differ.
    command.check(config)

"""Import every module's models here so Alembic autogenerate sees the full metadata."""

from app.db import Base

__all__ = ["Base"]

"""
Async SQLAlchemy engine + session factory.

Uses DATABASE_URL from settings:
  dev  → sqlite+aiosqlite:///./mawrid.db
  prod → postgresql+asyncpg://user:pass@host/mawrid
"""

from __future__ import annotations
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from database.models import Base
from config.settings import get_settings

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_async_engine(
            settings.database_url,
            connect_args=connect_args,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(), expire_on_commit=False
        )
    return _session_factory


async def init_db() -> None:
    """Create all tables on startup (idempotent)."""
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session

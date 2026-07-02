"""
database.py

Async SQLAlchemy engine and session management for the Telegram forwarding bot.

Provides:
    - Base: Declarative base class for all ORM models.
    - engine: The async SQLAlchemy engine bound to the Neon PostgreSQL database.
    - async_session_factory: async_sessionmaker used to create AsyncSession instances.
    - get_session(): Async context manager yielding a session for use in handlers/forwarder.
    - init_db(): Creates all tables on startup (idempotent).
    - close_db(): Gracefully disposes of the engine on shutdown.

All other modules must obtain database sessions exclusively through get_session().
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger("bot.database")


class Base(DeclarativeBase):
    """Declarative base class shared by every ORM model in models.py."""


# Async engine bound to Neon PostgreSQL.
# pool_pre_ping avoids stale-connection errors common with serverless Postgres
# providers (like Neon) that can silently close idle connections.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)

# Session factory used throughout the application.
# expire_on_commit=False prevents attribute-refresh errors when ORM objects
# are accessed after a commit inside handlers (a common pattern in this bot).
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Provide a transactional async database session as a context manager.

    Commits on successful exit, rolls back on any exception, and always
    closes the session. This is the single entry point every handler,
    forwarder function, and utility should use to talk to the database.

    Yields:
        An active AsyncSession bound to the configured engine.

    Example:
        async with get_session() as session:
            session.add(some_object)
    """
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Database session rolled back due to an exception.")
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """
    Create all database tables defined on Base.metadata if they do not exist.

    This is safe to call on every startup: SQLAlchemy's create_all() only
    creates tables that are missing and never drops or alters existing ones.
    Import models.py before calling this so all models are registered on
    Base.metadata.
    """
    # Imported here (not at module top) to avoid a circular import between
    # database.py and models.py, since models.py imports Base from this module.
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables verified/created successfully.")


async def close_db() -> None:
    """
    Dispose of the engine's connection pool.

    Should be called once during application shutdown to cleanly release
    all pooled database connections.
    """
    await engine.dispose()
    logger.info("Database engine disposed.")


async def check_connection() -> bool:
    """
    Verify that the database is reachable.

    Useful as a startup sanity check before the bot begins polling/webhooks.

    Returns:
        True if a connection could be established and a trivial query executed,
        False otherwise.
    """
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database connection check failed.")
        return False

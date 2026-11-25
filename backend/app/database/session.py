import asyncio
import time
from collections.abc import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


def create_engine_instance(url: str) -> AsyncEngine:
    """Create and configure an asynchronous SQLAlchemy engine."""
    engine_kwargs: dict = {
        "echo": settings.DB_ECHO,
        "future": True,
    }

    if url.startswith("sqlite"):
        # For SQLite (unit tests / fallback)
        engine_kwargs["poolclass"] = NullPool
    else:
        # For PostgreSQL (production & local development)
        engine_kwargs.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_pre_ping": True,
            "connect_args": {"timeout": 3.0, "command_timeout": 5.0},
        })

    return create_async_engine(url, **engine_kwargs)


engine = create_engine_instance(settings.DATABASE_URL)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> tuple[bool, str, float]:
    """
    Verify database connectivity by executing a lightweight query.
    Returns (is_connected: bool, message: str, latency_ms: float).
    """
    start_time = time.perf_counter()
    try:
        async def _ping() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=3.0)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return True, "Database connection operational", latency_ms
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, f"Database connection unavailable: {exc}", latency_ms


import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import check_db_connection


@pytest.mark.asyncio
async def test_session_lifecycle(db_session: AsyncSession):
    """Verify that an async database session executes queries and transactions properly."""
    result = await db_session.execute(text("SELECT 42 as answer"))
    row = result.mappings().one()
    assert row["answer"] == 42


@pytest.mark.asyncio
async def test_check_db_connection_structure():
    """Verify check_db_connection returns a 3-tuple with boolean, message, and latency."""
    connected, message, latency_ms = await check_db_connection()
    assert isinstance(connected, bool)
    assert isinstance(message, str)
    assert isinstance(latency_ms, float)
    assert latency_ms >= 0.0

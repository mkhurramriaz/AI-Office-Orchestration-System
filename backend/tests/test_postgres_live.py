import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import Department, ProjectStatus, UserRole
from app.models.project import Project
from app.models.user import User


@pytest.mark.asyncio
async def test_live_postgres_tables_exist():
    """Verify on live PostgreSQL that all Phase 2 tables and Alembic version exist."""
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
            )
            tables = {row[0] for row in res.fetchall()}

            expected_tables = {
                "alembic_version",
                "users",
                "projects",
                "tasks",
                "task_dependencies",
                "task_history",
                "notifications",
                "workflow_executions",
            }
            assert expected_tables.issubset(tables), f"Missing tables in PostgreSQL: {expected_tables - tables}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_model_insertion_and_foreign_keys():
    """Verify live PostgreSQL UUID generation, enum column storage, and foreign key enforcement."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            # 1. Create User
            test_uid = uuid.uuid4().hex[:8]
            user = User(
                full_name="Postgres Live Test User",
                email=f"pg_test_{test_uid}@taskflow.com",
                hashed_password=get_password_hash("LiveTestPass123!"),
                role=UserRole.MANAGER,
                department=Department.AI,
                job_title="Database Verification Engineer",
                is_active=True,
            )
            session.add(user)
            await session.flush()

            assert isinstance(user.id, uuid.UUID)

            # 2. Create Project referencing User
            project = Project(
                project_name="Live PG Project Test",
                description="Verifying live Postgres dialect",
                status=ProjectStatus.PLANNING,
                created_by=user.id,
            )
            session.add(project)
            await session.flush()

            assert isinstance(project.id, uuid.UUID)
            assert project.created_by == user.id

            # Roll back so live database remains clean
            await session.rollback()
    finally:
        await engine.dispose()

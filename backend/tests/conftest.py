import os
import sys
import uuid
from collections.abc import AsyncGenerator
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database.base import Base
from app.main import app
from app.models.enums import Department, UserRole
from app.models.user import User

# Test SQLite in-memory async database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test with isolated in-memory tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an AsyncClient that overrides get_db dependency with test session."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def create_user_helper(
    session: AsyncSession,
    role: UserRole,
    email: str | None = None,
    full_name: str | None = None,
    department: Department = Department.WEB,
) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        full_name=full_name or f"Test {role.value} {uid}",
        email=email or f"user_{uid}@example.com",
        hashed_password=get_password_hash("SecretPassword123!"),
        role=role,
        department=department,
        job_title=f"{role.value} Specialist",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def get_token_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role.value, "email": user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    return await create_user_helper(db_session, UserRole.ADMIN, email="admin@taskflow.com")


@pytest_asyncio.fixture(scope="function")
async def manager_user(db_session: AsyncSession) -> User:
    return await create_user_helper(db_session, UserRole.MANAGER, email="manager@taskflow.com")


@pytest_asyncio.fixture(scope="function")
async def employee_user(db_session: AsyncSession) -> User:
    return await create_user_helper(db_session, UserRole.EMPLOYEE, email="employee1@taskflow.com")


@pytest_asyncio.fixture(scope="function")
async def other_employee_user(db_session: AsyncSession) -> User:
    return await create_user_helper(db_session, UserRole.EMPLOYEE, email="employee2@taskflow.com")

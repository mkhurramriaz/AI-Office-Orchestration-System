import pytest
from httpx import AsyncClient

from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import get_token_headers


@pytest.mark.asyncio
async def test_user_registration_success(async_client: AsyncClient):
    """Test public user registration with Employee and Manager roles."""
    payload = {
        "full_name": "Alice Developer",
        "email": "alice@example.com",
        "password": "StrongPassword123!",
        "role": "EMPLOYEE",
        "department": "WEB",
        "job_title": "Frontend Engineer",
        "professional_role": "FRONTEND_DEVELOPER",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["role"] == "EMPLOYEE"
    assert data["professional_role"] == "FRONTEND_DEVELOPER"
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_public_registration_cannot_create_admin(async_client: AsyncClient):
    """Verify that public registration attempts with ADMIN role are strictly rejected."""
    payload = {
        "full_name": "Malicious Admin Attempt",
        "email": "bad_admin@example.com",
        "password": "StrongPassword123!",
        "role": "ADMIN",
        "department": "OPERATIONS",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 403
    assert "ADMIN role is not permitted" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected(async_client: AsyncClient, employee_user: User):
    """Verify that attempting to register an existing email returns 400."""
    payload = {
        "full_name": "Duplicate User",
        "email": employee_user.email,
        "password": "StrongPassword123!",
        "role": "EMPLOYEE",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, employee_user: User):
    """Verify valid credentials return access and refresh tokens."""
    payload = {
        "email": employee_user.email,
        "password": "SecretPassword123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, employee_user: User):
    """Verify login with incorrect password returns 401."""
    payload = {
        "email": employee_user.email,
        "password": "WrongPassword999!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_token_refresh(async_client: AsyncClient, employee_user: User):
    """Verify refresh token can issue new access and refresh tokens."""
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": employee_user.email, "password": "SecretPassword123!"},
    )
    tokens = login_res.json()
    refresh_token = tokens["refresh_token"]

    refresh_res = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


@pytest.mark.asyncio
async def test_get_me_endpoint(async_client: AsyncClient, manager_user: User):
    """Verify /auth/me returns the profile of the authenticated caller."""
    headers = get_token_headers(manager_user)
    response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(manager_user.id)
    assert data["email"] == manager_user.email
    assert data["role"] == "MANAGER"


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(async_client: AsyncClient):
    """Verify requests lacking Bearer tokens are rejected with 401/403."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code in [401, 403]

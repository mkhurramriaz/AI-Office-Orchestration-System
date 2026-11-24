import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token_headers


@pytest.mark.asyncio
async def test_admin_can_list_users(async_client: AsyncClient, admin_user: User, employee_user: User):
    """Verify ADMIN can list all organization users."""
    headers = get_token_headers(admin_user)
    response = await async_client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_employee_cannot_list_users(async_client: AsyncClient, employee_user: User):
    """Verify EMPLOYEE role cannot list all organization users (returns 403)."""
    headers = get_token_headers(employee_user)
    response = await async_client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_user(async_client: AsyncClient, admin_user: User):
    """Verify ADMIN can create a new user account with any role."""
    headers = get_token_headers(admin_user)
    payload = {
        "full_name": "Charlie Manager",
        "email": "charlie_mgr@example.com",
        "password": "Password123!",
        "role": "MANAGER",
        "department": "AI",
        "job_title": "AI Lead",
    }
    response = await async_client.post("/api/v1/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "charlie_mgr@example.com"
    assert data["role"] == "MANAGER"


@pytest.mark.asyncio
async def test_employee_cannot_escalate_role(async_client: AsyncClient, employee_user: User):
    """Verify EMPLOYEE cannot escalate their own role to ADMIN."""
    headers = get_token_headers(employee_user)
    response = await async_client.patch(
        f"/api/v1/users/{employee_user.id}",
        json={"role": "ADMIN"},
        headers=headers,
    )
    assert response.status_code == 403
    assert "administrators can modify roles" in response.json()["error"]["message"]

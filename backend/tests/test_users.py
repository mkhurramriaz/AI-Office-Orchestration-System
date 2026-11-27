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
        "professional_role": "AI_ENGINEER",
    }
    response = await async_client.post("/api/v1/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "charlie_mgr@example.com"
    assert data["role"] == "MANAGER"
    assert data["professional_role"] == "AI_ENGINEER"


@pytest.mark.asyncio
async def test_user_creation_rejects_unknown_professional_role(async_client: AsyncClient, admin_user: User):
    response = await async_client.post(
        "/api/v1/users",
        json={
            "full_name": "Invalid Role",
            "email": "invalid_role@example.com",
            "password": "Password123!",
            "role": "EMPLOYEE",
            "professional_role": "MAGIC_ENGINEER",
        },
        headers=get_token_headers(admin_user),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_cannot_remove_last_active_admin(async_client: AsyncClient, admin_user: User):
    headers = get_token_headers(admin_user)
    demote = await async_client.patch(f"/api/v1/users/{admin_user.id}", json={"role": "MANAGER"}, headers=headers)
    deactivate = await async_client.patch(f"/api/v1/users/{admin_user.id}", json={"is_active": False}, headers=headers)
    assert demote.status_code == 400
    assert deactivate.status_code == 400
    assert "last administrator" in demote.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_admin_overview_reports_real_organization_counts(async_client: AsyncClient, admin_user: User, employee_user: User):
    response = await async_client.get("/api/v1/admin/overview", headers=get_token_headers(admin_user))
    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] == 2
    assert data["active_users"] == 2
    assert data["users_by_account_role"]["ADMIN"] == 1
    assert data["users_by_account_role"]["EMPLOYEE"] == 1
    assert data["employees_by_department"]["WEB"] == 1


@pytest.mark.asyncio
async def test_manager_cannot_read_admin_overview(async_client: AsyncClient, manager_user: User):
    response = await async_client.get("/api/v1/admin/overview", headers=get_token_headers(manager_user))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_clear_professional_role(async_client: AsyncClient, admin_user: User, employee_user: User):
    response = await async_client.patch(
        f"/api/v1/users/{employee_user.id}",
        json={"professional_role": None},
        headers=get_token_headers(admin_user),
    )
    assert response.status_code == 200
    assert response.json()["professional_role"] is None


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

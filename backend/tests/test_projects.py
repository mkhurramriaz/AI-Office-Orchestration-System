import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token_headers


@pytest.mark.asyncio
async def test_manager_can_create_project(async_client: AsyncClient, manager_user: User):
    """Verify MANAGER role can create a new project."""
    headers = get_token_headers(manager_user)
    payload = {
        "project_name": "E-Commerce Revamp",
        "description": "Full platform overhaul with AI recommendations",
        "original_brief": "Build a scalable shop with search and payments",
    }
    response = await async_client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["project_name"] == "E-Commerce Revamp"
    assert data["status"] == "DRAFT"
    assert data["created_by"] == str(manager_user.id)


@pytest.mark.asyncio
async def test_employee_cannot_create_project(async_client: AsyncClient, employee_user: User):
    """Verify EMPLOYEE role cannot create projects (returns 403)."""
    headers = get_token_headers(employee_user)
    payload = {"project_name": "Unauthorized Project"}
    response = await async_client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_update_own_project(async_client: AsyncClient, manager_user: User):
    """Verify MANAGER can update details of their own project."""
    headers = get_token_headers(manager_user)
    create_res = await async_client.post(
        "/api/v1/projects",
        json={"project_name": "Initial Name", "description": "Draft"},
        headers=headers,
    )
    project_id = create_res.json()["id"]

    patch_res = await async_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_name": "Updated Name", "status": "ACTIVE"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["project_name"] == "Updated Name"
    assert patch_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_other_manager_cannot_modify_project(
    async_client: AsyncClient,
    manager_user: User,
    admin_user: User,
    db_session,
):
    """Verify that a manager cannot modify another manager's project."""
    # Manager 1 creates a project
    m1_headers = get_token_headers(manager_user)
    res = await async_client.post(
        "/api/v1/projects",
        json={"project_name": "Manager 1 Project"},
        headers=m1_headers,
    )
    project_id = res.json()["id"]

    # Manager 2 tries to update it
    from app.models.enums import UserRole
    from tests.conftest import create_user_helper

    m2 = await create_user_helper(db_session, UserRole.MANAGER, email="manager2@taskflow.com")
    m2_headers = get_token_headers(m2)

    update_res = await async_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_name": "Hijacked"},
        headers=m2_headers,
    )
    assert update_res.status_code == 403

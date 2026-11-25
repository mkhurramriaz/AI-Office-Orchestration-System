import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token_headers


@pytest.fixture
async def sample_project(async_client: AsyncClient, manager_user: User):
    headers = get_token_headers(manager_user)
    res = await async_client.post(
        "/api/v1/projects",
        json={"project_name": "Task Test Project", "description": "For task validation"},
        headers=headers,
    )
    return res.json()


@pytest.mark.asyncio
async def test_task_creation_and_code_uniqueness(
    async_client: AsyncClient,
    manager_user: User,
    sample_project: dict,
):
    """Verify task creation and uniqueness of task_code within project."""
    headers = get_token_headers(manager_user)
    project_id = sample_project["id"]

    task_payload = {
        "project_id": project_id,
        "task_code": "T1",
        "title": "Design Database Schema",
        "department": "AI",
        "priority": "HIGH",
        "acceptance_criteria": "All tables created with foreign keys",
    }
    res = await async_client.post("/api/v1/tasks", json=task_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["task_code"] == "T1"
    assert data["status"] == "TODO"

    # Duplicate code in same project must fail
    dup_res = await async_client.post("/api/v1/tasks", json=task_payload, headers=headers)
    assert dup_res.status_code == 400
    assert "already exists in this project" in dup_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_circular_dependency_prevention(
    async_client: AsyncClient,
    manager_user: User,
    sample_project: dict,
    db_session,
):
    """Verify that circular task dependencies (e.g. T1 -> T2 -> T3 -> T1) are blocked by the cycle detector."""
    import uuid
    from app.services.task_service import TaskService
    from fastapi import HTTPException

    project_id = uuid.UUID(sample_project["id"])
    task_service = TaskService(db_session)

    t1_id = uuid.uuid4()
    t2_id = uuid.uuid4()
    t3_id = uuid.uuid4()

    # Mock edges in project: t2 depends on t1 (t2, t1), t3 depends on t2 (t3, t2)
    # If t1 attempts to depend on t3 (t1, t3), a cycle is formed: t1 -> t3 -> t2 -> t1
    with pytest.raises(HTTPException) as exc_info:
        await task_service._detect_cycle(
            project_id=project_id,
            new_edges=[(t2_id, t1_id), (t3_id, t2_id), (t1_id, t3_id)],
        )
    assert exc_info.value.status_code == 400
    assert "Circular dependency detected" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cross_project_dependency_rejected(
    async_client: AsyncClient,
    manager_user: User,
    sample_project: dict,
):
    """Verify that a task cannot declare prerequisites from another project."""
    headers = get_token_headers(manager_user)
    # Create second project
    p2_res = await async_client.post(
        "/api/v1/projects",
        json={"project_name": "Project 2"},
        headers=headers,
    )
    p2_id = p2_res.json()["id"]

    # Create task in Project 2
    t_other = await async_client.post(
        "/api/v1/tasks",
        json={"project_id": p2_id, "task_code": "T_P2", "title": "Other project task", "department": "WEB"},
        headers=headers,
    )
    other_task_id = t_other.json()["id"]

    # Attempt to create task in Project 1 depending on task from Project 2
    bad_res = await async_client.post(
        "/api/v1/tasks",
        json={
            "project_id": sample_project["id"],
            "task_code": "T_ILLEGAL",
            "title": "Cross project dependency",
            "department": "WEB",
            "depends_on_task_ids": [other_task_id],
        },
        headers=headers,
    )
    assert bad_res.status_code == 400
    assert "belongs to a different project" in bad_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_task_assignment_and_notifications(
    async_client: AsyncClient,
    manager_user: User,
    employee_user: User,
    sample_project: dict,
):
    """Verify task assignment creates TaskHistory and Notification for employee."""
    headers = get_token_headers(manager_user)
    emp_headers = get_token_headers(employee_user)

    # 1. Create unassigned task
    task_res = await async_client.post(
        "/api/v1/tasks",
        json={
            "project_id": sample_project["id"],
            "task_code": "T_ASSIGN",
            "title": "Assign me",
            "department": "WEB",
        },
        headers=headers,
    )
    task_id = task_res.json()["id"]

    # 2. Assign task to employee
    assign_res = await async_client.post(
        f"/api/v1/tasks/{task_id}/assign",
        json={"assigned_to": str(employee_user.id)},
        headers=headers,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_to"] == str(employee_user.id)

    # 3. Check Task History
    history_res = await async_client.get(f"/api/v1/tasks/{task_id}/history", headers=headers)
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 2  # CREATED and ASSIGNED
    actions = [h["action"] for h in history]
    assert "ASSIGNED" in actions

    # 4. Check Employee Notification
    notif_res = await async_client.get("/api/v1/notifications", headers=emp_headers)
    assert notif_res.status_code == 200
    notifs = notif_res.json()["items"]
    assert any("T_ASSIGN" in n["message"] for n in notifs)


@pytest.mark.asyncio
async def test_task_completion_blocked_by_incomplete_dependencies(
    async_client: AsyncClient,
    manager_user: User,
    employee_user: User,
    sample_project: dict,
):
    """
    CRITICAL BUSINESS RULE:
    A task cannot be marked COMPLETED if any of its prerequisite dependencies remain incomplete.
    """
    headers = get_token_headers(manager_user)
    emp_headers = get_token_headers(employee_user)
    project_id = sample_project["id"]

    # 1. Create Prerequisite Task A (status: TODO)
    res_a = await async_client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "task_code": "DEP_A", "title": "Prerequisite A", "department": "WEB"},
        headers=headers,
    )
    task_a_id = res_a.json()["id"]

    # 2. Create Task B depending on Task A, assigned to Employee
    res_b = await async_client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "task_code": "DEP_B",
            "title": "Dependent B",
            "department": "WEB",
            "assigned_to": str(employee_user.id),
            "depends_on_task_ids": [task_a_id],
        },
        headers=headers,
    )
    task_b_id = res_b.json()["id"]

    # 3. Employee tries to mark Task B as COMPLETED while Task A is still TODO
    premature_complete = await async_client.post(
        f"/api/v1/tasks/{task_b_id}/status",
        json={"status": "COMPLETED", "completion_notes": "Finished prematurely"},
        headers=emp_headers,
    )
    assert premature_complete.status_code == 400
    assert "Required prerequisite task(s)" in premature_complete.json()["error"]["message"]
    assert "DEP_A" in premature_complete.json()["error"]["message"]

    # 4. Now complete Task A first
    complete_a = await async_client.post(
        f"/api/v1/tasks/{task_a_id}/status",
        json={"status": "COMPLETED"},
        headers=headers,
    )
    assert complete_a.status_code == 200
    assert complete_a.json()["status"] == "COMPLETED"

    # 5. Now complete Task B (should succeed!)
    valid_complete_b = await async_client.post(
        f"/api/v1/tasks/{task_b_id}/status",
        json={"status": "COMPLETED", "completion_notes": "All prerequisites satisfied"},
        headers=emp_headers,
    )
    assert valid_complete_b.status_code == 200
    assert valid_complete_b.json()["status"] == "COMPLETED"
    assert valid_complete_b.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_employee_cannot_modify_other_employees_task(
    async_client: AsyncClient,
    manager_user: User,
    employee_user: User,
    other_employee_user: User,
    sample_project: dict,
):
    """Verify that an employee cannot update or view another employee's private task."""
    mgr_headers = get_token_headers(manager_user)
    emp1_headers = get_token_headers(employee_user)
    emp2_headers = get_token_headers(other_employee_user)

    # Manager assigns task to Employee 1
    task_res = await async_client.post(
        "/api/v1/tasks",
        json={
            "project_id": sample_project["id"],
            "task_code": "T_PRIVATE",
            "title": "Employee 1 Only",
            "department": "WEB",
            "assigned_to": str(employee_user.id),
        },
        headers=mgr_headers,
    )
    task_id = task_res.json()["id"]

    # Employee 2 attempts to change status of Employee 1's task
    unauth_status = await async_client.post(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=emp2_headers,
    )
    assert unauth_status.status_code == 403

    # Employee 2 attempts to view Employee 1's task directly
    unauth_get = await async_client.get(f"/api/v1/tasks/{task_id}", headers=emp2_headers)
    assert unauth_get.status_code == 403

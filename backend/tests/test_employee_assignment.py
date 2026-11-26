"""Focused Phase 4B assignment recommendation tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.api.v1.endpoints.ai import get_employee_assignment_service
from app.models.enums import Department, ProfessionalRole, UserRole
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.schemas.project_plan import ProjectPlan
from app.services.employee_assignment import (
    EmployeeAssignmentService,
    normalize_professional_role,
    professional_role_matches,
    recommend_assignments,
)
from tests.conftest import create_user_helper, get_token_headers


def task(task_id: str, *, deps: list[str] | None = None, department="WEB", role="BACKEND_DEVELOPER") -> dict:
    return {
        "task_id": task_id,
        "title": f"Task {task_id}",
        "description": "Complete a concrete deliverable.",
        "required_role": role,
        "department": department,
        "priority": "MEDIUM",
        "dependencies": deps or [],
        "acceptance_criteria": ["Deliverable is reviewed."],
    }


def plan(*tasks: dict) -> ProjectPlan:
    return ProjectPlan.model_validate(
        {"project_name": "Assignment Test", "project_description": "Test plan", "tasks": list(tasks)}
    )


def user(
    uid: str,
    *,
    role=UserRole.EMPLOYEE,
    professional_role=ProfessionalRole.BACKEND_DEVELOPER,
    department=Department.WEB,
    active=True,
    title="Backend developer",
) -> User:
    return User(
        id=uuid.UUID(uid),
        full_name=f"User {uid[-4:]}",
        email=f"{uid[-4:]}@example.com",
        hashed_password="not-used",
        role=role,
        department=department,
        is_active=active,
        job_title=title,
        professional_role=professional_role,
    )


def test_professional_role_normalization_and_exact_matching():
    assert normalize_professional_role(ProfessionalRole.BACKEND_DEVELOPER) == "backend developer"
    assert professional_role_matches(
        ProfessionalRole.BACKEND_DEVELOPER, ProfessionalRole.BACKEND_DEVELOPER
    )
    assert not professional_role_matches(
        ProfessionalRole.BACKEND_DEVELOPER, ProfessionalRole.FRONTEND_DEVELOPER
    )
    assert not professional_role_matches(ProfessionalRole.BACKEND_DEVELOPER, None)


def test_account_role_is_independent_from_professional_role():
    manager = user(
        "00000000-0000-0000-0000-000000000006",
        role=UserRole.MANAGER,
        professional_role=ProfessionalRole.BACKEND_DEVELOPER,
    )
    assert manager.role is UserRole.MANAGER
    assert manager.professional_role is ProfessionalRole.BACKEND_DEVELOPER


def test_only_active_employees_with_matching_department_and_title_are_selected():
    plan_data = plan(task("T1"))
    candidates = [
        user("00000000-0000-0000-0000-000000000001", active=False),
        user("00000000-0000-0000-0000-000000000002", role=UserRole.MANAGER),
        user("00000000-0000-0000-0000-000000000003", department=Department.QA),
        user(
            "00000000-0000-0000-0000-000000000004",
            professional_role=None,
            title="Senior Backend Engineer",
        ),
        user("00000000-0000-0000-0000-000000000005"),
    ]
    result = recommend_assignments(plan_data, candidates, {candidate.id: 0 for candidate in candidates})
    assert [item.employee_id for item in result.assignments] == [candidates[-1].id]


def test_lowest_workload_selected_then_uuid_tie_breaker_and_temporary_load():
    plan_data = plan(task("T1"), task("T2"), task("T3"))
    first = user("00000000-0000-0000-0000-000000000001")
    second = user("00000000-0000-0000-0000-000000000002")
    result = recommend_assignments(plan_data, [second, first], {first.id: 2, second.id: 1})
    assert [a.employee_id for a in result.assignments] == [second.id, first.id, second.id]
    assert [(a.current_workload, a.projected_workload) for a in result.assignments] == [(1, 2), (2, 3), (2, 3)]


def test_dependency_order_and_failed_prerequisite_do_not_stop_independent_tasks():
    plan_data = plan(
        task("dependent", deps=["blocked"]),
        task("blocked", department="QA"),
        task("independent"),
    )
    employee = user("00000000-0000-0000-0000-000000000001")
    result = recommend_assignments(plan_data, [employee], {employee.id: 0})
    assert [item.task_id for item in result.assignments] == ["independent"]
    assert {item.task_id for item in result.unassigned_tasks} == {"blocked", "dependent"}
    assert "Prerequisite" in next(item.reason for item in result.unassigned_tasks if item.task_id == "dependent")


def test_dependency_plan_validation_rejects_cycles():
    with pytest.raises(ValueError, match="circular"):
        plan(task("A", deps=["B"]), task("B", deps=["A"]))


@pytest.mark.asyncio
async def test_unavailable_workload_is_not_assumed_to_be_zero():
    candidate = user("00000000-0000-0000-0000-000000000001")
    repository = AsyncMock()
    repository.get_employees_by_department.return_value = [candidate]
    repository.get_user_workload.side_effect = RuntimeError("database unavailable")
    result = await EmployeeAssignmentService(repository).recommend(plan(task("T1")))
    assert not result.assignments
    assert "workload data is unavailable" in result.unassigned_tasks[0].reason


@pytest.mark.asyncio
async def test_assign_endpoint_authentication_and_role(async_client: AsyncClient, employee_user: User):
    payload = plan(task("T1")).model_dump(mode="json")
    no_auth = await async_client.post("/api/v1/ai/assign", json=payload)
    assert no_auth.status_code in (401, 403)
    denied = await async_client.post(
        "/api/v1/ai/assign", json=payload, headers=get_token_headers(employee_user)
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_assign_endpoint_returns_recommendations_without_persistence(
    async_client: AsyncClient, manager_user: User, db_session
):
    employee = await create_user_helper(
        db_session, UserRole.EMPLOYEE, email="phase4b@example.com", department=Department.WEB
    )
    employee.job_title = "Employee Specialist"
    employee.professional_role = ProfessionalRole.BACKEND_DEVELOPER
    await db_session.commit()
    payload = plan(task("T1")).model_dump(mode="json")
    response = await async_client.post(
        "/api/v1/ai/assign", json=payload, headers=get_token_headers(manager_user)
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["is_fully_assigned"] is True
    assert result["assignments"][0]["employee_id"] == str(employee.id)
    assert await db_session.scalar(select(func.count(Task.id))) == 0
    assert await db_session.scalar(select(func.count(Notification.id))) == 0


@pytest.mark.asyncio
async def test_assign_endpoint_rejects_invalid_plan(async_client: AsyncClient, manager_user: User):
    response = await async_client.post(
        "/api/v1/ai/assign",
        json={"project_name": "Bad", "project_description": "Bad plan", "tasks": []},
        headers=get_token_headers(manager_user),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_assign_endpoint_sanitizes_database_failure(async_client: AsyncClient, manager_user: User):
    service = AsyncMock()
    service.recommend.side_effect = RuntimeError("private database detail")
    from app.main import app

    app.dependency_overrides[get_employee_assignment_service] = lambda: service
    try:
        response = await async_client.post(
            "/api/v1/ai/assign",
            json=plan(task("T1")).model_dump(mode="json"),
            headers=get_token_headers(manager_user),
        )
    finally:
        app.dependency_overrides.pop(get_employee_assignment_service, None)
    assert response.status_code == 503
    assert "private database detail" not in response.text

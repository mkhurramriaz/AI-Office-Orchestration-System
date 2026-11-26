"""Approval workflow API and persistence behavior tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import func, select

from app.api.v1.endpoints.workflows import get_approval_workflow_service
from app.main import app
from app.models.enums import Department, ProfessionalRole, UserRole, WorkflowStatus
from app.models.notification import Notification
from app.models.project import Project
from app.models.task import Task, TaskDependency
from app.models.task_history import TaskHistory
from app.models.user import User
from app.models.workflow import WorkflowExecution
from app.repositories.user_repository import UserRepository
from app.schemas.assignment import AssignmentResult
from app.schemas.project_plan import ProjectPlan
from app.services.approval_workflow import ApprovalWorkflowService
from app.services.employee_assignment import EmployeeAssignmentService
from tests.conftest import create_user_helper, get_token_headers


def make_plan() -> ProjectPlan:
    return ProjectPlan.model_validate(
        {
            "project_name": "Workflow Generated Project",
            "project_description": "A small project used to exercise durable approval.",
            "tasks": [
                {
                    "task_id": "PLAN-A",
                    "title": "Build the frontend",
                    "description": "Create the main user interface.",
                    "required_role": "FRONTEND_DEVELOPER",
                    "department": "WEB",
                    "priority": "HIGH",
                    "dependencies": [],
                    "acceptance_criteria": ["The interface renders correctly."],
                },
                {
                    "task_id": "PLAN-B",
                    "title": "Test the frontend",
                    "description": "Verify the user interface behavior.",
                    "required_role": "QA_ENGINEER",
                    "department": "QA",
                    "priority": "MEDIUM",
                    "dependencies": ["PLAN-A"],
                    "acceptance_criteria": ["Critical flows pass."],
                },
            ],
        }
    )


class FakePlanner:
    def __init__(self, plan: ProjectPlan | None = None):
        self.plan = plan or make_plan()
        self.create_plan = AsyncMock(return_value=self.plan)


def memory_checkpoint_factory():
    saver = InMemorySaver()

    @asynccontextmanager
    async def context():
        yield saver

    return context


async def configure_workflow_service(db_session, manager: User, employees: list[User]):
    for employee in employees:
        employee.professional_role = (
            ProfessionalRole.FRONTEND_DEVELOPER
            if employee.department == Department.WEB
            else ProfessionalRole.QA_ENGINEER
        )
    await db_session.commit()
    service = ApprovalWorkflowService(
        db_session,
        FakePlanner(),
        EmployeeAssignmentService(UserRepository(db_session)),
        memory_checkpoint_factory(),
    )
    app.dependency_overrides[get_approval_workflow_service] = lambda: service
    return service


@pytest.mark.asyncio
async def test_workflow_pauses_for_approval_then_persists_once(
    async_client: AsyncClient,
    db_session,
    manager_user: User,
):
    frontend = await create_user_helper(
        db_session,
        UserRole.EMPLOYEE,
        email="workflow_frontend@example.com",
        department=Department.WEB,
        professional_role=ProfessionalRole.FRONTEND_DEVELOPER,
    )
    qa = await create_user_helper(
        db_session,
        UserRole.EMPLOYEE,
        email="workflow_qa@example.com",
        department=Department.QA,
        professional_role=ProfessionalRole.QA_ENGINEER,
    )
    planner = await configure_workflow_service(db_session, manager_user, [frontend, qa])
    headers = get_token_headers(manager_user)
    try:
        started = await async_client.post(
            "/api/v1/ai/workflows", json={"project_brief": "Build a small accessible site."}, headers=headers
        )
        assert started.status_code == 201, started.text
        workflow = started.json()
        workflow_id = workflow["id"]
        assert workflow["status"] == WorkflowStatus.INTERRUPTED.value
        assert workflow["project_id"] is None
        assert [a["task_id"] for a in workflow["output_data"]["recommendations"]["assignments"]] == [
            "PLAN-A",
            "PLAN-B",
        ]
        assert planner.planner.create_plan.await_count == 1
        assert await db_session.scalar(select(func.count(Project.id))) == 0
        assert await db_session.scalar(select(func.count(Task.id))) == 0

        inspected = await async_client.get(f"/api/v1/ai/workflows/{workflow_id}", headers=headers)
        assert inspected.status_code == 200
        assert inspected.json()["status"] == WorkflowStatus.INTERRUPTED.value

        approved = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "APPROVE"},
            headers=headers,
        )
        assert approved.status_code == 200, approved.text
        result = approved.json()
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert result["project_id"] is not None
        assert len(result["output_data"]["task_ids"]) == 2
        assert await db_session.scalar(select(func.count(Project.id))) == 1
        assert await db_session.scalar(select(func.count(Task.id))) == 2
        assert await db_session.scalar(select(func.count(TaskDependency.id))) == 1
        assert await db_session.scalar(select(func.count(TaskHistory.id))) == 4
        persisted_tasks = (
            await db_session.scalars(select(Task).where(Task.project_id == UUID(result["project_id"])))
        ).all()
        by_code = {task.task_code: task for task in persisted_tasks}
        assert by_code["TASK-001"].assigned_to == frontend.id
        assert by_code["TASK-002"].assigned_to == qa.id
        dependency = await db_session.scalar(select(TaskDependency))
        assert dependency.task_id == by_code["TASK-002"].id
        assert dependency.depends_on_task_id == by_code["TASK-001"].id

        retry = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "APPROVE"},
            headers=headers,
        )
        assert retry.status_code == 200
        assert retry.json()["project_id"] == result["project_id"]
        assert await db_session.scalar(select(func.count(Project.id))) == 1
        assert await db_session.scalar(select(func.count(Task.id))) == 2
        assert await db_session.scalar(select(func.count(TaskHistory.id))) == 4
        assert await db_session.scalar(select(func.count(Notification.id))) == 2
    finally:
        app.dependency_overrides.pop(get_approval_workflow_service, None)


@pytest.mark.asyncio
async def test_rejection_persists_decision_without_creating_project_or_tasks(
    async_client: AsyncClient,
    db_session,
    manager_user: User,
):
    employees = [
        await create_user_helper(
            db_session,
            UserRole.EMPLOYEE,
            email="workflow_reject_frontend@example.com",
            department=Department.WEB,
            professional_role=ProfessionalRole.FRONTEND_DEVELOPER,
        ),
        await create_user_helper(
            db_session,
            UserRole.EMPLOYEE,
            email="workflow_reject_qa@example.com",
            department=Department.QA,
            professional_role=ProfessionalRole.QA_ENGINEER,
        ),
    ]
    await configure_workflow_service(db_session, manager_user, employees)
    headers = get_token_headers(manager_user)
    try:
        started = await async_client.post(
            "/api/v1/ai/workflows", json={"project_brief": "A rejected project."}, headers=headers
        )
        workflow_id = started.json()["id"]
        rejected = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "REJECT"},
            headers=headers,
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == WorkflowStatus.REJECTED.value
        assert rejected.json()["project_id"] is None
        assert await db_session.scalar(select(func.count(Project.id))) == 0
        assert await db_session.scalar(select(func.count(Task.id))) == 0

        retry = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "REJECT"},
            headers=headers,
        )
        assert retry.status_code == 200
        assert retry.json()["status"] == WorkflowStatus.REJECTED.value
    finally:
        app.dependency_overrides.pop(get_approval_workflow_service, None)


@pytest.mark.asyncio
async def test_workflow_endpoints_enforce_authentication_roles_and_ownership(
    async_client: AsyncClient,
    db_session,
    manager_user: User,
    employee_user: User,
):
    second_manager = await create_user_helper(
        db_session, UserRole.MANAGER, email="another_manager_workflow@example.com"
    )
    employees = [
        await create_user_helper(
            db_session,
            UserRole.EMPLOYEE,
            email="workflow_auth_frontend@example.com",
            department=Department.WEB,
            professional_role=ProfessionalRole.FRONTEND_DEVELOPER,
        ),
        await create_user_helper(
            db_session,
            UserRole.EMPLOYEE,
            email="workflow_auth_qa@example.com",
            department=Department.QA,
            professional_role=ProfessionalRole.QA_ENGINEER,
        ),
    ]
    await configure_workflow_service(db_session, manager_user, employees)
    try:
        no_auth = await async_client.post("/api/v1/ai/workflows", json={"project_brief": "A plan."})
        assert no_auth.status_code in (401, 403)
        forbidden = await async_client.post(
            "/api/v1/ai/workflows",
            json={"project_brief": "A plan."},
            headers=get_token_headers(employee_user),
        )
        assert forbidden.status_code == 403

        started = await async_client.post(
            "/api/v1/ai/workflows",
            json={"project_brief": "A plan."},
            headers=get_token_headers(manager_user),
        )
        workflow_id = started.json()["id"]
        not_owner = await async_client.get(
            f"/api/v1/ai/workflows/{workflow_id}", headers=get_token_headers(second_manager)
        )
        assert not_owner.status_code == 404
        stored = await db_session.get(WorkflowExecution, UUID(workflow_id))
        stored.status = WorkflowStatus.RUNNING
        await db_session.commit()
        wrong_state = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "APPROVE"},
            headers=get_token_headers(manager_user),
        )
        assert wrong_state.status_code == 409
        invalid_state = await async_client.post(
            f"/api/v1/ai/workflows/{workflow_id}/decision",
            json={"decision": "INVALID"},
            headers=get_token_headers(manager_user),
        )
        assert invalid_state.status_code == 422
    finally:
        app.dependency_overrides.pop(get_approval_workflow_service, None)


@pytest.mark.asyncio
async def test_unassigned_recommendations_are_saved_as_unassigned_tasks_on_approval(
    async_client: AsyncClient,
    db_session,
    manager_user: User,
):
    planner = FakePlanner()
    assignment_service = AsyncMock()
    assignment_service.recommend.return_value = AssignmentResult.model_validate(
        {
            "project_name": "Workflow Generated Project",
            "assignments": [],
            "unassigned_tasks": [
                {"task_id": task_id, "task_title": title, "reason": "No employee has the matching role."}
                for task_id, title in (("PLAN-A", "Build the frontend"), ("PLAN-B", "Test the frontend"))
            ],
            "is_fully_assigned": False,
        }
    )
    service = ApprovalWorkflowService(
        db_session, planner, assignment_service, memory_checkpoint_factory()
    )
    app.dependency_overrides[get_approval_workflow_service] = lambda: service
    try:
        started = await async_client.post(
            "/api/v1/ai/workflows",
            json={"project_brief": "A partially assignable plan."},
            headers=get_token_headers(manager_user),
        )
        assert started.status_code == 201
        approved = await async_client.post(
            f"/api/v1/ai/workflows/{started.json()['id']}/decision",
            json={"decision": "APPROVE"},
            headers=get_token_headers(manager_user),
        )
        assert approved.status_code == 200
        assert await db_session.scalar(select(func.count(Task.id))) == 2
        unassigned_count = await db_session.scalar(
            select(func.count(Task.id)).where(Task.assigned_to.is_(None))
        )
        assert unassigned_count == 2
    finally:
        app.dependency_overrides.pop(get_approval_workflow_service, None)

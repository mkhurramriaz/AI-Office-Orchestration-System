"""Phase 4A schema, DAG, LangGraph, and authenticated API tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.api.v1.endpoints.ai import get_project_planner_service
from app.main import app
from app.models.enums import Department, TaskPriority, UserRole
from app.schemas.project_plan import PlannedTask, ProjectPlan
from app.services.plan_validation import validate_dependency_graph
from app.services.project_planner import (
    PlanGenerationError,
    PlanValidationError,
    ProjectPlannerService,
)
from tests.conftest import get_token_headers


def planned_task(
    task_id: str,
    *,
    dependencies: list[str] | None = None,
    title: str = "Build API",
    priority: str = "HIGH",
    required_role: str = "EMPLOYEE",
    department: str = "WEB",
) -> dict:
    return {
        "task_id": task_id,
        "title": title,
        "description": "Implement the API endpoint and document its behavior.",
        "required_role": required_role,
        "department": department,
        "priority": priority,
        "dependencies": dependencies or [],
        "acceptance_criteria": ["The endpoint returns the documented response."],
    }


def valid_plan_data(tasks: list[dict] | None = None) -> dict:
    return {
        "project_name": "Employee Portal",
        "project_description": "Build a secure portal for employee operations.",
        "tasks": tasks if tasks is not None else [planned_task("TASK-001")],
    }


def make_plan() -> ProjectPlan:
    return ProjectPlan.model_validate(valid_plan_data())


class FakeStructuredModel:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.result


# Schema validation


def test_project_plan_accepts_valid_structured_plan():
    plan = ProjectPlan.model_validate(valid_plan_data())
    assert plan.project_name == "Employee Portal"
    assert plan.tasks[0].priority is TaskPriority.HIGH
    assert plan.tasks[0].required_role is UserRole.EMPLOYEE
    assert plan.tasks[0].department is Department.WEB


def test_project_plan_rejects_empty_task_list():
    with pytest.raises(ValidationError, match="at least 1 item"):
        ProjectPlan.model_validate(valid_plan_data(tasks=[]))


def test_project_plan_rejects_duplicate_task_ids():
    with pytest.raises(ValidationError, match="unique"):
        ProjectPlan.model_validate(
            valid_plan_data(tasks=[planned_task("TASK-001"), planned_task("TASK-001")])
        )


def test_project_plan_rejects_empty_task_title():
    with pytest.raises(ValidationError, match="empty"):
        PlannedTask.model_validate(planned_task("TASK-001", title="   "))


def test_project_plan_rejects_unsupported_priority():
    with pytest.raises(ValidationError, match="priority"):
        PlannedTask.model_validate(planned_task("TASK-001", priority="URGENT"))


@pytest.mark.parametrize(
    ("field", "value"),
    [("required_role", "BACKEND_DEVELOPER"), ("department", "ENGINEERING")],
)
def test_project_plan_rejects_unsupported_role_or_department(field, value):
    with pytest.raises(ValidationError, match=field):
        PlannedTask.model_validate(planned_task("TASK-001", **{field: value}))


# DAG validation


def test_dependency_graph_accepts_linear_dependencies():
    validate_dependency_graph(
        [
            planned_task("A"),
            planned_task("B", dependencies=["A"]),
            planned_task("C", dependencies=["B"]),
        ]
    )


def test_dependency_graph_accepts_independent_tasks_and_empty_graph():
    validate_dependency_graph([planned_task("A"), planned_task("B")])
    validate_dependency_graph([])


def test_dependency_graph_rejects_missing_reference():
    with pytest.raises(ValueError, match="missing dependency"):
        validate_dependency_graph([planned_task("A", dependencies=["MISSING"])])


def test_dependency_graph_rejects_self_dependency():
    with pytest.raises(ValueError, match="cannot depend on itself"):
        validate_dependency_graph([planned_task("A", dependencies=["A"])])


def test_dependency_graph_rejects_duplicate_dependency():
    with pytest.raises(ValueError, match="duplicate dependencies"):
        validate_dependency_graph(
            [planned_task("A"), planned_task("B", dependencies=["A", "A"])]
        )


def test_dependency_graph_rejects_cycle():
    with pytest.raises(ValueError, match="circular"):
        validate_dependency_graph(
            [planned_task("A", dependencies=["B"]), planned_task("B", dependencies=["A"])]
        )


def test_dependency_graph_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="unique"):
        validate_dependency_graph([planned_task("A"), planned_task("A")])


# Structured generation and LangGraph workflow


@pytest.mark.asyncio
async def test_planner_generates_and_validates_structured_plan():
    model = FakeStructuredModel(result=valid_plan_data())
    service = ProjectPlannerService(structured_model_factory=lambda: model)

    plan = await service.create_plan("Build a secure employee portal")

    assert plan.project_name == "Employee Portal"
    assert plan.tasks[0].required_role is UserRole.EMPLOYEE
    assert model.messages[0].content.startswith("You are TaskFlow AI's project planning assistant.")
    assert "Do not invent employees" in model.messages[0].content
    assert model.messages[1].content == "Build a secure employee portal"
    assert set(service._workflow.get_graph().nodes) >= {"generate_plan", "validate_plan"}


@pytest.mark.asyncio
async def test_planner_propagates_provider_failure_safely():
    service = ProjectPlannerService(
        structured_model_factory=lambda: FakeStructuredModel(error=RuntimeError("provider secret detail"))
    )
    with pytest.raises(PlanGenerationError, match="could not generate") as exc:
        await service.create_plan("Build a portal")
    assert "provider secret detail" not in str(exc.value)


@pytest.mark.asyncio
async def test_planner_rejects_invalid_structured_output():
    service = ProjectPlannerService(structured_model_factory=lambda: FakeStructuredModel(result={"bad": True}))
    with pytest.raises(PlanValidationError, match="failed schema"):
        await service.create_plan("Build a portal")


@pytest.mark.asyncio
async def test_planner_rejects_invalid_dependency_dag():
    cyclic_plan = valid_plan_data(
        tasks=[planned_task("A", dependencies=["B"]), planned_task("B", dependencies=["A"])]
    )
    service = ProjectPlannerService(structured_model_factory=lambda: FakeStructuredModel(result=cyclic_plan))
    with pytest.raises(PlanValidationError, match="failed schema or dependency"):
        await service.create_plan("Build a portal")


def test_groq_structured_model_uses_existing_provider_settings():
    from app.services.project_planner import build_structured_planner_model

    groq_model = MagicMock()
    structured_model = MagicMock()
    groq_model.with_structured_output.return_value = structured_model
    with (
        patch("app.services.project_planner.get_settings") as get_settings,
        patch("langchain_groq.ChatGroq", return_value=groq_model) as chat_groq,
    ):
        get_settings.return_value.DEFAULT_LLM_PROVIDER = "groq"
        get_settings.return_value.DEFAULT_LLM_MODEL = "configured-model"
        get_settings.return_value.GROQ_API_KEY = "test-only-key"
        result = build_structured_planner_model()

    chat_groq.assert_called_once_with(
        model="configured-model",
        api_key="test-only-key",
        temperature=0,
        max_retries=2,
    )
    groq_model.with_structured_output.assert_called_once_with(ProjectPlan)
    assert result is structured_model


# API authorization and error handling


@pytest.mark.asyncio
async def test_plan_endpoint_requires_authentication(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/ai/plan", json={"project_brief": "Build a secure company website."}
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_plan_endpoint_rejects_employee_role(async_client: AsyncClient, employee_user):
    response = await async_client.post(
        "/api/v1/ai/plan",
        headers=get_token_headers(employee_user),
        json={"project_brief": "Build a secure company website."},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_plan_endpoint_accepts_manager_and_returns_plan(async_client: AsyncClient, manager_user):
    plan = make_plan()
    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=plan)
    app.dependency_overrides[get_project_planner_service] = lambda: planner
    try:
        response = await async_client.post(
            "/api/v1/ai/plan",
            headers=get_token_headers(manager_user),
            json={"project_brief": "Build a secure company website."},
        )
    finally:
        app.dependency_overrides.pop(get_project_planner_service, None)

    assert response.status_code == 200
    assert response.json()["project_name"] == "Employee Portal"
    assert response.json()["tasks"][0]["task_id"] == "TASK-001"
    assert "assigned_to" not in response.json()["tasks"][0]
    planner.create_plan.assert_awaited_once_with("Build a secure company website.")


@pytest.mark.asyncio
async def test_plan_endpoint_rejects_blank_brief(async_client: AsyncClient, manager_user):
    response = await async_client.post(
        "/api/v1/ai/plan",
        headers=get_token_headers(manager_user),
        json={"project_brief": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "message"),
    [
        (PlanGenerationError("provider detail"), 502, "The planning service is temporarily unavailable."),
        (PlanValidationError("schema detail"), 502, "The AI generated a project plan that failed validation."),
    ],
)
async def test_plan_endpoint_sanitizes_planner_errors(
    async_client, manager_user, error, expected_status, message
):
    planner = MagicMock()
    planner.create_plan = AsyncMock(side_effect=error)
    app.dependency_overrides[get_project_planner_service] = lambda: planner
    try:
        response = await async_client.post(
            "/api/v1/ai/plan",
            headers=get_token_headers(manager_user),
            json={"project_brief": "Build a secure company website."},
        )
    finally:
        app.dependency_overrides.pop(get_project_planner_service, None)

    assert response.status_code == expected_status
    assert response.json()["error"]["message"] == message
    assert "detail" not in response.text

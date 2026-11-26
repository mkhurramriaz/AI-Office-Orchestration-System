"""Persistent plan, recommendation, approval, and project execution workflow."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, TypedDict
from uuid import UUID, uuid4

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.models.enums import TaskStatus, UserRole, WorkflowStatus
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workflow import WorkflowExecution
from app.repositories.user_repository import UserRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.assignment import AssignmentResult
from app.schemas.project import ProjectCreate
from app.schemas.project_plan import ProjectPlan
from app.schemas.task import TaskCreate, TaskResponse
from app.schemas.workflow import WorkflowDecision
from app.services.employee_assignment import EmployeeAssignmentService
from app.services.project_planner import ProjectPlannerService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

# Psycopg's async protocol requires a selector loop on Windows. Set this at
# import/startup time, before ASGI or pytest creates its event loop.
if sys.platform == "win32" and isinstance(
    asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy
):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ApprovalWorkflowError(RuntimeError):
    """Raised when a workflow cannot safely be resumed or executed."""


class WorkflowState(TypedDict, total=False):
    workflow_id: str
    initiated_by: str
    project_brief: str
    plan: dict[str, Any]
    recommendations: dict[str, Any]
    decision: str
    execution: dict[str, Any]


CheckpointContextFactory = Callable[[], AsyncIterator[Any]]


@asynccontextmanager
async def postgres_checkpoint_context() -> AsyncIterator[Any]:
    """Open PostgreSQL-backed LangGraph checkpoint storage using app DB config."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Persistent approval workflows require PostgreSQL.")
    from psycopg.conninfo import make_conninfo

    checkpoint_url = make_conninfo(
        host=url.host or "localhost",
        port=url.port or 5432,
        dbname=url.database or "",
        user=url.username,
        password=url.password,
        **dict(url.query),
    )
    serde = JsonPlusSerializer(allowed_msgpack_modules=[])
    async with AsyncPostgresSaver.from_conn_string(checkpoint_url, serde=serde) as saver:
        # The saver maintains its own migrations. Serialize first-use setup
        # across application workers because workflow starts can be concurrent.
        await saver.conn.execute(
            "SELECT pg_advisory_lock(hashtextextended(%s, 0))",
            ("taskflow-ai-checkpoint-setup",),
        )
        try:
            await saver.setup()
        finally:
            await saver.conn.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                ("taskflow-ai-checkpoint-setup",),
            )
        yield saver


class ApprovalWorkflowService:
    """Coordinates the graph while SQLAlchemy owns durable business records."""

    def __init__(
        self,
        session: AsyncSession,
        planner: ProjectPlannerService,
        assignment_service: EmployeeAssignmentService,
        checkpoint_context_factory: CheckpointContextFactory = postgres_checkpoint_context,
    ) -> None:
        self.session = session
        self.planner = planner
        self.assignment_service = assignment_service
        self.checkpoint_context_factory = checkpoint_context_factory
        self.workflow_repo = WorkflowRepository(session)

    def _build_graph(self, checkpointer: Any):
        graph = StateGraph(WorkflowState)
        graph.add_node("generate_plan", self._generate_plan)
        graph.add_node("recommend_employees", self._recommend_employees)
        graph.add_node("manager_approval", self._manager_approval)
        graph.add_node("persist_project", self._persist_project)
        graph.add_node("reject_workflow", self._reject_workflow)
        graph.add_edge(START, "generate_plan")
        graph.add_edge("generate_plan", "recommend_employees")
        graph.add_edge("recommend_employees", "manager_approval")
        graph.add_conditional_edges(
            "manager_approval",
            lambda state: "persist_project" if state.get("decision") == WorkflowDecision.APPROVE.value else "reject_workflow",
            {"persist_project": "persist_project", "reject_workflow": "reject_workflow"},
        )
        graph.add_edge("persist_project", END)
        graph.add_edge("reject_workflow", END)
        return graph.compile(checkpointer=checkpointer)

    async def start(self, project_brief: str, manager: User) -> WorkflowExecution:
        """Persist a workflow identity, then run until the approval interrupt."""
        workflow_id = uuid4()
        execution = WorkflowExecution(
            id=workflow_id,
            project_id=None,
            initiated_by=manager.id,
            status=WorkflowStatus.RUNNING,
            thread_id=str(workflow_id),
            input_data={"project_brief": project_brief},
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(execution)
        await self.session.flush()
        await self.session.commit()

        try:
            async with self.checkpoint_context_factory() as checkpointer:
                graph = self._build_graph(checkpointer)
                state = await graph.ainvoke(
                    {
                        "workflow_id": str(execution.id),
                        "initiated_by": str(manager.id),
                        "project_brief": project_brief,
                    },
                    config={"configurable": {"thread_id": execution.thread_id}},
                )
            current = await self.workflow_repo.get_by_id(execution.id)
            if current is None:
                raise ApprovalWorkflowError("Workflow record was not found after planning.")
            current.status = WorkflowStatus.INTERRUPTED
            current.output_data = {
                "plan": state.get("plan"),
                "recommendations": state.get("recommendations"),
            }
            await self.session.commit()
            return current
        except Exception as exc:
            await self.session.rollback()
            current = await self.workflow_repo.get_by_id(execution.id)
            if current is not None and current.project_id is None:
                current.status = WorkflowStatus.FAILED
                current.error_message = "Planning or employee recommendation failed."
                current.completed_at = datetime.now(timezone.utc)
                await self.session.commit()
            logger.warning("Approval workflow planning failed (%s).", type(exc).__name__)
            if current is not None:
                return current
            raise ApprovalWorkflowError("Workflow could not be started.") from None

    async def resume(self, execution: WorkflowExecution, decision: WorkflowDecision) -> WorkflowExecution:
        """Resume an interrupted graph with the manager's decision."""
        if execution.status in (WorkflowStatus.COMPLETED, WorkflowStatus.REJECTED):
            return execution
        if execution.status != WorkflowStatus.INTERRUPTED:
            raise ApprovalWorkflowError("Workflow is not waiting for a manager decision.")
        async with self.checkpoint_context_factory() as checkpointer:
            graph = self._build_graph(checkpointer)
            await graph.ainvoke(
                Command(resume={"decision": decision.value}),
                config={"configurable": {"thread_id": execution.thread_id}},
            )
        refreshed = await self.workflow_repo.get_by_id(execution.id)
        if refreshed is None:
            raise ApprovalWorkflowError("Workflow record was not found after resuming.")
        return refreshed

    async def _generate_plan(self, state: WorkflowState) -> dict[str, Any]:
        plan = await self.planner.create_plan(state["project_brief"])
        return {"plan": plan.model_dump(mode="json")}

    async def _recommend_employees(self, state: WorkflowState) -> dict[str, Any]:
        plan = ProjectPlan.model_validate(state["plan"])
        recommendations = await self.assignment_service.recommend(plan)
        return {"recommendations": recommendations.model_dump(mode="json")}

    async def _manager_approval(self, state: WorkflowState) -> dict[str, str]:
        resume_value = interrupt(
            {
                "workflow_id": state["workflow_id"],
                "message": "Manager approval is required before creating the project and tasks.",
                "plan": state["plan"],
                "recommendations": state["recommendations"],
            }
        )
        if not isinstance(resume_value, dict) or resume_value.get("decision") not in {
            WorkflowDecision.APPROVE.value,
            WorkflowDecision.REJECT.value,
        }:
            raise ApprovalWorkflowError("A valid approval decision is required.")
        return {"decision": resume_value["decision"]}

    async def _reject_workflow(self, state: WorkflowState) -> dict[str, Any]:
        execution = await self.workflow_repo.get_by_id_for_update(UUID(state["workflow_id"]))
        if execution is None:
            raise ApprovalWorkflowError("Workflow record was not found.")
        if execution.status == WorkflowStatus.COMPLETED:
            return {"execution": execution.output_data or {}}
        if execution.project_id is not None:
            raise ApprovalWorkflowError("A project already exists for this workflow.")
        execution.status = WorkflowStatus.REJECTED
        execution.output_data = {
            "plan": state["plan"],
            "recommendations": state["recommendations"],
        }
        execution.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return {"execution": execution.output_data}

    async def _persist_project(self, state: WorkflowState) -> dict[str, Any]:
        workflow_id = UUID(state["workflow_id"])
        execution = await self.workflow_repo.get_by_id_for_update(workflow_id)
        if execution is None:
            raise ApprovalWorkflowError("Workflow record was not found.")
        if execution.project_id is not None:
            return {"execution": execution.output_data or {"project_id": str(execution.project_id)}}
        if execution.status == WorkflowStatus.REJECTED:
            raise ApprovalWorkflowError("Rejected workflows cannot be executed.")

        plan = ProjectPlan.model_validate(state["plan"])
        recommendations = AssignmentResult.model_validate(state["recommendations"])
        planned_ids = {task.task_id for task in plan.tasks}
        assigned_ids = {item.task_id for item in recommendations.assignments}
        unassigned_ids = {item.task_id for item in recommendations.unassigned_tasks}
        if assigned_ids & unassigned_ids or assigned_ids | unassigned_ids != planned_ids:
            raise ApprovalWorkflowError("The recommendation result does not cover the plan exactly once.")

        assignment_by_task = {item.task_id: item for item in recommendations.assignments}
        user_repo = UserRepository(self.session)
        owner = await user_repo.get_by_id(execution.initiated_by)
        if owner is None or not owner.is_active or owner.role not in (UserRole.MANAGER, UserRole.ADMIN):
            raise ApprovalWorkflowError("The workflow owner is no longer authorized to execute this plan.")

        # Revalidate assignees at approval time so a stale recommendation cannot
        # assign an inactive user or a user whose department/role has changed.
        for planned_task in plan.tasks:
            recommendation = assignment_by_task.get(planned_task.task_id)
            if recommendation is None:
                continue
            employee = await user_repo.get_by_id(recommendation.employee_id)
            if (
                employee is None
                or not employee.is_active
                or employee.role != UserRole.EMPLOYEE
                or employee.department != planned_task.department
                or employee.professional_role != planned_task.required_role
            ):
                raise ApprovalWorkflowError("An employee recommendation is no longer eligible.")

        project = await ProjectService(self.session).create_project(
            ProjectCreate(
                project_name=plan.project_name,
                description=plan.project_description,
                original_brief=execution.input_data.get("project_brief"),
            ),
            owner,
        )

        task_ids: dict[str, UUID] = {}
        remaining = list(plan.tasks)
        ordered: list[Task] = []
        task_service = TaskService(self.session)
        while remaining:
            ready = [task for task in remaining if all(dependency in task_ids for dependency in task.dependencies)]
            if not ready:
                raise ApprovalWorkflowError("Task dependencies could not be resolved safely.")
            for task in ready:
                remaining.remove(task)
                dependencies = [task_ids[dep] for dep in task.dependencies]
                recommendation = assignment_by_task.get(task.task_id)
                persisted = await task_service.create_task(
                    TaskCreate(
                        project_id=project.id,
                        task_code=f"TASK-{len(task_ids) + 1:03d}",
                        title=task.title,
                        description=task.description,
                        department=task.department,
                        required_role=task.required_role.value,
                        priority=task.priority,
                        acceptance_criteria="\n".join(task.acceptance_criteria),
                        status=TaskStatus.TODO,
                        depends_on_task_ids=dependencies,
                    ),
                    owner,
                )
                if recommendation is not None:
                    persisted = await task_service.assign_task(
                        persisted.id,
                        recommendation.employee_id,
                        owner,
                    )
                task_ids[task.task_id] = persisted.id
                ordered.append(persisted)

        execution.project_id = project.id
        execution.status = WorkflowStatus.COMPLETED
        execution.error_message = None
        execution.completed_at = datetime.now(timezone.utc)
        execution.output_data = {
            "project_id": str(project.id),
            "plan": plan.model_dump(mode="json"),
            "recommendations": recommendations.model_dump(mode="json"),
            "task_ids": {key: str(value) for key, value in task_ids.items()},
            "tasks": [TaskResponse.from_orm_model(task).model_dump(mode="json") for task in ordered],
        }
        await self.session.commit()
        return {"execution": execution.output_data}

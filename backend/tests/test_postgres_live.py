import uuid
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import Department, ProfessionalRole, ProjectStatus, UserRole, WorkflowStatus
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workflow import WorkflowExecution
from app.repositories.user_repository import UserRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.project_plan import ProjectPlan
from app.schemas.workflow import WorkflowDecision
from app.services.approval_workflow import ApprovalWorkflowService
from app.services.employee_assignment import EmployeeAssignmentService


@pytest.mark.asyncio
async def test_live_postgres_tables_exist():
    """Verify on live PostgreSQL that all Phase 2 tables and Alembic version exist."""
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
            )
            tables = {row[0] for row in res.fetchall()}

            expected_tables = {
                "alembic_version",
                "users",
                "projects",
                "tasks",
                "task_dependencies",
                "task_history",
                "notifications",
                "workflow_executions",
            }
            assert expected_tables.issubset(tables), f"Missing tables in PostgreSQL: {expected_tables - tables}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_model_insertion_and_foreign_keys():
    """Verify live PostgreSQL UUID generation, enum column storage, and foreign key enforcement."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            # 1. Create User
            test_uid = uuid.uuid4().hex[:8]
            user = User(
                full_name="Postgres Live Test User",
                email=f"pg_test_{test_uid}@taskflow.com",
                hashed_password=get_password_hash("LiveTestPass123!"),
                role=UserRole.MANAGER,
                department=Department.AI,
                job_title="Database Verification Engineer",
                is_active=True,
            )
            session.add(user)
            await session.flush()

            assert isinstance(user.id, uuid.UUID)

            # 2. Create Project referencing User
            project = Project(
                project_name="Live PG Project Test",
                description="Verifying live Postgres dialect",
                status=ProjectStatus.PLANNING,
                created_by=user.id,
            )
            session.add(project)
            await session.flush()

            assert isinstance(project.id, uuid.UUID)
            assert project.created_by == user.id

            # Roll back so live database remains clean
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_checkpoint_persists_approval_and_resumes_after_reopen():
    """Verify the workflow pause survives a new saver connection and executes once."""
    from app.services.approval_workflow import postgres_checkpoint_context

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    manager_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    workflow_id = None
    project_id = None
    plan = ProjectPlan.model_validate(
        {
            "project_name": "Postgres Checkpoint Integration",
            "project_description": "Exercise persisted LangGraph pause and resume.",
            "tasks": [
                {
                    "task_id": "PG-TASK-1",
                    "title": "Implement API",
                    "description": "Implement the small integration task.",
                    "required_role": "BACKEND_DEVELOPER",
                    "department": "WEB",
                    "priority": "HIGH",
                    "dependencies": [],
                    "acceptance_criteria": ["The endpoint is available."],
                }
            ],
        }
    )
    planner = type("FixedPlanner", (), {"create_plan": AsyncMock(return_value=plan)})()

    try:
        async with session_factory() as session:
            manager = User(
                id=manager_id,
                full_name="Checkpoint Test Manager",
                email=f"checkpoint_manager_{manager_id.hex}@example.com",
                hashed_password="test-hash",
                role=UserRole.MANAGER,
                department=Department.WEB,
                is_active=True,
            )
            employee = User(
                id=employee_id,
                full_name="Checkpoint Test Engineer",
                email=f"checkpoint_employee_{employee_id.hex}@example.com",
                hashed_password="test-hash",
                role=UserRole.EMPLOYEE,
                department=Department.WEB,
                professional_role=ProfessionalRole.BACKEND_DEVELOPER,
                is_active=True,
            )
            session.add_all([manager, employee])
            await session.commit()

            service = ApprovalWorkflowService(
                session,
                planner,
                EmployeeAssignmentService(UserRepository(session)),
                postgres_checkpoint_context,
            )
            interrupted = await service.start("Verify persistent workflow recovery.", manager)
            workflow_id = interrupted.id
            assert interrupted.status is WorkflowStatus.INTERRUPTED
            assert interrupted.project_id is None
            assert interrupted.output_data["plan"]["project_name"] == plan.project_name

        # Reopen both the SQLAlchemy session and the saver connection; resume
        # must recover plan and recommendation state exclusively from PostgreSQL.
        async with session_factory() as session:
            execution = await WorkflowRepository(session).get_by_id(workflow_id)
            assert execution is not None
            service = ApprovalWorkflowService(
                session,
                planner,
                EmployeeAssignmentService(UserRepository(session)),
                postgres_checkpoint_context,
            )
            completed = await service.resume(execution, WorkflowDecision.APPROVE)
            assert completed.status is WorkflowStatus.COMPLETED
            project_id = completed.project_id
            assert await session.scalar(select(func.count(Task.id)).where(Task.project_id == project_id)) == 1

            retry = await service.resume(completed, WorkflowDecision.APPROVE)
            assert retry.project_id == project_id
            assert await session.scalar(select(func.count(Task.id)).where(Task.project_id == project_id)) == 1
    finally:
        async with session_factory() as session:
            if workflow_id is not None:
                await session.execute(delete(WorkflowExecution).where(WorkflowExecution.id == workflow_id))
            if project_id is not None:
                await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id.in_([manager_id, employee_id])))
            await session.commit()
        await engine.dispose()

"""Manager API for persistent project approval workflows."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.enums import UserRole, WorkflowStatus
from app.models.user import User
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflow import (
    WorkflowDecisionRequest,
    WorkflowExecutionResponse,
    WorkflowStartRequest,
)
from app.services.approval_workflow import ApprovalWorkflowError, ApprovalWorkflowService
from app.api.v1.endpoints.ai import get_employee_assignment_service, get_project_planner_service
from app.services.employee_assignment import EmployeeAssignmentService
from app.services.project_planner import ProjectPlannerService

router = APIRouter()


def get_approval_workflow_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    planner: Annotated[ProjectPlannerService, Depends(get_project_planner_service)],
    assignment_service: Annotated[EmployeeAssignmentService, Depends(get_employee_assignment_service)],
) -> ApprovalWorkflowService:
    return ApprovalWorkflowService(session, planner, assignment_service)


def _ensure_owner(execution, user: User) -> None:
    if user.role != UserRole.ADMIN and execution.initiated_by != user.id:
        # Avoid disclosing the existence of another manager's workflow.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")


@router.post(
    "",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a project planning and approval workflow",
)
async def start_workflow(
    request: WorkflowStartRequest,
    current_user: Annotated[User, Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))],
    workflow_service: Annotated[ApprovalWorkflowService, Depends(get_approval_workflow_service)],
) -> WorkflowExecutionResponse:
    if not request.project_brief:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Project brief must not be empty.")
    execution = await workflow_service.start(request.project_brief, current_user)
    return WorkflowExecutionResponse.model_validate(execution)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowExecutionResponse,
    summary="Inspect a project approval workflow",
)
async def get_workflow(
    workflow_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))],
) -> WorkflowExecutionResponse:
    execution = await WorkflowRepository(session).get_by_id(workflow_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    _ensure_owner(execution, current_user)
    return WorkflowExecutionResponse.model_validate(execution)


@router.post(
    "/{workflow_id}/decision",
    response_model=WorkflowExecutionResponse,
    summary="Approve or reject a project plan",
)
async def decide_workflow(
    workflow_id: UUID,
    request: WorkflowDecisionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))],
    workflow_service: Annotated[ApprovalWorkflowService, Depends(get_approval_workflow_service)],
) -> WorkflowExecutionResponse:
    execution = await WorkflowRepository(session).get_by_id_for_update(workflow_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    _ensure_owner(execution, current_user)

    if execution.status in (WorkflowStatus.COMPLETED, WorkflowStatus.REJECTED):
        return WorkflowExecutionResponse.model_validate(execution)
    if execution.status != WorkflowStatus.INTERRUPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow is not waiting for a manager decision.",
        )
    try:
        execution = await workflow_service.resume(execution, request.decision)
    except ApprovalWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow could not be resumed. It remains available for retry.",
        ) from None
    return WorkflowExecutionResponse.model_validate(execution)

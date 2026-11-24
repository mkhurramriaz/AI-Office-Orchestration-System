import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.enums import TaskStatus, UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task import (
    TaskAssignRequest,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdate,
)
from app.schemas.task_history import TaskHistoryResponse
from app.services.task_service import TaskService

router = APIRouter()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Task",
    description="Add a task to a project. Validates task codes, prerequisite DAG, and circular dependencies.",
)
async def create_task(
    task_in: TaskCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))],
) -> TaskResponse:
    task_service = TaskService(session)
    task = await task_service.create_task(task_in, current_user)
    return TaskResponse.from_orm_model(task)


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tasks",
    description="Retrieve tasks. Employees only see their own assigned tasks.",
)
async def list_tasks(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    project_id: uuid.UUID | None = None,
    status_filter: TaskStatus | None = Query(None, alias="status"),
    assigned_to: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[TaskResponse]:
    skip = (page - 1) * size
    task_service = TaskService(session)
    tasks = await task_service.list_tasks(
        current_user=current_user,
        project_id=project_id,
        status_filter=status_filter,
        assigned_to=assigned_to,
        skip=skip,
        limit=size,
    )
    items = [TaskResponse.from_orm_model(t) for t in tasks]
    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        size=size,
        pages=1,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Task Details",
)
async def get_task(
    task_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    task_service = TaskService(session)
    task = await task_service.get_task(task_id, current_user)
    return TaskResponse.from_orm_model(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Task Details",
)
async def update_task(
    task_id: uuid.UUID,
    task_in: TaskUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    task_service = TaskService(session)
    task = await task_service.update_task(task_id, task_in, current_user)
    return TaskResponse.from_orm_model(task)


@router.post(
    "/{task_id}/assign",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Task to Employee",
    description="Assigns task, records an append-only audit event, and delivers a notification to the employee.",
)
async def assign_task(
    task_id: uuid.UUID,
    assign_in: TaskAssignRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN]))],
) -> TaskResponse:
    task_service = TaskService(session)
    task = await task_service.assign_task(task_id, assign_in.assigned_to, current_user)
    return TaskResponse.from_orm_model(task)


@router.post(
    "/{task_id}/status",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Task Status",
    description="Updates task status. A task cannot be marked COMPLETED if any of its prerequisite dependencies remain incomplete.",
)
async def update_task_status(
    task_id: uuid.UUID,
    status_in: TaskStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    task_service = TaskService(session)
    task = await task_service.update_task_status(
        task_id=task_id,
        new_status=status_in.status,
        completion_notes=status_in.completion_notes,
        current_user=current_user,
    )
    return TaskResponse.from_orm_model(task)


@router.get(
    "/{task_id}/history",
    response_model=list[TaskHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Task Audit History",
    description="Retrieve the immutable audit history for this task.",
)
async def get_task_history(
    task_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[TaskHistoryResponse]:
    task_service = TaskService(session)
    history = await task_service.get_task_history(task_id, current_user)
    return [TaskHistoryResponse.model_validate(h) for h in history]

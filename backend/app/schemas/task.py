import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department, TaskPriority, TaskStatus


class TaskBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    department: Department = Department.OTHER
    required_role: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    acceptance_criteria: str | None = None


class TaskCreate(TaskBase):
    project_id: uuid.UUID
    task_code: str = Field(..., min_length=1, max_length=50)
    assigned_to: uuid.UUID | None = None
    status: TaskStatus = TaskStatus.TODO
    depends_on_task_ids: list[uuid.UUID] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    department: Department | None = None
    required_role: str | None = None
    priority: TaskPriority | None = None
    acceptance_criteria: str | None = None
    completion_notes: str | None = None


class TaskAssignRequest(BaseModel):
    assigned_to: uuid.UUID


class TaskStatusUpdateRequest(BaseModel):
    status: TaskStatus
    completion_notes: str | None = None


class TaskDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    created_at: datetime


class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    task_code: str
    status: TaskStatus
    assigned_to: uuid.UUID | None = None
    assigned_by: uuid.UUID | None = None
    completion_notes: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    dependencies: list[uuid.UUID] = Field(default_factory=list)

    @classmethod
    def from_orm_model(cls, task: Any) -> "TaskResponse":
        dep_ids: list[uuid.UUID] = []
        if hasattr(task, "dependencies") and "dependencies" in getattr(task, "__dict__", {}):
            for d in task.dependencies:
                if hasattr(d, "depends_on_task_id"):
                    dep_ids.append(d.depends_on_task_id)
        return cls(
            id=task.id,
            project_id=task.project_id,
            task_code=task.task_code,
            title=task.title,
            description=task.description,
            department=task.department,
            required_role=task.required_role,
            priority=task.priority,
            status=task.status,
            assigned_to=task.assigned_to,
            assigned_by=task.assigned_by,
            acceptance_criteria=task.acceptance_criteria,
            completion_notes=task.completion_notes,
            completed_at=task.completed_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
            dependencies=dep_ids,
        )

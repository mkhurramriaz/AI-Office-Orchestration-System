import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectStatus


class ProjectBase(BaseModel):
    project_name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    original_brief: str | None = None
    start_date: datetime | None = None
    deadline: datetime | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    original_brief: str | None = None
    status: ProjectStatus | None = None
    start_date: datetime | None = None
    deadline: datetime | None = None


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ProjectStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    task_count: int = 0

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

from app.models.enums import WorkflowStatus


class WorkflowExecutionCreate(BaseModel):
    project_id: uuid.UUID
    input_data: dict[str, Any]


class WorkflowExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    initiated_by: uuid.UUID
    status: WorkflowStatus
    thread_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

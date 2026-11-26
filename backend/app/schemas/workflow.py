import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import WorkflowStatus


class WorkflowStartRequest(BaseModel):
    project_brief: str = Field(min_length=1, max_length=10000)

    @field_validator("project_brief", mode="before")
    @classmethod
    def trim_brief(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class WorkflowDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class WorkflowDecisionRequest(BaseModel):
    decision: WorkflowDecision


class WorkflowExecutionCreate(BaseModel):
    project_id: uuid.UUID | None = None
    input_data: dict[str, Any]


class WorkflowExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None = None
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

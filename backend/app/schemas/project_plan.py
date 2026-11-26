"""Pydantic schemas for AI-generated project plans (plans are not persisted)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import Department, ProfessionalRole, TaskPriority
from app.services.plan_validation import validate_dependency_graph


def _strip_required_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("This field must be a string.")
    value = value.strip()
    if not value:
        raise ValueError("This field must not be empty.")
    return value


class ProjectPlanRequest(BaseModel):
    """A natural-language brief to plan, without creating project records."""

    project_brief: str

    @field_validator("project_brief", mode="before")
    @classmethod
    def normalize_project_brief(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class PlannedTask(BaseModel):
    """An actionable task proposal without assignment to a real employee."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    required_role: ProfessionalRole
    department: Department
    priority: TaskPriority
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)

    @field_validator("task_id", "title", "description", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def normalize_acceptance_criteria(cls, values: list[str]) -> list[str]:
        if not isinstance(values, list):
            return values
        return [_strip_required_text(value) for value in values]


class ProjectPlan(BaseModel):
    """Validated, ephemeral project plan returned by the AI planner."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=2, max_length=255)
    project_description: str = Field(min_length=1, max_length=4000)
    tasks: list[PlannedTask] = Field(min_length=1, max_length=100)

    @field_validator("project_name", "project_description", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @model_validator(mode="after")
    def validate_task_dependencies(self) -> "ProjectPlan":
        validate_dependency_graph(self.tasks)
        return self

"""Schemas for non-persistent employee assignment recommendations."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Department, ProfessionalRole


class AssignmentRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_title: str
    employee_id: UUID
    employee_name: str
    department: Department
    required_role: ProfessionalRole
    current_workload: int = Field(ge=0)
    projected_workload: int = Field(ge=1)
    reason: str


class UnassignedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_title: str
    reason: str


class AssignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    assignments: list[AssignmentRecommendation]
    unassigned_tasks: list[UnassignedTask]
    is_fully_assigned: bool

    @model_validator(mode="after")
    def validate_consistency(self) -> "AssignmentResult":
        assigned_ids = [item.task_id for item in self.assignments]
        unassigned_ids = [item.task_id for item in self.unassigned_tasks]
        if len(set(assigned_ids + unassigned_ids)) != len(assigned_ids + unassigned_ids):
            raise ValueError("Each planned task must appear exactly once in the assignment result.")
        if self.is_fully_assigned != (not self.unassigned_tasks):
            raise ValueError("is_fully_assigned must reflect whether unassigned tasks exist.")
        return self



"""Deterministic, read-only employee recommendations for ephemeral plans."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from uuid import UUID

from app.models.enums import ProfessionalRole, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.assignment import (
    AssignmentRecommendation,
    AssignmentResult,
    UnassignedTask,
)
from app.schemas.project_plan import ProjectPlan


def normalize_professional_role(value: str | ProfessionalRole | None) -> str:
    """Normalize a professional-role value without fuzzy inference."""
    if value is None:
        return ""
    raw = value.value if isinstance(value, ProfessionalRole) else value
    normalized = unicodedata.normalize("NFKC", raw).casefold().replace("_", " ")
    return " ".join(re.findall(r"[\w]+", normalized))


def professional_role_matches(
    required_role: ProfessionalRole,
    employee_role: ProfessionalRole | None,
) -> bool:
    """Require an exact match between validated professional-role values."""
    return employee_role is not None and normalize_professional_role(required_role) == normalize_professional_role(employee_role)


def recommend_assignments(
    plan: ProjectPlan,
    employees: Sequence[User],
    workloads: Mapping[UUID, int],
    unavailable_workloads: set[UUID] | None = None,
) -> AssignmentResult:
    """Pure deterministic selection logic; does not mutate users or task records."""
    unavailable_workloads = unavailable_workloads or set()
    by_task_id = {task.task_id: task for task in plan.tasks}
    pending = dict(by_task_id)
    resolved: dict[str, bool] = {}
    assignments: list[AssignmentRecommendation] = []
    unassigned: list[UnassignedTask] = []
    projected = dict(workloads)

    # ProjectPlan validation guarantees a DAG. Process ready tasks in the
    # original plan order to keep results repeatable while honoring edges.
    while pending:
        ready = [task for task in plan.tasks if task.task_id in pending and all(dep in resolved for dep in task.dependencies)]
        if not ready:  # Defensive guard if an invalid plan bypasses validation.
            raise ValueError("The project plan contains unresolved or circular dependencies.")
        for task in ready:
            del pending[task.task_id]
            blocked = [dep for dep in task.dependencies if not resolved[dep]]
            if blocked:
                unassigned.append(
                    UnassignedTask(
                        task_id=task.task_id,
                        task_title=task.title,
                        reason="Prerequisite task recommendation failed: " + ", ".join(blocked) + ".",
                    )
                )
                resolved[task.task_id] = False
                continue

            department_candidates = [
                employee
                for employee in employees
                if employee.role == UserRole.EMPLOYEE
                and employee.is_active
                and employee.department == task.department
            ]
            compatible = [
                employee
                for employee in department_candidates
                if professional_role_matches(task.required_role, employee.professional_role)
            ]
            known_workload = [employee for employee in compatible if employee.id in projected and employee.id not in unavailable_workloads]

            if not department_candidates:
                reason = f"No active employees are available in department {task.department.value}."
            elif not compatible:
                reason = (
                    f"No employee in {task.department.value} has a validated professional role matching "
                    f"the required role {task.required_role.value}."
                )
            elif not known_workload:
                reason = "Current workload data is unavailable for all role-compatible employees."
            else:
                employee = min(known_workload, key=lambda item: (projected[item.id], str(item.id)))
                current = projected[employee.id]
                projected[employee.id] = current + 1
                assignments.append(
                    AssignmentRecommendation(
                        task_id=task.task_id,
                        task_title=task.title,
                        employee_id=employee.id,
                        employee_name=employee.full_name,
                        department=employee.department,
                        required_role=task.required_role,
                        current_workload=current,
                        projected_workload=current + 1,
                        reason=(
                            f"Matched the {task.department.value} department and validated professional role; "
                            f"selected the lowest projected active workload ({current}) with UUID tie-breaking."
                        ),
                    )
                )
                resolved[task.task_id] = True
                continue

            unassigned.append(UnassignedTask(task_id=task.task_id, task_title=task.title, reason=reason))
            resolved[task.task_id] = False

    return AssignmentResult(
        project_name=plan.project_name,
        assignments=assignments,
        unassigned_tasks=unassigned,
        is_fully_assigned=not unassigned,
    )


class EmployeeAssignmentService:
    """Load actual workforce data, then run the pure recommendation algorithm."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def recommend(self, plan: ProjectPlan) -> AssignmentResult:
        employees_by_id: dict[UUID, User] = {}
        departments = {task.department for task in plan.tasks}
        for department in sorted(departments, key=lambda value: value.value):
            employees = await self.user_repository.get_employees_by_department(department.value)
            for employee in employees:
                if employee.role == UserRole.EMPLOYEE and employee.is_active:
                    employees_by_id[employee.id] = employee

        workloads: dict[UUID, int] = {}
        unavailable: set[UUID] = set()
        for employee in employees_by_id.values():
            try:
                workload = await self.user_repository.get_user_workload(employee.id)
                if not isinstance(workload, int) or workload < 0:
                    unavailable.add(employee.id)
                else:
                    workloads[employee.id] = workload
            except Exception:
                # Preserve the fact that load failed; never silently treat it as zero.
                unavailable.add(employee.id)

        return recommend_assignments(plan, list(employees_by_id.values()), workloads, unavailable)

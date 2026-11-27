from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models.enums import Department, ProfessionalRole, ProjectStatus, TaskStatus, UserRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse

router = APIRouter()


async def _group_counts(session: AsyncSession, model, column, *conditions) -> dict[str, int]:
    result = await session.execute(select(column, func.count(model.id)).where(*conditions).group_by(column))
    return {str(key.value if hasattr(key, "value") else key): count for key, count in result.all() if key is not None}


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_roles([UserRole.ADMIN]))],
) -> AdminOverviewResponse:
    grouped_user_counts = await _group_counts(session, User, User.role)
    user_counts = {role.value: grouped_user_counts.get(role.value, 0) for role in UserRole}
    grouped_departments = await _group_counts(session, User, User.department, User.role == UserRole.EMPLOYEE)
    department_counts = {department.value: grouped_departments.get(department.value, 0) for department in Department}
    grouped_professional_roles = await _group_counts(session, User, User.professional_role, User.role == UserRole.EMPLOYEE)
    professional_counts = {role.value: grouped_professional_roles.get(role.value, 0) for role in ProfessionalRole}
    project_counts = await _group_counts(session, Project, Project.status)
    task_counts = await _group_counts(session, Task, Task.status)
    totals = await session.execute(
        select(
            func.count(User.id),
            func.sum(case((User.is_active.is_(True), 1), else_=0)),
        )
    )
    total_users, active_users = totals.one()
    return AdminOverviewResponse(
        total_users=total_users or 0,
        active_users=active_users or 0,
        inactive_users=(total_users or 0) - (active_users or 0),
        users_by_account_role=user_counts,
        employees_by_department=department_counts,
        employees_by_professional_role=professional_counts,
        total_projects=sum(project_counts.values()),
        projects_by_status=project_counts,
        total_tasks=sum(task_counts.values()),
        tasks_by_status=task_counts,
    )

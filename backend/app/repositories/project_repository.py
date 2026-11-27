import uuid
from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.task import Task
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def get_recent(self, skip: int = 0, limit: int = 50) -> Sequence[Project]:
        query = select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_manager(self, manager_id: uuid.UUID, skip: int = 0, limit: int = 50) -> Sequence[Project]:
        query = select(Project).where(Project.created_by == manager_id).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_employee_projects(self, employee_id: uuid.UUID, skip: int = 0, limit: int = 50) -> Sequence[Project]:
        """Get distinct projects where the employee has assigned tasks."""
        query = (
            select(Project)
            .join(Task, Task.project_id == Project.id)
            .where(Task.assigned_to == employee_id)
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_tasks(self, project_id: uuid.UUID) -> int:
        query = select(func.count(Task.id)).where(Task.project_id == project_id)
        result = await self.session.execute(query)
        return result.scalar_one()

import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TaskStatus
from app.models.task import Task, TaskDependency
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def get_by_id_with_deps(self, id: uuid.UUID) -> Task | None:
        query = (
            select(Task)
            .options(
                selectinload(Task.dependencies),
                selectinload(Task.prerequisite_for),
            )
            .where(Task.id == id)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_project_and_code(self, project_id: uuid.UUID, task_code: str) -> Task | None:
        query = select(Task).where(Task.project_id == project_id, Task.task_code == task_code)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_project_tasks(
        self,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        status: TaskStatus | None = None,
        assigned_to: uuid.UUID | None = None,
    ) -> Sequence[Task]:
        query = (
            select(Task)
            .options(selectinload(Task.dependencies))
            .where(Task.project_id == project_id)
        )
        if status:
            query = query.where(Task.status == status)
        if assigned_to:
            query = query.where(Task.assigned_to == assigned_to)
        query = query.offset(skip).limit(limit).order_by(Task.task_code)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_employee_tasks(
        self,
        employee_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        status: TaskStatus | None = None,
    ) -> Sequence[Task]:
        query = (
            select(Task)
            .options(selectinload(Task.dependencies))
            .where(Task.assigned_to == employee_id)
        )
        if status:
            query = query.where(Task.status == status)
        query = query.offset(skip).limit(limit).order_by(Task.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add_dependency(self, task_id: uuid.UUID, depends_on_task_id: uuid.UUID) -> TaskDependency:
        dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id)
        self.session.add(dep)
        await self.session.flush()
        return dep

    async def get_dependencies_for_task(self, task_id: uuid.UUID) -> Sequence[Task]:
        """Fetch full Task entities that this task depends on."""
        query = (
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
            .where(TaskDependency.task_id == task_id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_project_dependencies(self, project_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Fetch all (task_id, depends_on_task_id) pairs in a project for cycle detection."""
        query = (
            select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
            .join(Task, Task.id == TaskDependency.task_id)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

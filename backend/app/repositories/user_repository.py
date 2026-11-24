import uuid
from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(func.lower(User.email) == email.lower()))
        return result.scalars().first()

    async def get_user_workload(self, user_id: uuid.UUID) -> int:
        """Count active (non-completed and non-cancelled) tasks assigned to user."""
        query = select(func.count(Task.id)).where(
            Task.assigned_to == user_id,
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_employees_by_department(self, department: str) -> Sequence[User]:
        query = select(User).where(User.department == department, User.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalars().all()

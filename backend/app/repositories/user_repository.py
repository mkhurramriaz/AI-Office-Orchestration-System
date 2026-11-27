import uuid
from typing import Sequence
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.enums import UserRole
from app.models.task import Task
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(func.lower(User.email) == email.lower()))
        return result.scalars().first()

    async def list_admin_users(
        self, *, skip: int, limit: int, role=None, department=None,
        professional_role=None, is_active=None, search: str | None = None,
    ) -> tuple[Sequence[User], int]:
        filters = []
        if role is not None:
            filters.append(User.role == role)
        if department is not None:
            filters.append(User.department == department)
        if professional_role is not None:
            filters.append(User.professional_role == professional_role)
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        if search:
            term = f"%{search.strip()}%"
            filters.append(or_(User.full_name.ilike(term), User.email.ilike(term)))
        count_result = await self.session.execute(select(func.count(User.id)).where(*filters))
        result = await self.session.execute(
            select(User).where(*filters).order_by(User.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all(), count_result.scalar_one()

    async def get_admins_for_update(self) -> Sequence[User]:
        """Lock admin rows while enforcing last-admin protections on PostgreSQL."""
        result = await self.session.execute(
            select(User).where(User.role == UserRole.ADMIN).with_for_update()
        )
        return result.scalars().all()

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

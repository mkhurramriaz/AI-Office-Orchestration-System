import uuid
from typing import Sequence
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def create_user(self, user_in: UserCreate) -> User:
        """Create a user (Admin operation)."""
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        user = User(
            full_name=user_in.full_name,
            email=user_in.email.lower(),
            hashed_password=get_password_hash(user_in.password),
            role=user_in.role,
            department=user_in.department,
            job_title=user_in.job_title,
            is_active=user_in.is_active,
        )
        return await self.user_repo.create(user)

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 50,
        role: UserRole | None = None,
        department: str | None = None,
    ) -> tuple[Sequence[User], int]:
        filters = {}
        if role:
            filters["role"] = role
        if department:
            filters["department"] = department
        users = await self.user_repo.get_multi(skip=skip, limit=limit, **filters)
        total = await self.user_repo.count(**filters)
        return users, total

    async def update_user(self, user_id: uuid.UUID, user_in: UserUpdate, current_user: User) -> User:
        user = await self.get_by_id(user_id)

        # Non-admins can only update their own profile and cannot change role or active status
        if current_user.role != UserRole.ADMIN and current_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this user.")

        update_data = user_in.model_dump(exclude_unset=True)
        if "role" in update_data and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can modify roles.")
        if "is_active" in update_data and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can modify active status.")

        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        if "email" in update_data and update_data["email"]:
            new_email = update_data["email"].lower()
            if new_email != user.email:
                existing = await self.user_repo.get_by_email(new_email)
                if existing:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already taken.")
                update_data["email"] = new_email

        return await self.user_repo.update(user, **update_data)

    async def delete_user(self, user_id: uuid.UUID, current_user: User) -> None:
        """Deactivate or delete user (Admin operation)."""
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
        if current_user.id == user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own admin account.")
        user = await self.get_by_id(user_id)
        await self.user_repo.delete(user)

    async def get_user_workload(self, user_id: uuid.UUID) -> int:
        return await self.user_repo.get_user_workload(user_id)

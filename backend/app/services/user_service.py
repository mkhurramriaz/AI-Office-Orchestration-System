import uuid
from typing import Sequence
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.enums import ProfessionalRole, UserRole
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
            professional_role=user_in.professional_role,
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
        professional_role: ProfessionalRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[User], int]:
        return await self.user_repo.list_admin_users(
            skip=skip, limit=limit, role=role, department=department,
            professional_role=professional_role, is_active=is_active, search=search,
        )

    async def _ensure_admin_remains(self, target: User, update_data: dict) -> None:
        removes_admin = target.role == UserRole.ADMIN and (
            update_data.get("role", target.role) != UserRole.ADMIN
            or update_data.get("is_active", target.is_active) is False
        )
        if removes_admin:
            admins = await self.user_repo.get_admins_for_update()
            active_admins_after = sum(
                1 for admin in admins
                if (
                    admin.id != target.id and admin.is_active
                ) or (
                    admin.id == target.id
                    and update_data.get("role", admin.role) == UserRole.ADMIN
                    and update_data.get("is_active", admin.is_active) is True
                )
            )
            if active_admins_after < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The last administrator cannot be demoted or deactivated.",
                )

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
        if current_user.role == UserRole.ADMIN:
            await self._ensure_admin_remains(user, update_data)

        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        if "email" in update_data and update_data["email"]:
            new_email = update_data["email"].lower()
            if new_email != user.email:
                existing = await self.user_repo.get_by_email(new_email)
                if existing:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already taken.")
                update_data["email"] = new_email

        clearable_fields = {"professional_role", "job_title"}
        explicit_clears = {
            key for key in clearable_fields
            if key in update_data and update_data[key] is None
        }
        for key in explicit_clears:
            update_data.pop(key)
            setattr(user, key, None)
        updated = await self.user_repo.update(user, **update_data)
        if explicit_clears:
            await self.session.flush()
        return updated

    async def delete_user(self, user_id: uuid.UUID, current_user: User) -> None:
        """Deactivate or delete user (Admin operation)."""
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
        if current_user.id == user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own admin account.")
        user = await self.get_by_id(user_id)
        if user.role == UserRole.ADMIN:
            admins = await self.user_repo.get_admins_for_update()
            active_admins_after = sum(1 for admin in admins if admin.id != user.id and admin.is_active)
            if user.is_active and active_admins_after < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The last administrator cannot be deleted.",
                )
        await self.user_repo.delete(user)

    async def get_user_workload(self, user_id: uuid.UUID) -> int:
        return await self.user_repo.get_user_workload(user_id)

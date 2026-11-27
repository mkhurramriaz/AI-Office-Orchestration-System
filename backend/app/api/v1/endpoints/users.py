import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.enums import Department, ProfessionalRole, UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List Users",
    description="Retrieve users. Restricted to Managers and Administrators.",
)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER]))],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: UserRole | None = None,
    department: Department | None = None,
    professional_role: ProfessionalRole | None = None,
    is_active: bool | None = None,
    search: str | None = Query(None, min_length=1, max_length=255),
) -> PaginatedResponse[UserResponse]:
    skip = (page - 1) * size
    user_service = UserService(session)
    users, total = await user_service.list_users(
        skip=skip, limit=size, role=role, department=department,
        professional_role=professional_role, is_active=is_active, search=search,
    )
    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User (Admin only)",
    description="Provision a new user account with any assigned role.",
)
async def create_user(
    user_in: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.ADMIN]))],
) -> UserResponse:
    user_service = UserService(session)
    user = await user_service.create_user(user_in)
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User by ID",
)
async def get_user_by_id(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
)
async def update_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    user_service = UserService(session)
    user = await user_service.update_user(user_id, user_in, current_user)
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User (Admin only)",
)
async def delete_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([UserRole.ADMIN]))],
) -> None:
    user_service = UserService(session)
    await user_service.delete_user(user_id, current_user)

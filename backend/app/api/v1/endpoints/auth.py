from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, Token
from app.schemas.user import UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Register an account. By default, public registration creates EMPLOYEE or MANAGER accounts.",
)
async def register(
    user_in: UserRegister,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    auth_service = AuthService(session)
    user = await auth_service.register(user_in)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate with email and password to receive JWT access and refresh tokens.",
)
async def login(
    login_in: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    auth_service = AuthService(session)
    return await auth_service.login(login_in)


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Submit a valid refresh token to obtain a new pair of access and refresh tokens.",
)
async def refresh_token(
    refresh_in: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    auth_service = AuthService(session)
    return await auth_service.refresh(refresh_in)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current User Profile",
    description="Retrieve the profile details of the currently authenticated user.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)

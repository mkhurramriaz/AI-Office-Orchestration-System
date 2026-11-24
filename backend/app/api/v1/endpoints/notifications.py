import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Notifications",
    description="Retrieve notifications for the current authenticated user.",
)
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[NotificationResponse]:
    skip = (page - 1) * size
    service = NotificationService(session)
    notifications = await service.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=size,
        unread_only=unread_only,
    )
    items = [NotificationResponse.model_validate(n) for n in notifications]
    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        size=size,
        pages=1,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Notification as Read",
)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    service = NotificationService(session)
    notification = await service.mark_as_read(notification_id, current_user.id)
    return NotificationResponse.model_validate(notification)

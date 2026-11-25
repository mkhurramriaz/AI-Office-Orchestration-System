import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Notification, session)

    async def create_notification(
        self,
        recipient_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM,
    ) -> Notification:
        notification = Notification(
            recipient_id=recipient_id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=False,
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_by_user(
        self,
        recipient_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> Sequence[Notification]:
        query = select(Notification).where(Notification.recipient_id == recipient_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def mark_as_read(self, notification_id: uuid.UUID, recipient_id: uuid.UUID) -> Notification | None:
        notification = await self.get_by_id(notification_id)
        if notification and notification.recipient_id == recipient_id:
            notification.is_read = True
            await self.session.flush()
            return notification
        return None

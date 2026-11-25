import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_id: uuid.UUID
    title: str
    message: str
    notification_type: NotificationType
    is_read: bool
    created_at: datetime

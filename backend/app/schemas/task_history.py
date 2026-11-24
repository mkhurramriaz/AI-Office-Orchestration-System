import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.enums import ActorType


class TaskHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_type: ActorType
    action: str
    old_status: str | None = None
    new_status: str | None = None
    description: str | None = None
    created_at: datetime

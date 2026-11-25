import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ActorType
from app.models.task_history import TaskHistory


class TaskHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        task_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID | None = None,
        actor_type: ActorType = ActorType.HUMAN,
        old_status: str | None = None,
        new_status: str | None = None,
        description: str | None = None,
    ) -> TaskHistory:
        """Create an append-only task history record."""
        history = TaskHistory(
            task_id=task_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            old_status=old_status,
            new_status=new_status,
            description=description,
        )
        self.session.add(history)
        await self.session.flush()
        return history

    async def get_by_task_id(self, task_id: uuid.UUID, skip: int = 0, limit: int = 50) -> Sequence[TaskHistory]:
        query = (
            select(TaskHistory)
            .where(TaskHistory.task_id == task_id)
            .order_by(TaskHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

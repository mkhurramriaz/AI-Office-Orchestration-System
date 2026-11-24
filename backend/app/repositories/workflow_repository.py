import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkflowStatus
from app.models.workflow import WorkflowExecution
from app.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[WorkflowExecution]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WorkflowExecution, session)

    async def get_by_thread_id(self, thread_id: str) -> WorkflowExecution | None:
        query = select(WorkflowExecution).where(WorkflowExecution.thread_id == thread_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def update_status(
        self,
        execution: WorkflowExecution,
        status: WorkflowStatus,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> WorkflowExecution:
        execution.status = status
        if output_data is not None:
            execution.output_data = output_data
        if error_message is not None:
            execution.error_message = error_message
        await self.session.flush()
        return execution

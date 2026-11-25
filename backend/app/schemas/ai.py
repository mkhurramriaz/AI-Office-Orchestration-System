"""Request and response schemas for the AI co-pilot API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return value.strip()


class ChatSource(BaseModel):
    source: str
    content: str
    metadata: dict[str, Any]
    relevance_score: float


class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    sources: list[ChatSource]

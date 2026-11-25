"""Authenticated AI co-pilot endpoint."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.rag.chat_service import GenerationError, RAGChatService, RetrievalError
from app.schemas.ai import ChatRequest, ChatResponse

router = APIRouter()


def get_chat_service() -> RAGChatService:
    """Dependency factory, overridable by tests and deployment integrations."""
    return RAGChatService()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the AI co-pilot a document-grounded question",
)
async def chat(
    request: ChatRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[RAGChatService, Depends(get_chat_service)],
) -> ChatResponse:
    if not request.question or len(request.question) > 4000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Question must contain 1 to 4000 characters.",
        )
    if request.conversation_id is not None:
        try:
            conversation_id = UUID(request.conversation_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="conversation_id must be a valid UUID.",
            ) from None
    else:
        conversation_id = uuid4()
    try:
        result = await chat_service.answer(request.question, request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    except RetrievalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval is temporarily unavailable.",
        ) from None
    except GenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service could not generate a response.",
        ) from None

    return ChatResponse(
        conversation_id=conversation_id,
        answer=result["answer"],
        sources=result["sources"],
    )

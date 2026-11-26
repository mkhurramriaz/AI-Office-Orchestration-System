"""Authenticated AI co-pilot endpoint."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.rag.chat_service import GenerationError, RAGChatService, RetrievalError
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.project_plan import ProjectPlan, ProjectPlanRequest
from app.services.project_planner import (
    PlanGenerationError,
    PlanValidationError,
    ProjectPlannerService,
)

router = APIRouter()


def get_chat_service() -> RAGChatService:
    """Dependency factory, overridable by tests and deployment integrations."""
    return RAGChatService()


def get_project_planner_service() -> ProjectPlannerService:
    """Dependency factory for the ephemeral project planning workflow."""
    return ProjectPlannerService()


@router.post(
    "/plan",
    response_model=ProjectPlan,
    summary="Generate a validated project plan",
    description="Creates an AI-generated plan only; it does not persist projects, tasks, or assignments.",
)
async def plan_project(
    request: ProjectPlanRequest,
    _current_user: Annotated[
        User,
        Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN])),
    ],
    planner: Annotated[ProjectPlannerService, Depends(get_project_planner_service)],
) -> ProjectPlan:
    if not request.project_brief or len(request.project_brief) > 10000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project brief must contain 1 to 10000 characters.",
        )
    try:
        return await planner.create_plan(request.project_brief)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except PlanValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI generated a project plan that failed validation.",
        ) from None
    except PlanGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The planning service is temporarily unavailable.",
        ) from None


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

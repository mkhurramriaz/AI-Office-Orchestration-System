"""Phase 3B retrieval and authenticated AI co-pilot tests (all providers mocked)."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import AsyncClient
from langchain_core.documents import Document

from app.api.v1.endpoints.ai import get_chat_service
from app.main import app
from app.rag.chat_service import (
    NO_CONTEXT_ANSWER,
    GenerationError,
    RAGChatService,
    RetrievalError,
    generate_grounded_answer,
)
from app.rag.retrieval import retrieve_documents
from tests.conftest import get_token_headers


def test_retrieval_uses_persistent_store_and_filters_low_relevance():
    embedding = MagicMock()
    store = MagicMock()
    store.similarity_search_with_relevance_scores.return_value = [
        (
            Document(
                page_content="Leave policy details.",
                metadata={
                    "source": "Data/documents/hr/leave.md",
                    "file_hash": "private-index-hash",
                    "title": "Leave Policy",
                },
            ),
            0.91,
        ),
        (Document(page_content="Irrelevant", metadata={"source": "other.txt"}), 0.1),
    ]

    with (
        patch("app.rag.retrieval.get_query_embedding_function", return_value=embedding),
        patch("app.rag.retrieval.get_vector_store", return_value=store) as get_store,
    ):
        results = retrieve_documents("annual leave", top_k=6)

    get_store.assert_called_once_with(embedding)
    store.similarity_search_with_relevance_scores.assert_called_once_with("annual leave", k=6)
    assert results == [
        {
            "content": "Leave policy details.",
            "source": "Data/documents/hr/leave.md",
            "metadata": {
                "source": "Data/documents/hr/leave.md",
                "title": "Leave Policy",
            },
            "relevance_score": 0.91,
        }
    ]


def test_retrieval_rejects_invalid_top_k():
    with pytest.raises(ValueError, match="top_k"):
        retrieve_documents("question", top_k=21)


@pytest.mark.asyncio
async def test_chat_generates_answer_from_context_and_returns_sources():
    sources = [
        {
            "source": "Data/documents/hr/leave.md",
            "content": "Employees receive 20 days of leave.",
            "metadata": {"title": "Leave Policy"},
            "relevance_score": 0.9,
        }
    ]
    retriever = MagicMock(return_value=sources)
    generator = AsyncMock(return_value="The policy grants 20 days of leave.")

    result = await RAGChatService(retriever, generator).answer("How much leave?", top_k=3)

    assert "The policy grants 20 days" in result["answer"]
    assert "Sources: Data/documents/hr/leave.md" in result["answer"]
    assert result["sources"] == sources
    generator.assert_awaited_once_with("How much leave?", sources)


@pytest.mark.asyncio
async def test_empty_retrieval_returns_insufficient_context_without_llm_call():
    generator = AsyncMock()
    result = await RAGChatService(MagicMock(return_value=[]), generator).answer("Unknown question")

    assert result == {"answer": NO_CONTEXT_ANSWER, "sources": []}
    generator.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieval_and_generation_errors_are_sanitized():
    with pytest.raises(RetrievalError, match="temporarily unavailable"):
        await RAGChatService(MagicMock(side_effect=RuntimeError("internal details"))).answer("question")

    with pytest.raises(GenerationError, match="could not generate"):
        await RAGChatService(
            MagicMock(return_value=[{"source": "doc.md", "content": "text"}]),
            AsyncMock(side_effect=RuntimeError("provider detail")),
        ).answer("question")


@pytest.mark.asyncio
async def test_groq_generation_sends_grounded_context_without_exposing_credentials():
    settings = MagicMock(
        DEFAULT_LLM_PROVIDER="groq",
        DEFAULT_LLM_MODEL="configured-chat-model",
        GROQ_API_KEY="test-only-secret",
    )
    client = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "The policy grants 20 days."}}]
    }
    client.post = AsyncMock(return_value=response)
    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(return_value=client)
    client_context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.rag.chat_service.get_settings", return_value=settings),
        patch("app.rag.chat_service.httpx.AsyncClient", return_value=client_context),
    ):
        answer = await generate_grounded_answer(
            "How much leave?",
            [{"source": "hr/leave.md", "content": "20 days", "metadata": {}}],
        )

    assert answer == "The policy grants 20 days."
    kwargs = client.post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer test-only-secret"
    assert kwargs["json"]["model"] == "configured-chat-model"
    assert "[Source: hr/leave.md]\n20 days" in kwargs["json"]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_groq_errors_return_generic_generation_error():
    settings = MagicMock(
        DEFAULT_LLM_PROVIDER="groq",
        DEFAULT_LLM_MODEL="configured-chat-model",
        GROQ_API_KEY="test-only-secret",
    )
    client = MagicMock()
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.ConnectError("provider detail")
    client.post = AsyncMock(return_value=response)
    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(return_value=client)
    client_context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.rag.chat_service.get_settings", return_value=settings),
        patch("app.rag.chat_service.httpx.AsyncClient", return_value=client_context),
    ):
        with pytest.raises(GenerationError, match="could not generate") as exc:
            await generate_grounded_answer("Question", [{"source": "doc", "content": "text"}])

    assert "provider detail" not in str(exc.value)
    assert "test-only-secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_chat_endpoint_requires_authentication(async_client: AsyncClient):
    response = await async_client.post("/api/v1/ai/chat", json={"question": "What is the policy?"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_chat_endpoint_returns_grounded_response(async_client, employee_user):
    conversation_id = uuid4()
    fake_service = MagicMock()
    fake_service.answer = AsyncMock(
        return_value={
            "answer": "The policy grants 20 days.\n\nSources: hr/leave.md",
            "sources": [
                {
                    "source": "hr/leave.md",
                    "content": "20 days",
                    "metadata": {"title": "Leave"},
                    "relevance_score": 0.9,
                }
            ],
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: fake_service
    try:
        response = await async_client.post(
            "/api/v1/ai/chat",
            headers=get_token_headers(employee_user),
            json={"question": "How much leave?", "conversation_id": str(conversation_id), "top_k": 3},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == str(conversation_id)
    assert payload["answer"].startswith("The policy grants 20 days")
    assert payload["sources"][0]["source"] == "hr/leave.md"
    fake_service.answer.assert_awaited_once_with("How much leave?", 3)


@pytest.mark.asyncio
async def test_chat_endpoint_rejects_blank_question(async_client, employee_user):
    response = await async_client.post(
        "/api/v1/ai/chat",
        headers=get_token_headers(employee_user),
        json={"question": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_endpoint_rejects_invalid_conversation_id(async_client, employee_user):
    response = await async_client.post(
        "/api/v1/ai/chat",
        headers=get_token_headers(employee_user),
        json={"question": "Question?", "conversation_id": "not-a-uuid"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "public_message"),
    [
        (RetrievalError("secret retrieval detail"), 503, "Document retrieval is temporarily unavailable."),
        (GenerationError("secret provider detail"), 502, "The AI service could not generate a response."),
    ],
)
async def test_chat_endpoint_maps_service_errors_safely(
    async_client, employee_user, error, status_code, public_message
):
    fake_service = MagicMock()
    fake_service.answer = AsyncMock(side_effect=error)
    app.dependency_overrides[get_chat_service] = lambda: fake_service
    try:
        response = await async_client.post(
            "/api/v1/ai/chat",
            headers=get_token_headers(employee_user),
            json={"question": "Question?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == status_code
    assert response.json()["error"]["message"] == public_message
    assert "secret" not in response.text

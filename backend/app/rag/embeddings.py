"""
TaskFlow AI — Embeddings Factory

Creates and caches a LangChain-compatible embedding model backed by the
Google Gemini Embeddings API.  API key is read exclusively from application
settings — never hard-coded.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Model used for all document and query embeddings.
# text-embedding-004 is Google's current best-in-class embedding model.
GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"


@lru_cache(maxsize=1)
def get_embedding_function() -> GoogleGenerativeAIEmbeddings:
    """
    Return a cached instance of the Gemini embedding function.

    The instance is constructed once per process lifetime (lru_cache with
    maxsize=1).  Uses the GEMINI_API_KEY from application settings.

    Raises
    ------
    ValueError
        If GEMINI_API_KEY is not configured in the environment.
    """
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Add it to the root .env file before running ingestion."
        )

    logger.info("Initialising Gemini embedding model: %s", GEMINI_EMBEDDING_MODEL)
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        task_type="retrieval_document",  # optimise embeddings for retrieval
    )


@lru_cache(maxsize=1)
def get_query_embedding_function() -> GoogleGenerativeAIEmbeddings:
    """Return the Gemini embedding client configured for retrieval queries."""
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured for document retrieval.")
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        task_type="retrieval_query",
    )

"""Semantic retrieval helpers for the persistent TaskFlow Chroma collection."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.rag.embeddings import get_query_embedding_function
from app.rag.vector_store import get_vector_store


def retrieve_documents(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """Return the most relevant indexed chunks with their source metadata."""
    if not query or not query.strip():
        raise ValueError("Question must not be empty.")

    settings = get_settings()
    result_limit = top_k if top_k is not None else settings.RAG_TOP_K
    if not 1 <= result_limit <= 20:
        raise ValueError("top_k must be between 1 and 20.")

    store = get_vector_store(get_query_embedding_function())
    matches = store.similarity_search_with_relevance_scores(query.strip(), k=result_limit)

    results: list[dict[str, Any]] = []
    for document, score in matches:
        relevance = float(score)
        if relevance < settings.RAG_MIN_RELEVANCE_SCORE:
            continue
        metadata = dict(document.metadata or {})
        source = metadata.get("source") or metadata.get("source_path") or "unknown"
        # Hashes are indexing internals and aren't useful to chat clients.
        metadata.pop("file_hash", None)
        metadata["source"] = source
        results.append(
            {
                "content": document.page_content,
                "source": source,
                "metadata": metadata,
                "relevance_score": relevance,
            }
        )
    return results

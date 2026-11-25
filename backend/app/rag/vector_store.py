"""
TaskFlow AI — ChromaDB Vector Store Manager

Provides a thin wrapper around langchain-chroma that handles:
  - Persistent collection creation / retrieval.
  - Duplicate detection by file hash (avoids re-embedding unchanged files).
  - Atomic upsert: delete existing chunks for a source → add new chunks.
  - Collection stats queries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Single collection name for the TaskFlow AI knowledge base
COLLECTION_NAME: str = "taskflow_documents"


def get_vector_store(
    embedding_function: Embeddings,
    persist_directory: str | None = None,
    collection_name: str = COLLECTION_NAME,
) -> Chroma:
    """
    Return a persistent Chroma vector store.

    Parameters
    ----------
    embedding_function:
        LangChain-compatible embedding model.
    persist_directory:
        Path on disk where ChromaDB will persist its SQLite + data files.
        Defaults to ``settings.CHROMA_PERSIST_DIRECTORY``.
    collection_name:
        Name of the ChromaDB collection (default: ``taskflow_documents``).
    """
    settings = get_settings()
    directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY

    # Resolve relative paths from the project root (two levels above backend/)
    path = Path(directory)
    if not path.is_absolute():
        # When running from backend/, step up to repo root
        path = Path(__file__).resolve().parents[3] / directory.lstrip("./")

    path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Opening ChromaDB collection '%s' at: %s",
        collection_name,
        path,
    )
    return Chroma(
        collection_name=collection_name,
        embedding_function=embedding_function,
        persist_directory=str(path),
    )


def get_indexed_hashes(vector_store: Chroma) -> dict[str, str]:
    """
    Return a mapping of ``{source_filename: file_hash}`` for every document
    currently stored in the collection.

    Used by the ingestion service to skip files that haven't changed.
    """
    try:
        result = vector_store.get(include=["metadatas"])
        hashes: dict[str, str] = {}
        for meta in result.get("metadatas") or []:
            if meta and "source" in meta and "file_hash" in meta:
                hashes[meta["source"]] = meta["file_hash"]
        return hashes
    except Exception as exc:
        logger.warning("Could not read existing hashes from ChromaDB: %s", exc)
        return {}


def get_source_chunk_ids(vector_store: Chroma, source: str) -> list[str]:
    """Return the IDs currently indexed for one normalized source path."""
    result = vector_store.get(where={"source": source}, include=["metadatas"])
    return result.get("ids") or []


def delete_source(
    vector_store: Chroma,
    source_filename: str,
    chunk_ids: list[str] | None = None,
) -> int:
    """
    Delete all chunks whose ``source`` metadata field equals *source_filename*.

    Returns the number of chunks deleted.
    """
    ids = chunk_ids if chunk_ids is not None else get_source_chunk_ids(vector_store, source_filename)
    if ids:
        vector_store.delete(ids=ids)
        logger.info(
            "Deleted %d existing chunk(s) for source: %s",
            len(ids),
            source_filename,
        )
    return len(ids)


def add_chunks(
    vector_store: Chroma,
    chunks: list[Document],
) -> list[str]:
    """
    Add *chunks* to the vector store and return their assigned IDs.

    ChromaDB will embed each chunk using the collection's embedding function.
    """
    if not chunks:
        return []
    ids = vector_store.add_documents(chunks)
    logger.info("Added %d chunk(s) to ChromaDB.", len(ids))
    return ids


def get_collection_stats(vector_store: Chroma) -> dict[str, Any]:
    """
    Return basic statistics about the current collection.

    Returns
    -------
    dict with keys:
        total_chunks      : int
        unique_sources    : int
        source_breakdown  : dict[str, int]  (filename → chunk count)
    """
    try:
        result = vector_store.get(include=["metadatas"])
        metadatas = result.get("metadatas") or []
        source_counts: dict[str, int] = {}
        for meta in metadatas:
            if meta:
                src = meta.get("source", "unknown")
                source_counts[src] = source_counts.get(src, 0) + 1

        return {
            "total_chunks": len(metadatas),
            "unique_sources": len(source_counts),
            "source_breakdown": source_counts,
        }
    except Exception as exc:
        logger.error("Error fetching collection stats: %s", exc)
        return {"total_chunks": 0, "unique_sources": 0, "source_breakdown": {}}

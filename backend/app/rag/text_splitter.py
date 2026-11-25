"""
TaskFlow AI — Text Splitter

Wraps LangChain's RecursiveCharacterTextSplitter with project-wide defaults
and chunk-level metadata enrichment (chunk index, total chunks per source).
"""

from __future__ import annotations

import logging
from typing import Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Project defaults — override via constructor kwargs or environment settings
DEFAULT_CHUNK_SIZE: int = 1000
DEFAULT_CHUNK_OVERLAP: int = 200
DEFAULT_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]


def build_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> RecursiveCharacterTextSplitter:
    """
    Construct a RecursiveCharacterTextSplitter with the given parameters.

    Parameters
    ----------
    chunk_size:
        Maximum character count per chunk (default 1000).
    chunk_overlap:
        Number of characters each consecutive chunk shares with its predecessor
        (default 200).  Maintains sentence context across chunk boundaries.
    separators:
        Ordered list of separator strings tried when splitting. Falls through
        to the next separator when the current one would exceed chunk_size.
    """
    if separators is None:
        separators = DEFAULT_SEPARATORS

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False,
        add_start_index=True,  # adds 'start_index' to metadata for exact location tracking
    )


def split_documents(
    documents: Sequence[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[Document]:
    """
    Split a list of Documents into chunks and enrich each chunk's metadata.

    Added metadata fields per chunk
    --------------------------------
    chunk_index   : 0-based position of this chunk within its source file.
    total_chunks  : Total number of chunks produced from the same source file.
    chunk_size    : The configured chunk_size used for this split.
    chunk_overlap : The configured overlap used.

    Parameters
    ----------
    documents:
        Raw documents returned by the document loaders.
    chunk_size / chunk_overlap / separators:
        Forwarded to :func:`build_splitter`.
    """
    splitter = build_splitter(chunk_size, chunk_overlap, separators)
    chunks = splitter.split_documents(list(documents))

    # Group chunks by source file so we can record chunk_index / total_chunks
    source_counters: dict[str, int] = {}
    source_totals: dict[str, int] = {}

    # First pass — count totals per source
    for chunk in chunks:
        src = chunk.metadata.get("source", "unknown")
        source_totals[src] = source_totals.get(src, 0) + 1

    # Second pass — assign index and totals
    for chunk in chunks:
        src = chunk.metadata.get("source", "unknown")
        idx = source_counters.get(src, 0)
        source_counters[src] = idx + 1
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["total_chunks"] = source_totals[src]
        chunk.metadata["chunk_size"] = chunk_size
        chunk.metadata["chunk_overlap"] = chunk_overlap

    logger.info(
        "Split %d document(s) into %d chunk(s) "
        "(chunk_size=%d, overlap=%d)",
        len(documents),
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks

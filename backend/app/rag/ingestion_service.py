"""
TaskFlow AI — Document Ingestion Service

Orchestrates the full ingestion pipeline:

  1. Discover documents in the configured directory.
  2. Load raw documents with source metadata.
  3. Split into overlapping chunks.
  4. Compute file hashes and compare against the existing ChromaDB index.
  5. Skip unchanged files, delete-then-re-add changed/new files.
  6. Return a structured IngestionReport.

Designed to be called from the CLI script, a FastAPI background task,
or a Celery worker — no FastAPI-specific imports here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from app.core.config import get_settings
from app.rag.document_loader import (
    REPOSITORY_ROOT,
    discover_documents,
    load_document,
    repository_relative_path,
)
from app.rag.text_splitter import split_documents
from app.rag.vector_store import (
    add_chunks,
    delete_source,
    get_collection_stats,
    get_indexed_hashes,
    get_vector_store,
    get_source_chunk_ids,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FileIngestionResult:
    """Result of processing a single file."""

    filename: str
    status: str  # "added" | "updated" | "skipped" | "failed"
    chunks_added: int = 0
    chunks_deleted: int = 0
    error: str | None = None


@dataclass
class IngestionReport:
    """Aggregate result of a full ingestion run."""

    files_discovered: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    total_chunks_added: int = 0
    total_chunks_deleted: int = 0
    file_results: list[FileIngestionResult] = field(default_factory=list)
    collection_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_discovered": self.files_discovered,
            "files_added": self.files_added,
            "files_updated": self.files_updated,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "total_chunks_added": self.total_chunks_added,
            "total_chunks_deleted": self.total_chunks_deleted,
            "collection_stats": self.collection_stats,
            "file_results": [
                {
                    "filename": r.filename,
                    "status": r.status,
                    "chunks_added": r.chunks_added,
                    "chunks_deleted": r.chunks_deleted,
                    "error": r.error,
                }
                for r in self.file_results
            ],
        }


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


class IngestionService:
    """
    Reusable document ingestion service.

    Parameters
    ----------
    embedding_function:
        LangChain-compatible Embeddings instance. Injected so callers can
        pass a mock in tests without touching the real Gemini API.
    documents_directory:
        Path to the folder containing source documents.  Defaults to
        ``settings.DOCUMENTS_DIRECTORY``.
    chroma_persist_directory:
        Path where ChromaDB persists data.  Defaults to
        ``settings.CHROMA_PERSIST_DIRECTORY``.
    chunk_size / chunk_overlap:
        Text splitter parameters.
    force_reindex:
        When True, all files are re-embedded regardless of their hash.
    """

    def __init__(
        self,
        embedding_function: Embeddings,
        documents_directory: str | None = None,
        chroma_persist_directory: str | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        force_reindex: bool = False,
    ) -> None:
        settings = get_settings()
        self._embedding_function = embedding_function
        docs_path = Path(documents_directory or settings.DOCUMENTS_DIRECTORY)
        self._documents_directory = str(
            docs_path if docs_path.is_absolute() else REPOSITORY_ROOT / docs_path
        )
        self._chroma_directory = chroma_persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._force_reindex = force_reindex

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self) -> IngestionReport:
        """
        Run the full ingestion pipeline and return a structured report.

        Pipeline
        --------
        1. Discover all supported files in the documents directory.
        2. Open (or create) the ChromaDB collection.
        3. Load existing file-hash index from ChromaDB.
        4. For each discovered file:
           a. Skip if hash unchanged (unless force_reindex).
           b. Delete existing chunks if the file was previously indexed.
           c. Load → split → embed → store new chunks.
        5. Query final collection stats.
        6. Return IngestionReport.
        """
        report = IngestionReport()

        # Step 1: discover
        paths = discover_documents(self._documents_directory)
        report.files_discovered = len(paths)
        logger.info("Starting ingestion — %d file(s) discovered.", len(paths))

        if not paths:
            logger.warning(
                "No documents found in '%s'. "
                "Add PDF, TXT, or Markdown files and re-run.",
                self._documents_directory,
            )
            return report

        # Step 2: open vector store
        vector_store = get_vector_store(
            embedding_function=self._embedding_function,
            persist_directory=self._chroma_directory,
        )

        # Step 3: existing hash index
        existing_hashes: dict[str, str] = get_indexed_hashes(vector_store)

        # Step 4: process each file
        for path in paths:
            result = self._process_file(path, vector_store, existing_hashes)
            report.file_results.append(result)

            if result.status == "added":
                report.files_added += 1
            elif result.status == "updated":
                report.files_updated += 1
            elif result.status == "skipped":
                report.files_skipped += 1
            elif result.status == "failed":
                report.files_failed += 1

            report.total_chunks_added += result.chunks_added
            report.total_chunks_deleted += result.chunks_deleted

        # Step 5: final stats
        report.collection_stats = get_collection_stats(vector_store)

        logger.info(
            "Ingestion complete — added=%d updated=%d skipped=%d failed=%d "
            "total_chunks=%d",
            report.files_added,
            report.files_updated,
            report.files_skipped,
            report.files_failed,
            report.total_chunks_added,
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_file(
        self,
        path: Path,
        vector_store: Any,
        existing_hashes: dict[str, str],
    ) -> FileIngestionResult:
        """Process a single file and return its ingestion result."""
        filename = repository_relative_path(path)
        added_ids: list[str] = []
        try:
            # Load document(s) — also computes file_hash in metadata
            raw_docs = load_document(path)
            if not raw_docs:
                return FileIngestionResult(filename=filename, status="failed", error="No content loaded")

            current_hash: str = raw_docs[0].metadata.get("file_hash", "")
            source_id: str = raw_docs[0].metadata["source"]
            stored_hash: str = existing_hashes.get(source_id, "")

            # --- Duplicate / unchanged check ---
            if stored_hash and stored_hash == current_hash and not self._force_reindex:
                logger.debug("Skipping unchanged file: %s", filename)
                return FileIngestionResult(filename=filename, status="skipped")

            # Determine whether this is an update (file existed before)
            is_update = bool(stored_hash)

            # Split
            chunks = split_documents(
                raw_docs,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )

            # Snapshot the old IDs before insertion so replacement cleanup
            # cannot match and remove the new chunks with the same source.
            old_chunk_ids = (
                get_source_chunk_ids(vector_store, source_id) if is_update else []
            )

            # Embed + store
            added_ids = add_chunks(vector_store, chunks)
            if len(added_ids) != len(chunks):
                raise RuntimeError(
                    f"Expected {len(chunks)} stored chunk IDs, got {len(added_ids)}"
                )

            # Only replace the old source after the complete new set is stored.
            deleted = 0
            if is_update:
                deleted = delete_source(vector_store, source_id, chunk_ids=old_chunk_ids)

            status = "updated" if is_update else "added"
            logger.info(
                "[%s] %s — %d chunk(s) added, %d deleted.",
                status.upper(),
                filename,
                len(chunks),
                deleted,
            )
            return FileIngestionResult(
                filename=filename,
                status=status,
                chunks_added=len(chunks),
                chunks_deleted=deleted,
            )

        except Exception as exc:
            # A backend may raise after inserting some new chunks. Remove any
            # IDs it returned, while leaving the previous source untouched.
            if added_ids:
                try:
                    vector_store.delete(ids=added_ids)
                except Exception:
                    logger.exception("Could not clean up replacement chunks for '%s'.", filename)
            logger.error("Failed to ingest '%s': %s", filename, exc, exc_info=True)
            return FileIngestionResult(filename=filename, status="failed", error=str(exc))

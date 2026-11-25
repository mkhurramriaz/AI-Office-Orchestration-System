#!/usr/bin/env python3
"""
TaskFlow AI — Document Ingestion CLI Script

Usage (from the backend/ directory):

    # Ingest documents using the real Gemini API:
    python scripts/ingest_documents.py

    # Force re-index all files (even unchanged ones):
    python scripts/ingest_documents.py --force

    # Custom chunk size / overlap:
    python scripts/ingest_documents.py --chunk-size 800 --chunk-overlap 150

    # Point to a different documents directory:
    python scripts/ingest_documents.py --docs-dir /path/to/docs

    # Show current collection stats without ingesting:
    python scripts/ingest_documents.py --stats-only

Environment:
    GEMINI_API_KEY must be set in the root .env file (or as an env var).
    CHROMA_PERSIST_DIRECTORY / DOCUMENTS_DIRECTORY are read from settings.

Exit codes:
    0 — success (even if some files were skipped or zero files found)
    1 — partial failure (some files failed to ingest)
    2 — fatal error (environment misconfiguration, etc.)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the backend package is importable when the script is run directly
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ---------------------------------------------------------------------------
# Imports — after sys.path manipulation
# ---------------------------------------------------------------------------
from app.core.config import get_settings  # noqa: E402
from app.rag.embeddings import get_embedding_function  # noqa: E402
from app.rag.ingestion_service import IngestionService  # noqa: E402
from app.rag.vector_store import get_collection_stats, get_vector_store  # noqa: E402

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("taskflow.ingest")


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest_documents",
        description="TaskFlow AI — ingest company documents into ChromaDB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    settings = get_settings()

    parser.add_argument(
        "--docs-dir",
        default=settings.DOCUMENTS_DIRECTORY,
        help="Directory containing source documents (PDF, TXT, Markdown).",
    )
    parser.add_argument(
        "--chroma-dir",
        default=settings.CHROMA_PERSIST_DIRECTORY,
        help="Directory where ChromaDB persists its data.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum character count per text chunk.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Character overlap between consecutive chunks.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-embedding of all files, ignoring hash cache.",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        default=False,
        help="Print collection statistics without running ingestion.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        default=False,
        help="Output the ingestion report as JSON (useful for scripting).",
    )
    return parser


# ---------------------------------------------------------------------------
# Stats-only mode
# ---------------------------------------------------------------------------

def print_stats(chroma_dir: str) -> None:
    logger.info("Fetching collection statistics…")
    try:
        embedding_fn = get_embedding_function()
        store = get_vector_store(embedding_fn, persist_directory=chroma_dir)
        stats = get_collection_stats(store)
    except Exception as exc:
        logger.error("Could not fetch stats: %s", exc)
        sys.exit(2)

    print("\n── ChromaDB Collection Statistics ──────────────────────────────")
    print(f"  Total chunks    : {stats['total_chunks']}")
    print(f"  Unique sources  : {stats['unique_sources']}")
    if stats["source_breakdown"]:
        print("  Source breakdown:")
        for src, count in sorted(stats["source_breakdown"].items()):
            print(f"    {src:<45} {count:>5} chunk(s)")
    else:
        print("  (collection is empty)")
    print("────────────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Stats-only mode
    if args.stats_only:
        print_stats(args.chroma_dir)
        return 0

    # Build embedding function (validates GEMINI_API_KEY early)
    logger.info("Initialising embedding function…")
    try:
        embedding_fn = get_embedding_function()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Build and run ingestion service
    service = IngestionService(
        embedding_function=embedding_fn,
        documents_directory=args.docs_dir,
        chroma_persist_directory=args.chroma_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        force_reindex=args.force,
    )

    logger.info("Starting ingestion pipeline…")
    report = service.ingest()

    # Output
    if args.output_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("\n── TaskFlow AI Ingestion Report ────────────────────────────────")
        print(f"  Files discovered : {report.files_discovered}")
        print(f"  Files added      : {report.files_added}")
        print(f"  Files updated    : {report.files_updated}")
        print(f"  Files skipped    : {report.files_skipped}")
        print(f"  Files failed     : {report.files_failed}")
        print(f"  Chunks added     : {report.total_chunks_added}")
        print(f"  Chunks deleted   : {report.total_chunks_deleted}")
        if report.collection_stats:
            print(f"  Total in DB      : {report.collection_stats.get('total_chunks', 0)} chunk(s)")
            print(f"  Unique sources   : {report.collection_stats.get('unique_sources', 0)}")
        print()
        for r in report.file_results:
            status_icon = {"added": "✅", "updated": "🔄", "skipped": "⏭ ", "failed": "❌"}.get(r.status, "?")
            line = f"  {status_icon} [{r.status.upper():8}] {r.filename}"
            if r.chunks_added:
                line += f"  ({r.chunks_added} chunks)"
            if r.error:
                line += f"  — ERROR: {r.error}"
            print(line)
        print("────────────────────────────────────────────────────────────────\n")

    # Exit code
    if report.files_failed > 0:
        logger.warning("%d file(s) failed to ingest.", report.files_failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

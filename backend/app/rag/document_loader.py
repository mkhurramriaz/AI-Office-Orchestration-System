"""
TaskFlow AI — Document Loader

Loads PDF, TXT, and Markdown documents from the configured documents directory.
Attaches rich source metadata to every loaded document.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter  # python-frontmatter: reads YAML front-matter from .md files
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Supported file extensions mapped to their MIME-like type label
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}


def _compute_file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents (for duplicate detection)."""
    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _build_base_metadata(path: Path) -> dict:
    """Build the standard metadata dict attached to every chunk from this file."""
    stat = path.stat()
    return {
        "source": path.name,
        "source_path": str(path.resolve()),
        "file_type": SUPPORTED_EXTENSIONS.get(path.suffix.lower(), "unknown"),
        "file_size_bytes": stat.st_size,
        "file_hash": _compute_file_hash(path),
        "last_modified": stat.st_mtime,
    }


def load_pdf(path: Path) -> list[Document]:
    """Load a PDF file. Each page becomes a separate Document."""
    logger.debug("Loading PDF: %s", path.name)
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    base_meta = _build_base_metadata(path)
    for i, doc in enumerate(docs):
        doc.metadata.update(base_meta)
        doc.metadata["page"] = i + 1
        doc.metadata["total_pages"] = len(docs)
    logger.info("Loaded %d pages from PDF: %s", len(docs), path.name)
    return docs


def load_text(path: Path) -> list[Document]:
    """Load a plain-text file as a single Document."""
    logger.debug("Loading TXT: %s", path.name)
    # encoding='utf-8' with error fallback covers most real-world documents
    loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
    docs = loader.load()
    base_meta = _build_base_metadata(path)
    for doc in docs:
        doc.metadata.update(base_meta)
    logger.info("Loaded TXT: %s (%d chars)", path.name, sum(len(d.page_content) for d in docs))
    return docs


def load_markdown(path: Path) -> list[Document]:
    """
    Load a Markdown file.

    Extracts YAML front-matter (if present) and merges it into metadata so that
    document title, author, tags etc. are queryable at retrieval time.
    """
    logger.debug("Loading Markdown: %s", path.name)
    post = frontmatter.load(str(path))
    content: str = post.content
    fm_meta: dict = dict(post.metadata)  # YAML front-matter fields

    base_meta = _build_base_metadata(path)
    merged_meta = {**base_meta, **fm_meta}  # front-matter wins on key collision
    merged_meta["has_frontmatter"] = bool(fm_meta)

    doc = Document(page_content=content, metadata=merged_meta)
    logger.info("Loaded Markdown: %s (frontmatter keys: %s)", path.name, list(fm_meta.keys()))
    return [doc]


def load_document(path: Path) -> list[Document]:
    """
    Dispatch to the correct loader based on file extension.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf(path)
    if ext == ".txt":
        return load_text(path)
    if ext in (".md", ".markdown"):
        return load_markdown(path)
    raise ValueError(f"Unsupported document type '{ext}' for file: {path.name}")


def discover_documents(directory: str | Path) -> list[Path]:
    """
    Recursively discover all supported documents under *directory*.

    Returns a sorted list of Path objects so ingestion order is deterministic.
    """
    root = Path(directory)
    if not root.exists():
        logger.warning("Documents directory does not exist: %s", root)
        return []

    found: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        found.extend(root.rglob(f"*{ext}"))

    found.sort()
    logger.info("Discovered %d document(s) in '%s'", len(found), root)
    return found


def load_all_documents(directory: str | Path) -> list[Document]:
    """
    Load all supported documents from *directory*.

    Skips and logs any file that fails to load so a single corrupt file cannot
    abort an entire ingestion run.
    """
    paths = discover_documents(directory)
    all_docs: list[Document] = []
    for path in paths:
        try:
            docs = load_document(path)
            all_docs.extend(docs)
        except Exception as exc:
            logger.error("Failed to load '%s': %s", path.name, exc)

    logger.info("Total raw documents loaded: %d", len(all_docs))
    return all_docs

"""
TaskFlow AI — Phase 3A Unit Tests: RAG Ingestion Pipeline

Tests cover:
  - Document discovery and loading (PDF, TXT, Markdown).
  - Text splitting with chunk metadata.
  - Duplicate detection logic.
  - Ingestion service orchestration (add / update / skip / fail paths).
  - Vector store helpers (stats, delete, add).
  - ChromaDB path resolution.

All external API calls (Gemini embeddings, real ChromaDB writes) are mocked.
No network access is required to run these tests.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the backend package is importable
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Helper: compute sha256 of raw bytes (mirrors document_loader._compute_file_hash)
# ---------------------------------------------------------------------------

def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ===========================================================================
# 1. Document Loader Tests
# ===========================================================================


class TestDocumentDiscovery:
    """Tests for discover_documents()."""

    def test_discovers_supported_extensions(self, tmp_path):
        from app.rag.document_loader import discover_documents

        (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4 fake")
        (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "readme.md").write_text("# Title", encoding="utf-8")
        (tmp_path / "data.csv").write_text("a,b,c", encoding="utf-8")  # unsupported

        paths = discover_documents(tmp_path)
        names = [p.name for p in paths]

        assert "report.pdf" in names
        assert "notes.txt" in names
        assert "readme.md" in names
        assert "data.csv" not in names

    def test_returns_empty_for_missing_directory(self, tmp_path):
        from app.rag.document_loader import discover_documents

        result = discover_documents(tmp_path / "nonexistent")
        assert result == []

    def test_discovers_recursively(self, tmp_path):
        from app.rag.document_loader import discover_documents

        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "nested.txt").write_text("nested content", encoding="utf-8")

        paths = discover_documents(tmp_path)
        assert any(p.name == "nested.txt" for p in paths)

    def test_returns_sorted_list(self, tmp_path):
        from app.rag.document_loader import discover_documents

        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "c.txt").write_text("c", encoding="utf-8")

        paths = discover_documents(tmp_path)
        names = [p.name for p in paths]
        assert names == sorted(names)


class TestTextLoading:
    """Tests for load_text() and load_markdown()."""

    def test_load_txt_attaches_metadata(self, tmp_path):
        from app.rag.document_loader import load_text, repository_relative_path

        f = tmp_path / "sample.txt"
        f.write_text("Hello TaskFlow", encoding="utf-8")

        docs = load_text(f)
        assert len(docs) >= 1
        meta = docs[0].metadata
        assert meta["source"] == repository_relative_path(f)
        assert meta["file_type"] == "text"
        assert "file_hash" in meta
        assert "file_size_bytes" in meta
        assert "last_modified" in meta

    def test_load_txt_content(self, tmp_path):
        from app.rag.document_loader import load_text

        f = tmp_path / "content.txt"
        f.write_text("The quick brown fox", encoding="utf-8")

        docs = load_text(f)
        assert "The quick brown fox" in docs[0].page_content

    def test_load_markdown_basic(self, tmp_path):
        from app.rag.document_loader import load_markdown, repository_relative_path

        f = tmp_path / "doc.md"
        f.write_text("# Heading\n\nSome content here.", encoding="utf-8")

        docs = load_markdown(f)
        assert len(docs) == 1
        assert "Some content here." in docs[0].page_content
        assert docs[0].metadata["source"] == repository_relative_path(f)
        assert docs[0].metadata["file_type"] == "markdown"

    def test_load_markdown_extracts_frontmatter(self, tmp_path):
        from app.rag.document_loader import load_markdown

        f = tmp_path / "policy.md"
        content = "---\ntitle: HR Policy\nauthor: Jane Doe\ntags: [hr, policy]\n---\n\nBody text here."
        f.write_text(content, encoding="utf-8")

        docs = load_markdown(f)
        meta = docs[0].metadata
        assert meta["title"] == "HR Policy"
        assert meta["author"] == "Jane Doe"
        assert meta["has_frontmatter"] is True
        assert "Body text here." in docs[0].page_content

    def test_markdown_nested_frontmatter_is_chroma_compatible(self, tmp_path):
        from app.rag.document_loader import load_markdown

        f = tmp_path / "nested.md"
        f.write_text(
            '---\ntags: [hr, policy]\nowner:\n  name: Jane\n  teams: [people, legal]\nempty: null\n---\nBody',
            encoding="utf-8",
        )
        metadata = load_markdown(f)[0].metadata
        assert metadata["tags"] == '["hr", "policy"]'
        assert metadata["owner"] == '{"name": "Jane", "teams": ["people", "legal"]}'
        assert metadata["empty"] == "null"
        assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())

    def test_load_markdown_no_frontmatter(self, tmp_path):
        from app.rag.document_loader import load_markdown

        f = tmp_path / "plain.md"
        f.write_text("Just plain markdown content.", encoding="utf-8")

        docs = load_markdown(f)
        assert docs[0].metadata["has_frontmatter"] is False

    def test_load_document_raises_for_unsupported(self, tmp_path):
        from app.rag.document_loader import load_document

        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported document type"):
            load_document(f)

    def test_file_hash_is_deterministic(self, tmp_path):
        from app.rag.document_loader import load_text

        f = tmp_path / "stable.txt"
        f.write_text("Stable content", encoding="utf-8")

        docs1 = load_text(f)
        docs2 = load_text(f)
        assert docs1[0].metadata["file_hash"] == docs2[0].metadata["file_hash"]

    def test_file_hash_changes_with_content(self, tmp_path):
        from app.rag.document_loader import load_text

        f = tmp_path / "changing.txt"
        f.write_text("Version 1", encoding="utf-8")
        docs1 = load_text(f)

        f.write_text("Version 2", encoding="utf-8")
        docs2 = load_text(f)

        assert docs1[0].metadata["file_hash"] != docs2[0].metadata["file_hash"]

    def test_load_all_documents_skips_failed_files(self, tmp_path):
        """load_all_documents should not raise when one file is unreadable."""
        from app.rag.document_loader import load_all_documents

        good = tmp_path / "good.txt"
        good.write_text("Good content", encoding="utf-8")

        # Create a file with an unsupported extension — will be ignored by discovery
        bad = tmp_path / "bad.xyz"
        bad.write_text("bad", encoding="utf-8")

        docs = load_all_documents(tmp_path)
        assert len(docs) >= 1
        assert all(d.metadata["source"] != "bad.xyz" for d in docs)


# ===========================================================================
# 2. Text Splitter Tests
# ===========================================================================


class TestTextSplitter:
    """Tests for split_documents()."""

    def _make_doc(self, content: str, source: str = "test.txt"):
        from langchain_core.documents import Document
        return Document(page_content=content, metadata={"source": source, "file_hash": "abc123"})

    def test_single_short_document_produces_one_chunk(self):
        from app.rag.text_splitter import split_documents

        doc = self._make_doc("Short content.")
        chunks = split_documents([doc], chunk_size=1000, chunk_overlap=0)
        assert len(chunks) == 1

    def test_long_document_produces_multiple_chunks(self):
        from app.rag.text_splitter import split_documents

        # 3000 chars — should produce at least 3 chunks at chunk_size=1000
        content = "word " * 600  # ~3000 chars
        doc = self._make_doc(content)
        chunks = split_documents([doc], chunk_size=1000, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_chunk_index_and_total_in_metadata(self):
        from app.rag.text_splitter import split_documents

        content = "paragraph\n\n" * 100  # long enough to split
        doc = self._make_doc(content, source="indexed.txt")
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=0)

        for i, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_index"] == i
            assert chunk.metadata["total_chunks"] == len(chunks)

    def test_chunk_size_and_overlap_in_metadata(self):
        from app.rag.text_splitter import split_documents

        doc = self._make_doc("x " * 500)
        chunks = split_documents([doc], chunk_size=300, chunk_overlap=50)

        for chunk in chunks:
            assert chunk.metadata["chunk_size"] == 300
            assert chunk.metadata["chunk_overlap"] == 50

    def test_source_metadata_preserved(self):
        from app.rag.text_splitter import split_documents

        doc = self._make_doc("content " * 200, source="policy.pdf")
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=0)

        for chunk in chunks:
            assert chunk.metadata["source"] == "policy.pdf"

    def test_empty_documents_list(self):
        from app.rag.text_splitter import split_documents

        chunks = split_documents([])
        assert chunks == []

    def test_separate_chunk_indices_per_source(self):
        from app.rag.text_splitter import split_documents

        doc_a = self._make_doc("a " * 400, source="a.txt")
        doc_b = self._make_doc("b " * 400, source="b.txt")
        chunks = split_documents([doc_a, doc_b], chunk_size=200, chunk_overlap=0)

        a_chunks = [c for c in chunks if c.metadata["source"] == "a.txt"]
        b_chunks = [c for c in chunks if c.metadata["source"] == "b.txt"]

        # Each source has its own 0-based index
        assert a_chunks[0].metadata["chunk_index"] == 0
        assert b_chunks[0].metadata["chunk_index"] == 0
        assert a_chunks[-1].metadata["total_chunks"] == len(a_chunks)
        assert b_chunks[-1].metadata["total_chunks"] == len(b_chunks)


# ===========================================================================
# 3. Vector Store Helpers Tests (all ChromaDB calls are mocked)
# ===========================================================================


class TestVectorStoreHelpers:
    """Tests for vector_store module with ChromaDB mocked out."""

    def _make_mock_store(self, metadatas=None, ids=None):
        """Return a MagicMock that mimics a Chroma vector store."""
        store = MagicMock()
        store.get.return_value = {
            "metadatas": metadatas or [],
            "ids": ids or [],
        }
        return store

    def test_get_indexed_hashes_returns_mapping(self):
        from app.rag.vector_store import get_indexed_hashes

        store = self._make_mock_store(
            metadatas=[
                {"source": "policies/doc1.txt", "file_hash": "hash_aaa"},
                {"source": "reports/doc2.pdf", "file_hash": "hash_bbb"},
            ]
        )
        result = get_indexed_hashes(store)
        assert result == {"policies/doc1.txt": "hash_aaa", "reports/doc2.pdf": "hash_bbb"}

    def test_get_indexed_hashes_empty_collection(self):
        from app.rag.vector_store import get_indexed_hashes

        store = self._make_mock_store(metadatas=[])
        result = get_indexed_hashes(store)
        assert result == {}

    def test_get_indexed_hashes_handles_exception(self):
        from app.rag.vector_store import get_indexed_hashes

        store = MagicMock()
        store.get.side_effect = RuntimeError("DB error")
        result = get_indexed_hashes(store)
        assert result == {}

    def test_delete_source_calls_delete_with_correct_ids(self):
        from app.rag.vector_store import delete_source

        store = self._make_mock_store(
            metadatas=[{"source": "doc.txt"}],
            ids=["id-1", "id-2"],
        )
        count = delete_source(store, "doc.txt")
        store.delete.assert_called_once_with(ids=["id-1", "id-2"])
        assert count == 2

    def test_delete_source_returns_zero_when_not_found(self):
        from app.rag.vector_store import delete_source

        store = self._make_mock_store(metadatas=[], ids=[])
        count = delete_source(store, "missing.txt")
        store.delete.assert_not_called()
        assert count == 0

    def test_add_chunks_calls_add_documents(self):
        from langchain_core.documents import Document
        from app.rag.vector_store import add_chunks

        store = MagicMock()
        store.add_documents.return_value = ["id-1", "id-2"]

        chunks = [
            Document(page_content="chunk 1", metadata={}),
            Document(page_content="chunk 2", metadata={}),
        ]
        ids = add_chunks(store, chunks)
        store.add_documents.assert_called_once_with(chunks)
        assert ids == ["id-1", "id-2"]

    def test_add_chunks_empty_list_returns_empty(self):
        from app.rag.vector_store import add_chunks

        store = MagicMock()
        ids = add_chunks(store, [])
        store.add_documents.assert_not_called()
        assert ids == []

    def test_get_collection_stats(self):
        from app.rag.vector_store import get_collection_stats

        store = self._make_mock_store(
            metadatas=[
                {"source": "a.txt"},
                {"source": "a.txt"},
                {"source": "b.pdf"},
            ]
        )
        stats = get_collection_stats(store)
        assert stats["total_chunks"] == 3
        assert stats["unique_sources"] == 2
        assert stats["source_breakdown"]["a.txt"] == 2
        assert stats["source_breakdown"]["b.pdf"] == 1

    def test_get_collection_stats_handles_exception(self):
        from app.rag.vector_store import get_collection_stats

        store = MagicMock()
        store.get.side_effect = RuntimeError("boom")
        stats = get_collection_stats(store)
        assert stats["total_chunks"] == 0
        assert stats["unique_sources"] == 0


# ===========================================================================
# 4. Ingestion Service Tests (embeddings + ChromaDB fully mocked)
# ===========================================================================


class TestIngestionService:
    """
    Tests for IngestionService.ingest() with all external calls mocked.

    Strategy
    --------
    - Provide a tmp_path as documents directory with real files.
    - Mock get_vector_store() to return a mock Chroma instance.
    - Mock get_indexed_hashes(), delete_source(), add_chunks(), get_collection_stats().
    - Use a MagicMock() as the embedding_function (never called — ChromaDB is mocked).
    """

    def _make_service(self, docs_dir: str, mock_embedding=None, force=False, chunk_size=200):
        from app.rag.ingestion_service import IngestionService

        return IngestionService(
            embedding_function=mock_embedding or MagicMock(),
            documents_directory=docs_dir,
            chroma_persist_directory="/tmp/fake_chroma",
            chunk_size=chunk_size,
            chunk_overlap=0,
            force_reindex=force,
        )

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 5, "unique_sources": 1, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", return_value=["id-1"])
    @patch("app.rag.ingestion_service.delete_source", return_value=0)
    @patch("app.rag.ingestion_service.get_indexed_hashes", return_value={})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_new_file_is_added(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        (tmp_path / "new.txt").write_text("New document content " * 5, encoding="utf-8")

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_discovered == 1
        assert report.files_added == 1
        assert report.files_skipped == 0
        assert report.files_failed == 0
        mock_add.assert_called_once()

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 5, "unique_sources": 1, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", return_value=["id-1"])
    @patch("app.rag.ingestion_service.delete_source", return_value=3)
    @patch("app.rag.ingestion_service.get_indexed_hashes")
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_changed_file_is_updated(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        """When stored hash differs from current hash → delete + re-add."""
        f = tmp_path / "changed.txt"
        f.write_text("Updated content " * 5, encoding="utf-8")

        # Simulate a stale hash (different from actual file hash)
        from app.rag.document_loader import repository_relative_path
        source_id = repository_relative_path(f)
        mock_hashes.return_value = {source_id: "stale_hash_000"}

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_updated == 1
        assert report.files_added == 0
        mock_delete.assert_called_once()
        assert mock_delete.call_args.args[:2] == (mock_vs.return_value, source_id)
        mock_add.assert_called_once()
        assert report.total_chunks_deleted == 3

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 5, "unique_sources": 1, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks")
    @patch("app.rag.ingestion_service.delete_source")
    @patch("app.rag.ingestion_service.get_indexed_hashes")
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_unchanged_file_is_skipped(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        """When stored hash matches current hash → skip without re-embedding."""
        f = tmp_path / "stable.txt"
        content = b"Stable content that never changes"
        f.write_bytes(content)

        actual_hash = _sha256(content)
        from app.rag.document_loader import repository_relative_path
        mock_hashes.return_value = {repository_relative_path(f): actual_hash}

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_skipped == 1
        assert report.files_added == 0
        assert report.files_updated == 0
        mock_add.assert_not_called()
        mock_delete.assert_not_called()

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 5, "unique_sources": 1, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", return_value=["id-1"])
    @patch("app.rag.ingestion_service.delete_source", return_value=0)
    @patch("app.rag.ingestion_service.get_indexed_hashes")
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_force_reindex_bypasses_hash_check(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        """force_reindex=True should re-embed even if hash matches."""
        f = tmp_path / "stable.txt"
        content = b"Stable content"
        f.write_bytes(content)

        actual_hash = _sha256(content)
        from app.rag.document_loader import repository_relative_path
        mock_hashes.return_value = {repository_relative_path(f): actual_hash}  # would normally skip

        service = self._make_service(str(tmp_path), force=True)
        report = service.ingest()

        # Force re-index still replaces existing chunks for the same source.
        assert report.files_updated == 1
        assert report.files_skipped == 0
        mock_add.assert_called_once()
        mock_delete.assert_called_once()
        assert mock_delete.call_args.args[:2] == (
            mock_vs.return_value,
            repository_relative_path(f),
        )

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 0, "unique_sources": 0, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_empty_directory_returns_zero_counts(self, mock_vs, mock_stats, tmp_path):
        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_discovered == 0
        assert report.files_added == 0
        mock_vs.assert_not_called()  # vector store not opened for empty directory

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 0, "unique_sources": 0, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", side_effect=RuntimeError("embed failed"))
    @patch("app.rag.ingestion_service.delete_source", return_value=0)
    @patch("app.rag.ingestion_service.get_indexed_hashes", return_value={})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_failed_file_recorded_in_report(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        """When add_chunks raises, file should be recorded as 'failed'."""
        (tmp_path / "bad.txt").write_text("content", encoding="utf-8")

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_failed == 1
        assert report.files_added == 0
        assert report.file_results[0].status == "failed"
        assert "embed failed" in report.file_results[0].error

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 1, "unique_sources": 1, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", side_effect=RuntimeError("embedding failed"))
    @patch("app.rag.ingestion_service.delete_source")
    @patch("app.rag.ingestion_service.get_indexed_hashes")
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_failed_reindex_preserves_existing_chunks(
        self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path
    ):
        from app.rag.document_loader import repository_relative_path

        f = tmp_path / "existing.txt"
        f.write_text("replacement content", encoding="utf-8")
        source_id = repository_relative_path(f)
        existing_chunks = [{"id": "old-chunk", "source": source_id}]
        mock_hashes.return_value = {source_id: "old-hash"}

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_failed == 1
        assert existing_chunks == [{"id": "old-chunk", "source": source_id}]
        mock_add.assert_called_once()
        mock_delete.assert_not_called()

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 2, "unique_sources": 2, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", side_effect=[["id-a"], ["id-b"]])
    @patch("app.rag.ingestion_service.get_indexed_hashes", return_value={})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_same_filename_in_different_directories_has_distinct_identity(
        self, mock_vs, mock_hashes, mock_add, mock_stats, tmp_path
    ):
        from app.rag.document_loader import repository_relative_path

        (tmp_path / "policies").mkdir()
        (tmp_path / "reports").mkdir()
        (tmp_path / "policies" / "guide.txt").write_text("policy text", encoding="utf-8")
        (tmp_path / "reports" / "guide.txt").write_text("report text", encoding="utf-8")

        report = self._make_service(str(tmp_path)).ingest()
        source_ids = [r.filename for r in report.file_results]

        assert report.files_added == 2
        assert len(set(source_ids)) == 2
        assert set(source_ids) == {
            repository_relative_path(tmp_path / "policies" / "guide.txt"),
            repository_relative_path(tmp_path / "reports" / "guide.txt"),
        }
        chunks = [call.args[1][0] for call in mock_add.call_args_list]
        assert {chunk.metadata["source"] for chunk in chunks} == set(source_ids)

    @pytest.mark.parametrize("working_directory", ["repository", "backend"])
    def test_default_documents_directory_resolves_from_repository_root(
        self, monkeypatch, working_directory
    ):
        from app.core.config import get_settings
        from app.rag.document_loader import REPOSITORY_ROOT
        from app.rag.ingestion_service import IngestionService

        base = REPOSITORY_ROOT if working_directory == "repository" else REPOSITORY_ROOT / "backend"
        monkeypatch.chdir(base)
        settings = get_settings()
        service = IngestionService(embedding_function=MagicMock())

        assert Path(service._documents_directory) == REPOSITORY_ROOT / settings.DOCUMENTS_DIRECTORY

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 10, "unique_sources": 2, "source_breakdown": {"a.txt": 5, "b.md": 5}})
    @patch("app.rag.ingestion_service.add_chunks", return_value=["id-1"])
    @patch("app.rag.ingestion_service.delete_source", return_value=0)
    @patch("app.rag.ingestion_service.get_indexed_hashes", return_value={})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_report_to_dict_is_serialisable(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        """IngestionReport.to_dict() must return a JSON-serialisable dict."""
        import json
        (tmp_path / "sample.txt").write_text("content", encoding="utf-8")

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        d = report.to_dict()
        # Should not raise
        serialised = json.dumps(d)
        assert "files_discovered" in serialised

    @patch("app.rag.ingestion_service.get_collection_stats", return_value={"total_chunks": 5, "unique_sources": 2, "source_breakdown": {}})
    @patch("app.rag.ingestion_service.add_chunks", return_value=["id-1"])
    @patch("app.rag.ingestion_service.delete_source", return_value=0)
    @patch("app.rag.ingestion_service.get_indexed_hashes", return_value={})
    @patch("app.rag.ingestion_service.get_vector_store")
    def test_multiple_files_all_added(self, mock_vs, mock_hashes, mock_delete, mock_add, mock_stats, tmp_path):
        (tmp_path / "a.txt").write_text("content a " * 5, encoding="utf-8")
        (tmp_path / "b.md").write_text("# Content B\n\nBody.", encoding="utf-8")

        service = self._make_service(str(tmp_path))
        report = service.ingest()

        assert report.files_discovered == 2
        assert report.files_added == 2
        assert mock_add.call_count == 2


# ===========================================================================
# 5. Ingestion Report Tests
# ===========================================================================


class TestIngestionReport:
    def test_to_dict_structure(self):
        from app.rag.ingestion_service import FileIngestionResult, IngestionReport

        report = IngestionReport(
            files_discovered=3,
            files_added=2,
            files_skipped=1,
            total_chunks_added=10,
            collection_stats={"total_chunks": 10},
            file_results=[
                FileIngestionResult(filename="a.txt", status="added", chunks_added=5),
                FileIngestionResult(filename="b.txt", status="skipped"),
                FileIngestionResult(filename="c.txt", status="failed", error="oops"),
            ],
        )
        d = report.to_dict()
        assert d["files_discovered"] == 3
        assert d["files_added"] == 2
        assert d["files_skipped"] == 1
        assert d["total_chunks_added"] == 10
        assert len(d["file_results"]) == 3
        assert d["file_results"][2]["error"] == "oops"


# ===========================================================================
# 6. Configuration Tests
# ===========================================================================


class TestRAGConfiguration:
    """Verify settings expose the expected RAG-related fields."""

    def test_settings_has_chroma_directory(self):
        from app.core.config import get_settings
        s = get_settings()
        assert hasattr(s, "CHROMA_PERSIST_DIRECTORY")
        assert s.CHROMA_PERSIST_DIRECTORY != ""

    def test_settings_has_documents_directory(self):
        from app.core.config import get_settings
        s = get_settings()
        assert hasattr(s, "DOCUMENTS_DIRECTORY")
        assert s.DOCUMENTS_DIRECTORY != ""

    def test_settings_has_gemini_api_key_field(self):
        from app.core.config import get_settings
        s = get_settings()
        assert hasattr(s, "GEMINI_API_KEY")

    def test_embeddings_raises_without_api_key(self):
        """get_embedding_function() must raise ValueError when key is missing."""
        from app.rag.embeddings import get_embedding_function

        # Clear the lru_cache to avoid cross-test contamination
        get_embedding_function.cache_clear()

        with patch("app.rag.embeddings.get_settings") as mock_settings:
            mock_s = MagicMock()
            mock_s.GEMINI_API_KEY = None
            mock_settings.return_value = mock_s

            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                get_embedding_function()

        # Restore cache state for subsequent tests
        get_embedding_function.cache_clear()

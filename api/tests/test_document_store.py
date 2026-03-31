"""
Tests for document store API endpoints.
"""

import pytest
import io
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Confab, ConfabDocument, DocumentChunk


class TestDocumentUpload:
    """Tests for POST /confabs/{confab_id}/documents"""

    def test_upload_text_document(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_document_service
    ):
        """Test uploading a plain text document."""
        content = b"This is a test document with some content for testing."

        response = client.post(
            f"/confabs/{test_confab.id}/documents",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["status"] == "indexed"
        assert data["chunk_count"] >= 1

    def test_upload_markdown_document(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_document_service
    ):
        """Test uploading a markdown document."""
        content = b"# Test Document\n\nThis is a **test** document.\n\n## Section 2\n\nMore content here."

        response = client.post(
            f"/confabs/{test_confab.id}/documents",
            headers=auth_headers,
            files={"file": ("test.md", io.BytesIO(content), "text/markdown")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.md"
        assert data["status"] == "indexed"

    def test_upload_document_with_metadata(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_document_service
    ):
        """Test uploading a document with custom metadata."""
        import json
        content = b"Document content for metadata test."
        metadata = json.dumps({"author": "Test Author", "category": "testing"})

        response = client.post(
            f"/confabs/{test_confab.id}/documents",
            headers=auth_headers,
            files={"file": ("doc.txt", io.BytesIO(content), "text/plain")},
            data={"metadata": metadata}
        )

        assert response.status_code == 200

    def test_upload_document_confab_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test uploading to non-existent confab returns 404."""
        content = b"Test content"

        response = client.post(
            "/confabs/99999/documents",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")}
        )

        assert response.status_code == 404

    def test_upload_document_unauthenticated(
        self,
        client: TestClient,
        test_confab: Confab
    ):
        """Test uploading without auth returns 401/403."""
        content = b"Test content"

        response = client.post(
            f"/confabs/{test_confab.id}/documents",
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")}
        )

        assert response.status_code in [401, 403]


class TestDocumentList:
    """Tests for GET /confabs/{confab_id}/documents"""

    def test_list_documents_empty(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab
    ):
        """Test listing documents when none exist."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_list_documents_with_documents(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        test_document: ConfabDocument
    ):
        """Test listing documents when documents exist."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test_doc.txt"
        assert data[0]["chunk_count"] == 1

    def test_list_documents_confab_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test listing documents for non-existent confab."""
        response = client.get(
            "/confabs/99999/documents",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestDocumentGet:
    """Tests for GET /confabs/{confab_id}/documents/{document_id}"""

    def test_get_document(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        test_document: ConfabDocument
    ):
        """Test getting a specific document."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/{test_document.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_document.id
        assert data["filename"] == "test_doc.txt"
        assert data["content_type"] == "text/plain"
        assert data["raw_content"] == "Test document content for testing."

    def test_get_document_not_found(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab
    ):
        """Test getting non-existent document returns 404."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/99999",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestDocumentDelete:
    """Tests for DELETE /confabs/{confab_id}/documents/{document_id}"""

    def test_delete_document(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        test_document: ConfabDocument,
        db: Session,
        mock_vector_store
    ):
        """Test deleting a document."""
        response = client.delete(
            f"/confabs/{test_confab.id}/documents/{test_document.id}",
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify document is deleted
        doc = db.query(ConfabDocument).filter(ConfabDocument.id == test_document.id).first()
        assert doc is None

    def test_delete_document_not_found(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_vector_store
    ):
        """Test deleting non-existent document returns 404."""
        response = client.delete(
            f"/confabs/{test_confab.id}/documents/99999",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestDocumentSearch:
    """Tests for POST /confabs/{confab_id}/documents/search"""

    def test_search_documents(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        test_document: ConfabDocument,
        mock_search_service
    ):
        """Test searching documents."""
        response = client.post(
            f"/confabs/{test_confab.id}/documents/search",
            headers=auth_headers,
            json={"query": "test content", "top_k": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["query"] == "test content"
        assert "total_results" in data

    def test_search_documents_with_filter(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_search_service
    ):
        """Test searching with type filter."""
        response = client.post(
            f"/confabs/{test_confab.id}/documents/search",
            headers=auth_headers,
            json={"query": "test", "top_k": 3, "filter_type": "document"}
        )

        assert response.status_code == 200

    def test_search_documents_confab_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test searching in non-existent confab."""
        response = client.post(
            "/confabs/99999/documents/search",
            headers=auth_headers,
            json={"query": "test"}
        )

        assert response.status_code == 404


class TestDocumentStats:
    """Tests for GET /confabs/{confab_id}/documents/stats"""

    def test_get_stats_empty(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        mock_stats_service
    ):
        """Test getting stats with no documents."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/stats",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_count" in data
        assert "total_chunks" in data
        assert "embedding_model" in data

    def test_get_stats_with_documents(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        test_document: ConfabDocument,
        mock_stats_service
    ):
        """Test getting stats with documents."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/stats",
            headers=auth_headers
        )

        assert response.status_code == 200


# =============================================================================
# Additional Fixtures for Document Store Tests
# =============================================================================

@pytest.fixture
def test_document(db: Session, test_confab: Confab) -> ConfabDocument:
    """Create a test document."""
    import hashlib
    content = "Test document content for testing."
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    doc = ConfabDocument(
        confab_id=test_confab.id,
        filename="test_doc.txt",
        content_type="text/plain",
        source="upload",
        content_hash=content_hash,
        raw_content=content,
        chunk_count=1,
        status="indexed"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Add a chunk
    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content=content,
        vector_id=f"doc_{doc.id}_chunk_0"
    )
    db.add(chunk)
    db.commit()

    return doc


@pytest.fixture
def mock_document_service():
    """Mock DocumentService for upload tests."""
    with patch("main.DocumentService") as mock_class:
        mock_instance = MagicMock()

        # Mock upload_document
        async def mock_upload(*args, **kwargs):
            from document_store.service import UploadResult
            return UploadResult(
                document_id=1,
                filename=kwargs.get("filename", "test.txt"),
                chunk_count=1,
                status="indexed"
            )

        mock_instance.upload_document = AsyncMock(side_effect=mock_upload)
        mock_instance.list_documents = AsyncMock(return_value=[])

        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for delete tests."""
    with patch("document_store.service.VectorStore") as mock_class:
        mock_instance = MagicMock()
        mock_instance.delete_document_chunks = AsyncMock(return_value=1)
        mock_instance.clear_collection = AsyncMock(return_value=True)
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_search_service():
    """Mock DocumentService for search tests."""
    with patch("main.DocumentService") as mock_class:
        mock_instance = MagicMock()

        async def mock_search(*args, **kwargs):
            from document_store.service import SearchResultWithSource
            return [
                SearchResultWithSource(
                    chunk_id="doc_1_chunk_0",
                    document_id=1,
                    filename="test.txt",
                    content="Test content",
                    score=0.95,
                    chunk_index=0,
                    source_type="document",
                    metadata={}
                )
            ]

        mock_instance.search = AsyncMock(side_effect=mock_search)
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_stats_service():
    """Mock DocumentService for stats tests."""
    with patch("main.DocumentService") as mock_class:
        mock_instance = MagicMock()

        async def mock_stats(*args, **kwargs):
            return {
                "document_count": 0,
                "total_chunks": 0,
                "total_size_bytes": 0,
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_provider": "sentence_transformers",
                "vector_store": {"total_chunks": 0}
            }

        mock_instance.get_stats = AsyncMock(side_effect=mock_stats)
        mock_class.return_value = mock_instance
        yield mock_instance

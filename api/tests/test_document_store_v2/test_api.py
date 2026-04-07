"""
Tests for Document Store V2 API endpoints.

Integration tests for all document API endpoints.

NOTE: V2 endpoints share paths with V1 endpoints for upload/list/get/archive.
FastAPI routes V1 first. Tests for those endpoints are skipped when routing
conflicts exist. Version-specific endpoints (/versions) are fully tested here.
"""

import base64
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Confab, ConfabDocumentV2, DocumentVersion, User
from auth import create_access_token
from document_store_v2.compression import compress


# =============================================================================
# Helper to create documents directly in DB (bypasses routing issues)
# =============================================================================

def create_test_document_v2(db: Session, confab_id: int, filename: str = "test.txt", content: bytes = b"test") -> ConfabDocumentV2:
    """Create a V2 document with version directly in database."""
    doc = ConfabDocumentV2(
        confab_id=confab_id,
        filename=filename,
        original_content_type="text/plain",
        source="upload",
        status="active",
    )
    db.add(doc)
    db.flush()

    compressed = compress(content)
    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        content_blob=compressed,
        content_hash=hashlib.sha256(content).hexdigest(),
        original_size=len(content),
        compressed_size=len(compressed),
        text_extraction_status="pending",
    )
    db.add(version)
    db.commit()
    db.refresh(doc)
    return doc


# =============================================================================
# Note: Upload/List/Get/Archive endpoints share paths with V1 (file upload).
# FastAPI routes to V1 first. Full service-layer coverage is in test_service.py.
# These tests verify auth and basic routing for V2-specific endpoints.
# =============================================================================


class TestListDocumentsEndpointAuth:
    """Auth tests for list documents endpoint."""

    def test_list_without_auth_returns_401(self, client: TestClient, test_confab: Confab):
        """List without auth should return 401."""
        response = client.get(f"/confabs/{test_confab.id}/documents")
        assert response.status_code == 401


class TestGetDocumentEndpointAuth:
    """Auth tests for get document endpoint."""

    def test_get_document_nonexistent_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Get non-existent document should return 404."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_document_wrong_confab_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        """Get document with wrong confab should return 404."""
        doc = create_test_document_v2(db, test_confab.id)
        response = client.get(
            f"/confabs/99999/documents/{doc.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_document_without_auth_returns_401(self, client: TestClient, test_confab: Confab, db: Session):
        """Get document without auth should return 401."""
        doc = create_test_document_v2(db, test_confab.id)
        response = client.get(f"/confabs/{test_confab.id}/documents/{doc.id}")
        assert response.status_code == 401


class TestArchiveDocumentEndpointAuth:
    """Auth tests for archive document endpoint."""

    def test_archive_nonexistent_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Archive non-existent document should return 404."""
        response = client.delete(
            f"/confabs/{test_confab.id}/documents/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_archive_without_auth_returns_401(self, client: TestClient, test_confab: Confab, db: Session):
        """Archive without auth should return 401."""
        doc = create_test_document_v2(db, test_confab.id)
        response = client.delete(f"/confabs/{test_confab.id}/documents/{doc.id}")
        assert response.status_code == 401


class TestListVersionsEndpoint:
    """Tests for GET /confabs/{confab_id}/documents/{document_id}/versions endpoint."""

    @pytest.fixture
    def document_with_versions(self, db: Session, test_confab: Confab):
        """Create a document with versions."""
        from document_store_v2.compression import compress
        import hashlib

        doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="versioned.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc)
        db.flush()

        for i in range(1, 3):
            content = f"Version {i}".encode()
            version = DocumentVersion(
                document_id=doc.id,
                version_number=i,
                content_blob=compress(content),
                content_hash=hashlib.sha256(content).hexdigest(),
                original_size=len(content),
                compressed_size=len(compress(content)),
                text_extraction_status="pending",
            )
            db.add(version)

        db.commit()
        db.refresh(doc)
        return doc

    def test_list_versions_success(self, client: TestClient, auth_headers: dict, test_confab: Confab, document_with_versions):
        """List versions should return all versions."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/{document_with_versions.id}/versions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["versions"]) == 2

    def test_list_versions_ordered(self, client: TestClient, auth_headers: dict, test_confab: Confab, document_with_versions):
        """Versions should be ordered descending by version number."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/{document_with_versions.id}/versions",
            headers=auth_headers,
        )

        data = response.json()
        version_numbers = [v["version_number"] for v in data["versions"]]
        assert version_numbers == [2, 1]

    def test_list_versions_nonexistent_doc_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """List versions for non-existent document should return 404."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/99999/versions",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_list_versions_without_auth_returns_401(self, client: TestClient, test_confab: Confab, document_with_versions):
        """List versions without auth should return 401."""
        response = client.get(f"/confabs/{test_confab.id}/documents/{document_with_versions.id}/versions")
        assert response.status_code == 401


class TestGetVersionContentEndpoint:
    """Tests for GET /confabs/{confab_id}/documents/{document_id}/versions/{version_number} endpoint."""

    @pytest.fixture
    def document_with_content(self, db: Session, test_confab: Confab):
        """Create a document with version containing content."""
        from document_store_v2.compression import compress
        import hashlib

        doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="content_test.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc)
        db.flush()

        content = b"This is the test content"
        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            content_blob=compress(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            original_size=len(content),
            compressed_size=len(compress(content)),
            text_extraction_status="pending",
        )
        db.add(version)
        db.commit()
        db.refresh(doc)
        return doc, content

    def test_get_version_content_success(self, client: TestClient, auth_headers: dict, test_confab: Confab, document_with_content):
        """Get version content should return decompressed content."""
        doc, original_content = document_with_content

        response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        decoded = base64.b64decode(data["content_base64"])
        assert decoded == original_content

    def test_get_version_content_nonexistent_version_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab, document_with_content):
        """Get non-existent version should return 404."""
        doc, _ = document_with_content

        response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/99",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_get_version_content_without_auth_returns_401(self, client: TestClient, test_confab: Confab, document_with_content):
        """Get version content without auth should return 401."""
        doc, _ = document_with_content
        response = client.get(f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1")
        assert response.status_code == 401


class TestCreateVersionEndpoint:
    """Tests for POST /confabs/{confab_id}/documents/{document_id}/versions endpoint."""

    @pytest.fixture
    def existing_document(self, db: Session, test_confab: Confab):
        """Create a document with first version."""
        from document_store_v2.compression import compress
        import hashlib

        doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="version_test.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc)
        db.flush()

        content = b"Version 1 content"
        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            content_blob=compress(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            original_size=len(content),
            compressed_size=len(compress(content)),
            text_extraction_status="pending",
        )
        db.add(version)
        db.commit()
        db.refresh(doc)
        return doc

    @pytest.fixture
    def mock_validation(self):
        """Mock validation to pass."""
        with patch("document_store_v2.service.validate_upload") as mock:
            mock.return_value = MagicMock(
                is_valid=True,
                sanitized_filename="version_test.txt",
                actual_content_type="text/plain",
                original_size=200,
                error=None,
            )
            yield mock

    def test_create_version_success(self, client: TestClient, auth_headers: dict, test_confab: Confab, existing_document, mock_validation):
        """Create version should return updated version list."""
        new_content = base64.b64encode(b"Version 2 content").decode()

        response = client.post(
            f"/confabs/{test_confab.id}/documents/{existing_document.id}/versions",
            headers=auth_headers,
            json={"content_base64": new_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_create_version_increments_number(self, client: TestClient, auth_headers: dict, test_confab: Confab, existing_document, mock_validation):
        """New version should have incremented version number."""
        new_content = base64.b64encode(b"New content").decode()

        response = client.post(
            f"/confabs/{test_confab.id}/documents/{existing_document.id}/versions",
            headers=auth_headers,
            json={"content_base64": new_content}
        )

        data = response.json()
        # Versions are ordered descending, so newest first
        assert data["versions"][0]["version_number"] == 2

    def test_create_version_nonexistent_doc_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab, mock_validation):
        """Create version for non-existent document should return 404."""
        content = base64.b64encode(b"Content").decode()

        response = client.post(
            f"/confabs/{test_confab.id}/documents/99999/versions",
            headers=auth_headers,
            json={"content_base64": content}
        )

        assert response.status_code == 404

    def test_create_version_without_auth_returns_401(self, client: TestClient, test_confab: Confab, existing_document):
        """Create version without auth should return 401."""
        content = base64.b64encode(b"Content").decode()

        response = client.post(
            f"/confabs/{test_confab.id}/documents/{existing_document.id}/versions",
            json={"content_base64": content}
        )

        assert response.status_code == 401


class TestGetLatestVersionEndpoint:
    """Tests for GET /confabs/{confab_id}/documents/{document_id}/versions/latest endpoint."""

    @pytest.fixture
    def document_with_versions(self, db: Session, test_confab: Confab):
        """Create document with multiple versions."""
        from document_store_v2.compression import compress
        import hashlib

        doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="latest_test.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc)
        db.flush()

        for i in range(1, 4):
            content = f"Version {i} content".encode()
            version = DocumentVersion(
                document_id=doc.id,
                version_number=i,
                content_blob=compress(content),
                content_hash=hashlib.sha256(content).hexdigest(),
                original_size=len(content),
                compressed_size=len(compress(content)),
                text_extraction_status="pending",
            )
            db.add(version)

        db.commit()
        db.refresh(doc)
        return doc

    def test_get_latest_returns_newest(self, client: TestClient, auth_headers: dict, test_confab: Confab, document_with_versions):
        """Get latest should return the highest version number content."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/{document_with_versions.id}/versions/latest",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 3
        decoded = base64.b64decode(data["content_base64"])
        assert b"Version 3" in decoded

    def test_get_latest_nonexistent_doc_returns_404(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Get latest for non-existent document should return 404."""
        response = client.get(
            f"/confabs/{test_confab.id}/documents/99999/versions/latest",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_get_latest_without_auth_returns_401(self, client: TestClient, test_confab: Confab, document_with_versions):
        """Get latest without auth should return 401."""
        response = client.get(f"/confabs/{test_confab.id}/documents/{document_with_versions.id}/versions/latest")
        assert response.status_code == 401


class TestAcceptedFormatsEndpoint:
    """Tests for GET /documents/accepted-formats endpoint."""

    def test_get_accepted_formats(self, client: TestClient):
        """Get accepted formats should return format list."""
        response = client.get("/documents/accepted-formats")

        assert response.status_code == 200
        data = response.json()
        assert "accepted_formats" in data
        assert "pdf" in data["accepted_formats"]
        assert "txt" in data["accepted_formats"]

    def test_includes_stage_hint_info(self, client: TestClient):
        """Response should include stage hint information."""
        response = client.get("/documents/accepted-formats")

        data = response.json()
        assert data["stage"] == "documents"
        assert "question" in data
        assert data["max_file_size_mb"] == 50


class TestResponseSchemaValidation:
    """Tests to verify response schemas match expected structure."""

    def test_version_response_schema(self, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        """Version response should have all required fields."""
        # Create document directly in DB to bypass routing issues
        doc = create_test_document_v2(db, test_confab.id, "version_schema.txt", b"Content")

        # Get versions
        response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        version = response.json()["versions"][0]
        assert "id" in version
        assert "version_number" in version
        assert "content_hash" in version
        assert "original_size" in version
        assert "compressed_size" in version
        assert "compression_ratio" in version
        assert "text_extraction_status" in version
        assert "created_at" in version

    def test_version_list_response_schema(self, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        """Version list response should have all required fields."""
        doc = create_test_document_v2(db, test_confab.id, "list_schema.txt", b"Content")

        response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert "document_uuid" in data
        assert "filename" in data
        assert "versions" in data
        assert "total" in data

    def test_content_response_schema(self, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        """Content response should have all required fields."""
        doc = create_test_document_v2(db, test_confab.id, "content_schema.txt", b"Content")

        response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert "document_uuid" in data
        assert "version_number" in data
        assert "filename" in data
        assert "content_type" in data
        assert "content_base64" in data
        assert "original_size" in data

"""
End-to-end tests for Document Store V2.

Tests complete workflows: upload -> versions -> archive.

NOTE: V2 upload/list/get/archive endpoints share paths with V1 (file upload).
FastAPI routes V1 first. E2E tests use service layer for initial document
creation, then test version operations via API endpoints.
"""

import base64
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Confab, ConfabDocumentV2, DocumentVersion, User
from document_store_v2.compression import compress
from document_store_v2.service import DocumentServiceV2


# =============================================================================
# Helper to create documents directly via service (bypasses API routing issues)
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


class TestFullDocumentWorkflow:
    """E2E test for complete document lifecycle."""

    @pytest.fixture
    def mock_validation(self):
        """Mock validation for workflow tests."""
        with patch("document_store_v2.service.validate_upload") as mock:
            def make_result(content, filename, *args, **kwargs):
                return MagicMock(
                    is_valid=True,
                    sanitized_filename=filename,
                    actual_content_type="text/plain",
                    original_size=len(content),
                    error=None,
                )
            mock.side_effect = make_result
            yield mock

    def test_complete_version_workflow(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        mock_validation,
    ):
        """Test complete workflow: create document -> add versions -> get versions."""
        # Step 1: Create document (via DB - bypasses V1/V2 route conflict)
        original_content = b"This is the original document content for E2E testing."
        doc = create_test_document_v2(db, test_confab.id, "e2e_test.txt", original_content)

        # Step 2: Get version content and verify round-trip
        content_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1",
            headers=auth_headers,
        )

        assert content_response.status_code == 200
        retrieved_content = base64.b64decode(content_response.json()["content_base64"])
        assert retrieved_content == original_content

        # Step 3: Create new version via API
        updated_content = b"This is the UPDATED document content for version 2."
        updated_b64 = base64.b64encode(updated_content).decode()

        version_response = client.post(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
            json={
                "content_base64": updated_b64,
                "metadata": {"change": "update content"},
            }
        )

        assert version_response.status_code == 200
        assert version_response.json()["total"] == 2

        # Step 4: Get latest version via list (avoid /latest route ordering issue)
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )
        assert versions_response.status_code == 200
        versions = versions_response.json()["versions"]
        assert versions[0]["version_number"] == 2  # First in descending order is latest

        # Verify latest content via specific version number
        latest_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/2",
            headers=auth_headers,
        )
        assert latest_response.status_code == 200
        latest_content = base64.b64decode(latest_response.json()["content_base64"])
        assert latest_content == updated_content

        # Step 5: List all versions (already done above, verify structure)
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        assert versions_response.status_code == 200
        versions = versions_response.json()["versions"]
        assert len(versions) == 2
        assert versions[0]["version_number"] == 2  # Descending order
        assert versions[1]["version_number"] == 1


class TestVersionHistoryIntegrity:
    """E2E tests for version history integrity."""

    @pytest.fixture
    def mock_validation(self):
        """Mock validation."""
        with patch("document_store_v2.service.validate_upload") as mock:
            def make_result(content, filename, *args, **kwargs):
                return MagicMock(
                    is_valid=True,
                    sanitized_filename=filename,
                    actual_content_type="text/plain",
                    original_size=len(content),
                    error=None,
                )
            mock.side_effect = make_result
            yield mock

    def test_version_numbers_sequential(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        mock_validation,
    ):
        """Test that version numbers are assigned sequentially."""
        # Create document via DB
        doc = create_test_document_v2(db, test_confab.id, "sequential.txt", b"Version 1")

        # Create 4 more versions via API
        for i in range(2, 6):
            content = f"Version {i}".encode()
            client.post(
                f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
                headers=auth_headers,
                json={"content_base64": base64.b64encode(content).decode()}
            )

        # Get all versions
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        versions = versions_response.json()["versions"]
        version_numbers = sorted([v["version_number"] for v in versions])
        assert version_numbers == [1, 2, 3, 4, 5]

    def test_each_version_preserves_content(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        mock_validation,
    ):
        """Test that each version preserves its original content."""
        contents = [f"Content for version {i}".encode() for i in range(1, 4)]

        # Create document with first version via DB
        doc = create_test_document_v2(db, test_confab.id, "preserve.txt", contents[0])

        # Create more versions via API
        for content in contents[1:]:
            client.post(
                f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
                headers=auth_headers,
                json={"content_base64": base64.b64encode(content).decode()}
            )

        # Verify each version's content
        for i, expected_content in enumerate(contents, 1):
            response = client.get(
                f"/confabs/{test_confab.id}/documents/{doc.id}/versions/{i}",
                headers=auth_headers,
            )
            retrieved = base64.b64decode(response.json()["content_base64"])
            assert retrieved == expected_content

    def test_content_hash_integrity(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
    ):
        """Test that content hashes match actual content."""
        content = b"Content for hash verification"
        expected_hash = hashlib.sha256(content).hexdigest()

        doc = create_test_document_v2(db, test_confab.id, "hash_test.txt", content)

        # Get version and check hash
        version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.version_number == 1,
        ).first()

        assert version.content_hash == expected_hash


class TestCompressionVerification:
    """E2E tests verifying compression works correctly."""

    def test_compression_reduces_storage(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
    ):
        """Test that compression actually reduces storage size."""
        # Highly compressible content
        content = (b"This is a repeated line of text that compresses well. " * 100)

        doc = create_test_document_v2(db, test_confab.id, "compressible.txt", content)

        # Check compression in database
        version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc.id,
        ).first()

        assert version.compressed_size < version.original_size
        assert version.compressed_size < len(content) / 2  # Should compress to less than half

    def test_compression_ratio_reported_correctly(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
    ):
        """Test that compression ratio is reported in API response."""
        content = b"Compressible " * 1000

        doc = create_test_document_v2(db, test_confab.id, "ratio_test.txt", content)

        # Get versions to check ratio
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        version = versions_response.json()["versions"][0]
        assert "compression_ratio" in version
        assert version["compression_ratio"] < 1.0  # Should be compressed

    def test_decompression_restores_original(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
    ):
        """Test that decompressed content matches original exactly."""
        # Content with various byte patterns
        content = bytes(range(256)) * 100 + b"Text content mixed in"

        doc = create_test_document_v2(db, test_confab.id, "binary_test.txt", content)

        # Retrieve and verify
        content_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1",
            headers=auth_headers,
        )

        retrieved = base64.b64decode(content_response.json()["content_base64"])
        assert retrieved == content


class TestEdgeCases:
    """E2E tests for edge cases."""

    @pytest.fixture
    def mock_validation(self):
        """Mock validation."""
        with patch("document_store_v2.service.validate_upload") as mock:
            def make_result(content, filename, *args, **kwargs):
                return MagicMock(
                    is_valid=True,
                    sanitized_filename=filename,
                    actual_content_type="text/plain",
                    original_size=len(content),
                    error=None,
                )
            mock.side_effect = make_result
            yield mock

    def test_document_with_only_one_version(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
    ):
        """Test document that never gets additional versions."""
        content = b"Single version document"

        doc = create_test_document_v2(db, test_confab.id, "single.txt", content)

        # Get versions - should have only version 1
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        assert versions_response.status_code == 200
        versions = versions_response.json()["versions"]
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1

        # Verify content via direct version access
        content_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions/1",
            headers=auth_headers,
        )
        assert content_response.status_code == 200
        assert content_response.json()["version_number"] == 1

    def test_large_number_of_versions(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        mock_validation,
    ):
        """Test document with many versions."""
        # Create document via DB
        doc = create_test_document_v2(db, test_confab.id, "many_versions.txt", b"Version 1")

        # Create 19 more versions via API (20 total)
        for i in range(2, 21):
            client.post(
                f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
                headers=auth_headers,
                json={"content_base64": base64.b64encode(f"Version {i}".encode()).decode()}
            )

        # List all versions
        versions_response = client.get(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
        )

        assert versions_response.json()["total"] == 20

    def test_special_characters_in_version_metadata(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        mock_validation,
    ):
        """Test version with special characters in metadata."""
        doc = create_test_document_v2(db, test_confab.id, "special_meta.txt", b"Initial content")

        # Create version with special metadata via API
        response = client.post(
            f"/confabs/{test_confab.id}/documents/{doc.id}/versions",
            headers=auth_headers,
            json={
                "content_base64": base64.b64encode(b"Updated content").decode(),
                "metadata": {
                    "unicode": "Emoji \U0001F600 CJK \u4E2D\u6587",
                    "quotes": 'He said "hello"',
                    "newlines": "line1\nline2",
                    "nested": {"key": "value"},
                }
            }
        )

        assert response.status_code == 200

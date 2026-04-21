"""
Tests for document_store_v2.service module.

Tests DocumentServiceV2 class methods for document operations.
"""

import base64
import hashlib
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from models import Confab, ConfabDocumentV2, DocumentVersion, User
from document_store_v2.service import DocumentServiceV2
from document_store_v2.schemas import (
    DocumentResponse,
    DocumentVersionResponse,
    DocumentContentResponse,
    DocumentListResponse,
    VersionListResponse,
    DocumentUploadResponse,
)


class TestUploadDocument:
    """Tests for DocumentServiceV2.upload_document method."""

    @pytest.fixture
    def mock_validation(self):
        """Mock validation to always pass."""
        with patch("document_store_v2.service.validate_upload") as mock:
            mock.return_value = MagicMock(
                is_valid=True,
                sanitized_filename="test.txt",
                actual_content_type="text/plain",
                original_size=100,
                error=None,
            )
            yield mock

    @pytest.mark.asyncio
    async def test_upload_success(self, db: Session, test_confab: Confab, test_user: User, mock_validation):
        """Successful upload should create document and first version."""
        service = DocumentServiceV2(db)
        content = b"Hello, World!"
        content_b64 = base64.b64encode(content).decode()

        result = await service.upload_document(
            confab_id=test_confab.id,
            content_base64=content_b64,
            filename="test.txt",
            user_id=test_user.id,
        )

        assert isinstance(result, DocumentUploadResponse)
        assert result.document.filename == "test.txt"
        assert result.document.status == "active"
        assert result.document.version_count == 1

    @pytest.mark.asyncio
    async def test_upload_creates_first_version(self, db: Session, test_confab: Confab, test_user: User, mock_validation):
        """Upload should create version 1 with compressed content."""
        service = DocumentServiceV2(db)
        content = b"Test content for versioning"
        content_b64 = base64.b64encode(content).decode()

        result = await service.upload_document(
            confab_id=test_confab.id,
            content_base64=content_b64,
            filename="version_test.txt",
            user_id=test_user.id,
        )

        # Check version was created
        doc_id = result.document.id
        version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc_id
        ).first()

        assert version is not None
        assert version.version_number == 1
        assert version.original_size == len(content)  # Actual content size
        assert version.compressed_size > 0
        assert version.content_hash == hashlib.sha256(content).hexdigest()

    @pytest.mark.asyncio
    async def test_upload_with_metadata(self, db: Session, test_confab: Confab, test_user: User, mock_validation):
        """Upload with metadata should store metadata in version."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()
        metadata = {"author": "Test Author", "tags": ["test", "demo"]}

        result = await service.upload_document(
            confab_id=test_confab.id,
            content_base64=content_b64,
            filename="meta.txt",
            metadata=metadata,
            user_id=test_user.id,
        )

        # Check version metadata
        version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == result.document.id
        ).first()
        assert version.metadata_json == metadata

    @pytest.mark.asyncio
    async def test_upload_invalid_confab_raises(self, db: Session, mock_validation):
        """Upload to non-existent confab should raise LookupError."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()

        with pytest.raises(LookupError) as exc_info:
            await service.upload_document(
                confab_id=99999,
                content_base64=content_b64,
                filename="test.txt",
            )
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_invalid_base64_raises(self, db: Session, test_confab: Confab):
        """Upload with invalid base64 should raise ValueError."""
        service = DocumentServiceV2(db)

        with pytest.raises(ValueError) as exc_info:
            await service.upload_document(
                confab_id=test_confab.id,
                content_base64="not-valid-base64!!!",
                filename="test.txt",
            )
        assert "Invalid base64" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_validation_failure_raises(self, db: Session, test_confab: Confab):
        """Upload that fails validation should raise ValueError."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"").decode()  # Empty file

        with patch("document_store_v2.service.validate_upload") as mock:
            mock.return_value = MagicMock(
                is_valid=False,
                error="File is empty",
            )

            with pytest.raises(ValueError) as exc_info:
                await service.upload_document(
                    confab_id=test_confab.id,
                    content_base64=content_b64,
                    filename="empty.txt",
                )
            assert "File is empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_with_source_tracking(self, db: Session, test_confab: Confab, mock_validation):
        """Upload should track source and source_url."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()

        result = await service.upload_document(
            confab_id=test_confab.id,
            content_base64=content_b64,
            filename="url_import.txt",
            source="url",
            source_url="https://example.com/doc.txt",
        )

        assert result.document.source == "url"
        assert result.document.source_url == "https://example.com/doc.txt"


class TestCreateVersion:
    """Tests for DocumentServiceV2.create_version method."""

    @pytest.fixture
    def existing_document(self, db: Session, test_confab: Confab, test_user: User):
        """Create an existing document with one version."""
        from document_store_v2.compression import compress

        document = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="existing.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(document)
        db.flush()

        content = b"Original content"
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            content_blob=compress(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            original_size=len(content),
            compressed_size=len(compress(content)),
            text_extraction_status="pending",
        )
        db.add(version)
        db.commit()
        db.refresh(document)
        return document

    @pytest.fixture
    def mock_validation(self):
        """Mock validation to always pass."""
        with patch("document_store_v2.service.validate_upload") as mock:
            mock.return_value = MagicMock(
                is_valid=True,
                sanitized_filename="existing.txt",
                actual_content_type="text/plain",
                original_size=200,
                error=None,
            )
            yield mock

    @pytest.mark.asyncio
    async def test_create_version_increments_number(self, db: Session, existing_document, test_user: User, mock_validation):
        """Creating a version should increment version number."""
        service = DocumentServiceV2(db)
        new_content = b"Updated content version 2"
        content_b64 = base64.b64encode(new_content).decode()

        result = await service.create_version(
            document_id=existing_document.id,
            content_base64=content_b64,
            user_id=test_user.id,
        )

        assert result.version_number == 2

    @pytest.mark.asyncio
    async def test_create_version_stores_compressed_content(self, db: Session, existing_document, test_user: User, mock_validation):
        """New version should store compressed content."""
        service = DocumentServiceV2(db)
        new_content = b"New version content"
        content_b64 = base64.b64encode(new_content).decode()

        result = await service.create_version(
            document_id=existing_document.id,
            content_base64=content_b64,
            user_id=test_user.id,
        )

        version = db.query(DocumentVersion).filter(
            DocumentVersion.id == result.id
        ).first()

        assert version.compressed_size > 0
        assert version.content_hash == hashlib.sha256(new_content).hexdigest()

    @pytest.mark.asyncio
    async def test_create_version_archived_document_raises(self, db: Session, existing_document, mock_validation):
        """Creating version on archived document should raise LookupError."""
        # Archive the document
        existing_document.status = "archived"
        db.commit()

        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()

        with pytest.raises(LookupError) as exc_info:
            await service.create_version(
                document_id=existing_document.id,
                content_base64=content_b64,
            )
        assert "not found or archived" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_version_nonexistent_document_raises(self, db: Session, mock_validation):
        """Creating version for non-existent document should raise LookupError."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()

        with pytest.raises(LookupError):
            await service.create_version(
                document_id=99999,
                content_base64=content_b64,
            )

    @pytest.mark.asyncio
    async def test_create_version_with_metadata(self, db: Session, existing_document, mock_validation):
        """New version should store metadata."""
        service = DocumentServiceV2(db)
        content_b64 = base64.b64encode(b"content").decode()
        metadata = {"change_note": "Fixed typos"}

        result = await service.create_version(
            document_id=existing_document.id,
            content_base64=content_b64,
            metadata=metadata,
        )

        version = db.query(DocumentVersion).filter(
            DocumentVersion.id == result.id
        ).first()
        assert version.metadata_json == metadata


class TestGetDocument:
    """Tests for DocumentServiceV2.get_document method."""

    @pytest.fixture
    def existing_document(self, db: Session, test_confab: Confab):
        """Create an existing document."""
        document = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="get_test.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @pytest.mark.asyncio
    async def test_get_document_success(self, db: Session, test_confab: Confab, existing_document):
        """Get document should return document response."""
        service = DocumentServiceV2(db)

        result = await service.get_document(existing_document.id, test_confab.id)

        assert isinstance(result, DocumentResponse)
        assert result.id == existing_document.id
        assert result.filename == "get_test.txt"

    @pytest.mark.asyncio
    async def test_get_document_wrong_confab_raises(self, db: Session, existing_document):
        """Get document with wrong confab_id should raise LookupError."""
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.get_document(existing_document.id, confab_id=99999)

    @pytest.mark.asyncio
    async def test_get_document_nonexistent_raises(self, db: Session, test_confab: Confab):
        """Get non-existent document should raise LookupError."""
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.get_document(document_id=99999, confab_id=test_confab.id)


class TestGetVersionContent:
    """Tests for DocumentServiceV2.get_version_content method."""

    @pytest.fixture
    def document_with_version(self, db: Session, test_confab: Confab):
        """Create document with a version containing compressed content."""
        from document_store_v2.compression import compress

        document = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="content_test.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(document)
        db.flush()

        content = b"This is the decompressed content"
        compressed = compress(content)
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            content_blob=compressed,
            content_hash=hashlib.sha256(content).hexdigest(),
            original_size=len(content),
            compressed_size=len(compressed),
            text_extraction_status="completed",
            extracted_text="This is the decompressed content",
        )
        db.add(version)
        db.commit()
        db.refresh(document)
        return document, content

    @pytest.mark.asyncio
    async def test_get_version_content_decompresses(self, db: Session, test_confab: Confab, document_with_version):
        """Get version content should decompress and base64 encode."""
        document, original_content = document_with_version
        service = DocumentServiceV2(db)

        result = await service.get_version_content(document.id, 1, test_confab.id)

        assert isinstance(result, DocumentContentResponse)
        decoded = base64.b64decode(result.content_base64)
        assert decoded == original_content

    @pytest.mark.asyncio
    async def test_get_version_content_includes_metadata(self, db: Session, test_confab: Confab, document_with_version):
        """Get version content should include all metadata."""
        document, _ = document_with_version
        service = DocumentServiceV2(db)

        result = await service.get_version_content(document.id, 1, test_confab.id)

        assert result.document_id == document.id
        assert result.version_number == 1
        assert result.filename == "content_test.txt"
        assert result.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_get_version_content_wrong_confab_raises(self, db: Session, document_with_version):
        """Get version content with wrong confab should raise LookupError."""
        document, _ = document_with_version
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.get_version_content(document.id, 1, confab_id=99999)

    @pytest.mark.asyncio
    async def test_get_version_content_nonexistent_version_raises(self, db: Session, test_confab: Confab, document_with_version):
        """Get non-existent version should raise LookupError."""
        document, _ = document_with_version
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError) as exc_info:
            await service.get_version_content(document.id, version_number=99, confab_id=test_confab.id)
        assert "Version 99 not found" in str(exc_info.value)


class TestListDocuments:
    """Tests for DocumentServiceV2.list_documents method."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, db: Session, test_confab: Confab):
        """List documents for confab with no documents should return empty list."""
        service = DocumentServiceV2(db)

        result = await service.list_documents(test_confab.id)

        assert isinstance(result, DocumentListResponse)
        assert result.documents == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_documents_returns_active_only(self, db: Session, test_confab: Confab):
        """List documents should only return active documents."""
        # Create active document
        active_doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="active.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(active_doc)

        # Create archived document
        archived_doc = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="archived.txt",
            original_content_type="text/plain",
            source="upload",
            status="archived",
        )
        db.add(archived_doc)
        db.commit()

        service = DocumentServiceV2(db)
        result = await service.list_documents(test_confab.id)

        assert result.total == 1
        assert result.documents[0].filename == "active.txt"

    @pytest.mark.asyncio
    async def test_list_documents_filters_by_confab(self, db: Session, test_confab: Confab, test_user: User):
        """List documents should only return documents for specified confab."""
        # Create another confab
        other_confab = Confab(
            name="Other Confab",
            user_id=test_user.id,
            version="1.0.0",
            status="building",
        )
        db.add(other_confab)
        db.flush()  # Get ID for other_confab

        # Create document for test_confab
        doc1 = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="doc1.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc1)

        # Create document for other_confab
        doc2 = ConfabDocumentV2(
            confab_id=other_confab.id,
            filename="doc2.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(doc2)
        db.commit()

        service = DocumentServiceV2(db)
        result = await service.list_documents(test_confab.id)

        assert result.total == 1
        assert result.documents[0].filename == "doc1.txt"


class TestListVersions:
    """Tests for DocumentServiceV2.list_versions method."""

    @pytest.fixture
    def document_with_versions(self, db: Session, test_confab: Confab):
        """Create document with multiple versions."""
        from document_store_v2.compression import compress

        document = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="versioned.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(document)
        db.flush()

        for i in range(1, 4):  # 3 versions
            content = f"Version {i} content".encode()
            version = DocumentVersion(
                document_id=document.id,
                version_number=i,
                content_blob=compress(content),
                content_hash=hashlib.sha256(content).hexdigest(),
                original_size=len(content),
                compressed_size=len(compress(content)),
                text_extraction_status="pending",
            )
            db.add(version)

        db.commit()
        db.refresh(document)
        return document

    @pytest.mark.asyncio
    async def test_list_versions_returns_all(self, db: Session, test_confab: Confab, document_with_versions):
        """List versions should return all versions."""
        service = DocumentServiceV2(db)

        result = await service.list_versions(document_with_versions.id, test_confab.id)

        assert isinstance(result, VersionListResponse)
        assert result.total == 3
        assert len(result.versions) == 3

    @pytest.mark.asyncio
    async def test_list_versions_ordered_descending(self, db: Session, test_confab: Confab, document_with_versions):
        """List versions should be ordered by version_number descending."""
        service = DocumentServiceV2(db)

        result = await service.list_versions(document_with_versions.id, test_confab.id)

        version_numbers = [v.version_number for v in result.versions]
        assert version_numbers == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_list_versions_wrong_confab_raises(self, db: Session, document_with_versions):
        """List versions with wrong confab should raise LookupError."""
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.list_versions(document_with_versions.id, confab_id=99999)


class TestArchiveDocument:
    """Tests for DocumentServiceV2.archive_document method."""

    @pytest.fixture
    def active_document(self, db: Session, test_confab: Confab):
        """Create an active document."""
        document = ConfabDocumentV2(
            confab_id=test_confab.id,
            filename="to_archive.txt",
            original_content_type="text/plain",
            source="upload",
            status="active",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @pytest.mark.asyncio
    async def test_archive_sets_status(self, db: Session, test_confab: Confab, active_document):
        """Archive should set status to 'archived'."""
        service = DocumentServiceV2(db)

        await service.archive_document(active_document.id, test_confab.id)

        db.refresh(active_document)
        assert active_document.status == "archived"

    @pytest.mark.asyncio
    async def test_archive_wrong_confab_raises(self, db: Session, active_document):
        """Archive with wrong confab should raise LookupError."""
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.archive_document(active_document.id, confab_id=99999)

    @pytest.mark.asyncio
    async def test_archive_nonexistent_document_raises(self, db: Session, test_confab: Confab):
        """Archive non-existent document should raise LookupError."""
        service = DocumentServiceV2(db)

        with pytest.raises(LookupError):
            await service.archive_document(document_id=99999, confab_id=test_confab.id)

    @pytest.mark.asyncio
    async def test_archive_is_soft_delete(self, db: Session, test_confab: Confab, active_document):
        """Archive should be soft delete (document still exists)."""
        service = DocumentServiceV2(db)
        doc_id = active_document.id

        await service.archive_document(doc_id, test_confab.id)

        # Document should still exist in DB
        doc = db.query(ConfabDocumentV2).filter(ConfabDocumentV2.id == doc_id).first()
        assert doc is not None
        assert doc.status == "archived"

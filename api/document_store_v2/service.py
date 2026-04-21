"""
Document Store V2 Service.

Provides versioned document storage with compression.
Encryption support will be added in Phase 2.
"""

import base64
import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import ConfabDocumentV2, DocumentVersion, Confab
from .compression import compress, decompress, get_compression_ratio
from .validation import validate_upload, ValidationResult
from .schemas import (
    DocumentResponse,
    DocumentVersionResponse,
    DocumentContentResponse,
    DocumentListResponse,
    VersionListResponse,
    DocumentUploadResponse,
)

logger = logging.getLogger(__name__)


class DocumentServiceV2:
    """
    Service for versioned document storage.

    Handles:
    - Document upload with validation and compression
    - Version creation (append-only)
    - Document retrieval with decompression
    - Document listing and archival
    """

    def __init__(self, db: Session):
        self.db = db

    async def upload_document(
        self,
        confab_id: int,
        content_base64: str,
        filename: str,
        declared_content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
        user_id: Optional[int] = None,
        source: str = "upload",
        source_url: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """
        Upload a new document.

        Args:
            confab_id: ID of the confab this document belongs to
            content_base64: Base64-encoded file content
            filename: Original filename
            declared_content_type: Content-Type header (verified via magic)
            metadata: Optional metadata dict
            user_id: ID of the uploading user
            source: Source of the document (upload, url, api)
            source_url: URL if document was imported from URL

        Returns:
            DocumentUploadResponse with created document

        Raises:
            ValueError: If validation fails
            LookupError: If confab not found
        """
        # Verify confab exists
        confab = self.db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            raise LookupError(f"Confab {confab_id} not found")

        # Decode base64 content
        try:
            content = base64.b64decode(content_base64)
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {e}")

        # Validate upload
        validation = validate_upload(content, filename, declared_content_type)
        if not validation.is_valid:
            raise ValueError(validation.error)

        # Create document record
        document = ConfabDocumentV2(
            confab_id=confab_id,
            filename=validation.sanitized_filename,
            original_content_type=validation.actual_content_type,
            source=source,
            source_url=source_url,
            status="active",
        )
        self.db.add(document)
        self.db.flush()  # Get ID for version

        # Compress content
        compressed = compress(content)

        # Calculate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Create first version
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            content_blob=compressed,
            content_hash=content_hash,
            original_size=len(content),
            compressed_size=len(compressed),
            metadata_json=metadata,
            created_by=user_id,
            text_extraction_status="pending",  # TODO: Extract text in Phase 3
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(document)

        logger.info(
            f"Uploaded document {document.id} ({document.filename}) "
            f"for confab {confab_id}, "
            f"compressed {len(content)} -> {len(compressed)} bytes "
            f"({get_compression_ratio(len(content), len(compressed)):.1%})"
        )

        return DocumentUploadResponse(
            document=self._to_document_response(document),
            message="Document uploaded successfully",
        )

    async def create_version(
        self,
        document_id: int,
        content_base64: str,
        metadata: Optional[dict] = None,
        user_id: Optional[int] = None,
    ) -> DocumentVersionResponse:
        """
        Create a new version of an existing document.

        Args:
            document_id: ID of the document
            content_base64: Base64-encoded new content
            metadata: Optional metadata for this version
            user_id: ID of the uploading user

        Returns:
            DocumentVersionResponse for the new version

        Raises:
            ValueError: If validation fails
            LookupError: If document not found
        """
        # Get document
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.status == "active",
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found or archived")

        # Decode base64 content
        try:
            content = base64.b64decode(content_base64)
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {e}")

        # Validate upload
        validation = validate_upload(content, document.filename, document.original_content_type)
        if not validation.is_valid:
            raise ValueError(validation.error)

        # Get next version number
        latest_version = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        # Compress content
        compressed = compress(content)

        # Calculate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Create version
        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version,
            content_blob=compressed,
            content_hash=content_hash,
            original_size=len(content),
            compressed_size=len(compressed),
            metadata_json=metadata,
            created_by=user_id,
            text_extraction_status="pending",
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        logger.info(
            f"Created version {next_version} for document {document_id}, "
            f"compressed {len(content)} -> {len(compressed)} bytes"
        )

        return self._to_version_response(version)

    async def get_document(self, document_id: int, confab_id: int) -> DocumentResponse:
        """
        Get document metadata.

        Args:
            document_id: ID of the document
            confab_id: ID of the confab (for authorization)

        Returns:
            DocumentResponse with document metadata

        Raises:
            LookupError: If document not found or doesn't belong to confab
        """
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.confab_id == confab_id,
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found")

        return self._to_document_response(document)

    async def get_version_content(
        self,
        document_id: int,
        version_number: int,
        confab_id: int,
    ) -> DocumentContentResponse:
        """
        Get decrypted, decompressed content for a specific version.

        Args:
            document_id: ID of the document
            version_number: Version number to retrieve
            confab_id: ID of the confab (for authorization)

        Returns:
            DocumentContentResponse with content

        Raises:
            LookupError: If document/version not found
        """
        # Get document (with auth check)
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.confab_id == confab_id,
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found")

        # Get version
        version = self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        ).first()
        if not version:
            raise LookupError(f"Version {version_number} not found for document {document_id}")

        # Decompress content
        content = decompress(version.content_blob)

        return DocumentContentResponse(
            document_id=document.id,
            document_uuid=str(document.document_uuid),
            version_number=version.version_number,
            filename=document.filename,
            content_type=document.original_content_type,
            content_base64=base64.b64encode(content).decode("utf-8"),
            original_size=version.original_size,
            extracted_text=version.extracted_text,
            metadata=version.metadata_json,
        )

    async def get_latest_version_content(
        self,
        document_id: int,
        confab_id: int,
    ) -> DocumentContentResponse:
        """
        Get content for the latest version.

        Args:
            document_id: ID of the document
            confab_id: ID of the confab (for authorization)

        Returns:
            DocumentContentResponse with latest content

        Raises:
            LookupError: If document not found or has no versions
        """
        # Get document (with auth check)
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.confab_id == confab_id,
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found")

        # Get latest version
        version = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not version:
            raise LookupError(f"No versions found for document {document_id}")

        return await self.get_version_content(document_id, version.version_number, confab_id)

    async def list_documents(self, confab_id: int) -> DocumentListResponse:
        """
        List all active documents for a confab.

        Args:
            confab_id: ID of the confab

        Returns:
            DocumentListResponse with list of documents
        """
        documents = (
            self.db.query(ConfabDocumentV2)
            .filter(
                ConfabDocumentV2.confab_id == confab_id,
                ConfabDocumentV2.status == "active",
            )
            .order_by(ConfabDocumentV2.created_at.desc())
            .all()
        )

        return DocumentListResponse(
            documents=[self._to_document_response(doc) for doc in documents],
            total=len(documents),
        )

    async def list_versions(self, document_id: int, confab_id: int) -> VersionListResponse:
        """
        List all versions of a document.

        Args:
            document_id: ID of the document
            confab_id: ID of the confab (for authorization)

        Returns:
            VersionListResponse with list of versions

        Raises:
            LookupError: If document not found
        """
        # Get document (with auth check)
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.confab_id == confab_id,
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found")

        versions = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .all()
        )

        return VersionListResponse(
            document_id=document.id,
            document_uuid=str(document.document_uuid),
            filename=document.filename,
            versions=[self._to_version_response(v) for v in versions],
            total=len(versions),
        )

    async def archive_document(self, document_id: int, confab_id: int) -> None:
        """
        Archive (soft delete) a document.

        Args:
            document_id: ID of the document
            confab_id: ID of the confab (for authorization)

        Raises:
            LookupError: If document not found
        """
        document = self.db.query(ConfabDocumentV2).filter(
            ConfabDocumentV2.id == document_id,
            ConfabDocumentV2.confab_id == confab_id,
        ).first()
        if not document:
            raise LookupError(f"Document {document_id} not found")

        document.status = "archived"
        self.db.commit()

        logger.info(f"Archived document {document_id}")

    def _to_document_response(self, document: ConfabDocumentV2) -> DocumentResponse:
        """Convert document model to response schema."""
        version_count = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document.id)
            .count()
        )

        latest_version = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )

        return DocumentResponse(
            id=document.id,
            document_uuid=str(document.document_uuid),
            confab_id=document.confab_id,
            filename=document.filename,
            content_type=document.original_content_type,
            source=document.source,
            source_url=document.source_url,
            status=document.status,
            version_count=version_count,
            latest_version=self._to_version_response(latest_version) if latest_version else None,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_version_response(self, version: DocumentVersion) -> DocumentVersionResponse:
        """Convert version model to response schema."""
        return DocumentVersionResponse(
            id=version.id,
            version_number=version.version_number,
            content_hash=version.content_hash,
            original_size=version.original_size,
            compressed_size=version.compressed_size,
            compression_ratio=get_compression_ratio(version.original_size, version.compressed_size),
            text_extraction_status=version.text_extraction_status or "pending",
            metadata=version.metadata_json,
            created_at=version.created_at,
            created_by=version.created_by,
        )

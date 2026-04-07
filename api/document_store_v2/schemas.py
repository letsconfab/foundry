"""
Pydantic schemas for Document Store V2 API.

These schemas define the request/response models for document operations.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class DocumentUploadRequest(BaseModel):
    """Request to upload a new document."""

    filename: str = Field(..., description="Original filename")
    content_base64: str = Field(..., description="Base64-encoded file content")
    content_type: Optional[str] = Field(
        None, description="Declared content type (verified via magic bytes)"
    )
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata (author, tags, etc.)"
    )


class DocumentVersionRequest(BaseModel):
    """Request to create a new version of an existing document."""

    content_base64: str = Field(..., description="Base64-encoded file content")
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata for this version"
    )


# =============================================================================
# Response Schemas
# =============================================================================


class DocumentVersionResponse(BaseModel):
    """Response for a single document version."""

    id: int
    version_number: int
    content_hash: str
    original_size: int
    compressed_size: int
    compression_ratio: float = Field(
        ..., description="Ratio of compressed to original size"
    )
    text_extraction_status: str
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Response for a document with version summary."""

    id: int
    document_uuid: str
    confab_id: int
    filename: str
    content_type: str
    source: str
    source_url: Optional[str] = None
    status: str
    version_count: int
    latest_version: Optional[DocumentVersionResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response for listing documents."""

    documents: list[DocumentResponse]
    total: int


class DocumentContentResponse(BaseModel):
    """Response with decrypted document content."""

    document_id: int
    document_uuid: str
    version_number: int
    filename: str
    content_type: str
    content_base64: str = Field(..., description="Decrypted, decompressed, base64-encoded content")
    original_size: int
    extracted_text: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""

    document: DocumentResponse
    message: str = "Document uploaded successfully"


class VersionListResponse(BaseModel):
    """Response for listing document versions."""

    document_id: int
    document_uuid: str
    filename: str
    versions: list[DocumentVersionResponse]
    total: int


# =============================================================================
# UI Hint Schemas (for Foreman integration)
# =============================================================================


class DocumentStageHint(BaseModel):
    """UI hint for the documents stage in Foreman."""

    stage: str = "documents"
    question: str = "Would you like to upload any reference documents?"
    ui_hint: str = "show_upload_panel"
    accepted_formats: list[str] = Field(
        default_factory=lambda: [
            "pdf", "docx", "xlsx", "txt", "md", "json", "yaml", "yml", "toml",
            "png", "jpg", "jpeg", "gif", "webp", "csv"
        ]
    )
    max_file_size_mb: int = 50

"""
Pydantic schemas for document store API.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    """Request to upload a document (for JSON API, not multipart)."""
    content: str = Field(..., description="Document content (text/markdown) or base64-encoded (PDF)")
    filename: str = Field(..., description="Original filename with extension")
    content_type: str = Field(..., description="MIME type: text/plain, text/markdown, application/pdf")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class DocumentResponse(BaseModel):
    """Response for a document."""
    id: int
    filename: str
    content_type: str
    source: str
    source_url: Optional[str] = None
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_content: Optional[str] = None  # Full content for text/markdown documents

    class Config:
        from_attributes = True


class DocumentListItem(BaseModel):
    """Lightweight document for list views."""
    id: int
    filename: str
    content_type: str
    chunk_count: int
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    document_id: int
    filename: str
    chunk_count: int
    status: str
    error_message: Optional[str] = None


class DocumentSearchRequest(BaseModel):
    """Request to search documents."""
    query: str = Field(..., description="Search query (natural language)")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")
    filter_type: Optional[str] = Field(default=None, description="Filter by type: document or learning")


class SearchResultItem(BaseModel):
    """Individual search result."""
    chunk_id: str
    document_id: int
    filename: str
    content: str
    score: float
    chunk_index: int
    source_type: str
    metadata: Dict[str, Any]


class DocumentSearchResponse(BaseModel):
    """Response from document search."""
    results: List[SearchResultItem]
    query: str
    total_results: int


class ContextRequest(BaseModel):
    """Request for RAG context."""
    query: str = Field(..., description="User's query")
    max_tokens: int = Field(default=2000, ge=100, le=8000, description="Maximum context length")


class ContextResponse(BaseModel):
    """Assembled context for RAG."""
    context: str
    sources: List[Dict[str, Any]]
    total_chunks: int


class DocumentStoreStats(BaseModel):
    """Document store statistics."""
    document_count: int
    total_chunks: int
    total_size_bytes: int
    embedding_model: str
    embedding_provider: str
    vector_store: Dict[str, Any]

"""
Document Store module for confab-specific RAG capabilities.

Provides:
- EmbeddingService: Provider abstraction for embeddings (sentence_transformers, ollama, openai)
- VectorStore: ChromaDB wrapper with per-confab collection isolation
- DocumentProcessor: Chunking and loading for text, markdown, PDF
- DocumentService: Main orchestrator for document operations
"""

from .embedding_service import EmbeddingService
from .vector_store import VectorStore
from .document_processor import DocumentProcessor
from .service import DocumentService
from .schemas import (
    DocumentUploadRequest,
    DocumentResponse,
    DocumentListItem,
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    ContextRequest,
    ContextResponse,
    DocumentStoreStats,
)

__all__ = [
    "EmbeddingService",
    "VectorStore",
    "DocumentProcessor",
    "DocumentService",
    "DocumentUploadRequest",
    "DocumentResponse",
    "DocumentListItem",
    "DocumentUploadResponse",
    "DocumentSearchRequest",
    "DocumentSearchResponse",
    "ContextRequest",
    "ContextResponse",
    "DocumentStoreStats",
]

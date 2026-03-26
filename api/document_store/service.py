"""
Document Service - main orchestrator for document store operations.

Coordinates:
- Document processing and chunking
- Embedding generation
- Vector storage and retrieval
- Database persistence
- Learning indexing
"""

import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from .embedding_service import EmbeddingService
from .vector_store import VectorStore, SearchResult
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of uploading a document."""
    document_id: int
    filename: str
    chunk_count: int
    status: str
    error_message: Optional[str] = None


@dataclass
class SearchResultWithSource:
    """Search result with source document info."""
    chunk_id: str
    document_id: int
    filename: str
    content: str
    score: float
    chunk_index: int
    source_type: str  # "document" or "learning"
    metadata: Dict[str, Any]


@dataclass
class ContextResult:
    """Assembled context for RAG."""
    context: str
    sources: List[Dict[str, Any]]
    total_chunks: int


class DocumentService:
    """
    Main service for document store operations.

    Usage:
        service = DocumentService(db_session)
        result = await service.upload_document(confab_id, content, filename, content_type)
        search_results = await service.search(confab_id, "query text")
    """

    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService = None,
        vector_store: VectorStore = None,
        document_processor: DocumentProcessor = None
    ):
        """
        Initialize document service.

        Args:
            db: SQLAlchemy database session
            embedding_service: Optional custom embedding service
            vector_store: Optional custom vector store
            document_processor: Optional custom document processor
        """
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()
        self.processor = document_processor or DocumentProcessor()

    def _get_upload_dir(self, confab_id: int) -> str:
        """Get upload directory for a confab."""
        base_dir = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "uploads"))
        upload_dir = os.path.join(base_dir, f"confab_{confab_id}")
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    async def upload_document(
        self,
        confab_id: int,
        content: str | bytes,
        filename: str,
        content_type: str,
        source: str = "upload",
        source_url: str = None,
        metadata: Dict[str, Any] = None
    ) -> UploadResult:
        """
        Upload and index a document.

        Args:
            confab_id: The confab ID
            content: Document content
            filename: Original filename
            content_type: MIME type
            source: Source type (upload, url, manual)
            source_url: URL if imported from web
            metadata: Optional metadata

        Returns:
            UploadResult with document ID and status
        """
        from models import ConfabDocument, DocumentChunk as DBDocumentChunk

        # Check for duplicates by content hash
        save_path = None
        if content_type == "application/pdf":
            save_path = os.path.join(self._get_upload_dir(confab_id), filename)

        try:
            # Process document
            processed, saved_path = await self.processor.process_document(
                content, filename, content_type, metadata, save_path
            )

            # Check for existing document with same hash
            existing = self.db.query(ConfabDocument).filter(
                ConfabDocument.confab_id == confab_id,
                ConfabDocument.content_hash == processed.content_hash
            ).first()

            if existing:
                return UploadResult(
                    document_id=existing.id,
                    filename=existing.filename,
                    chunk_count=existing.chunk_count,
                    status="duplicate",
                    error_message="Document with same content already exists"
                )

            # Create document record
            doc = ConfabDocument(
                confab_id=confab_id,
                filename=filename,
                content_type=content_type,
                source=source,
                source_url=source_url,
                content_hash=processed.content_hash,
                raw_content=processed.content if content_type != "application/pdf" else None,
                file_path=saved_path,
                chunk_count=len(processed.chunks),
                status="pending",
                metadata_json=processed.metadata
            )
            self.db.add(doc)
            self.db.flush()  # Get document ID

            # Generate embeddings
            chunk_texts = [c.content for c in processed.chunks]
            embeddings = await self.embedding_service.get_embeddings(chunk_texts)

            # Prepare chunks for vector store
            vector_chunks = []
            db_chunks = []

            for i, chunk in enumerate(processed.chunks):
                vector_id = f"doc_{doc.id}_chunk_{i}"

                vector_chunks.append({
                    "id": vector_id,
                    "content": chunk.content,
                    "document_id": doc.id,
                    "chunk_index": i,
                    "type": "document",
                    "metadata": {
                        "filename": filename,
                        **(chunk.metadata or {})
                    }
                })

                db_chunks.append(DBDocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk.content,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    vector_id=vector_id
                ))

            # Add to vector store
            await self.vector_store.add_chunks(confab_id, vector_chunks, embeddings)

            # Save chunks to database
            self.db.add_all(db_chunks)

            # Update document status
            doc.status = "indexed"
            self.db.commit()

            logger.info(f"Uploaded document {filename} with {len(processed.chunks)} chunks")

            return UploadResult(
                document_id=doc.id,
                filename=filename,
                chunk_count=len(processed.chunks),
                status="indexed"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to upload document: {e}")
            return UploadResult(
                document_id=0,
                filename=filename,
                chunk_count=0,
                status="failed",
                error_message=str(e)
            )

    async def list_documents(self, confab_id: int) -> List[Dict[str, Any]]:
        """List all documents for a confab."""
        from models import ConfabDocument

        docs = self.db.query(ConfabDocument).filter(
            ConfabDocument.confab_id == confab_id
        ).order_by(ConfabDocument.created_at.desc()).all()

        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "content_type": doc.content_type,
                "source": doc.source,
                "chunk_count": doc.chunk_count,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "metadata": doc.metadata_json
            }
            for doc in docs
        ]

    async def get_document(self, confab_id: int, document_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific document."""
        from models import ConfabDocument

        doc = self.db.query(ConfabDocument).filter(
            ConfabDocument.id == document_id,
            ConfabDocument.confab_id == confab_id
        ).first()

        if not doc:
            return None

        return {
            "id": doc.id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "source": doc.source,
            "source_url": doc.source_url,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "metadata": doc.metadata_json,
            "raw_content": doc.raw_content  # Only for text/markdown
        }

    async def delete_document(self, confab_id: int, document_id: int) -> bool:
        """Delete a document and its chunks."""
        from models import ConfabDocument

        doc = self.db.query(ConfabDocument).filter(
            ConfabDocument.id == document_id,
            ConfabDocument.confab_id == confab_id
        ).first()

        if not doc:
            return False

        # Delete from vector store
        await self.vector_store.delete_document_chunks(confab_id, document_id)

        # Delete file if exists
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        # Delete from database (cascades to chunks)
        self.db.delete(doc)
        self.db.commit()

        logger.info(f"Deleted document {document_id}")
        return True

    async def search(
        self,
        confab_id: int,
        query: str,
        top_k: int = 5,
        filter_type: str = None  # "document" or "learning"
    ) -> List[SearchResultWithSource]:
        """
        Search for relevant chunks.

        Args:
            confab_id: The confab ID
            query: Search query (natural language)
            top_k: Number of results
            filter_type: Optional filter by type

        Returns:
            List of search results with source info
        """
        from models import ConfabDocument

        # Generate query embedding
        query_embedding = await self.embedding_service.get_embedding(query)

        # Search vector store
        filter_metadata = {"type": filter_type} if filter_type else None
        results = await self.vector_store.search(
            confab_id, query_embedding, top_k, filter_metadata
        )

        # Enrich with document info
        enriched_results = []
        doc_cache = {}

        for result in results:
            doc_id = result.document_id
            if doc_id and doc_id not in doc_cache:
                doc = self.db.query(ConfabDocument).filter(
                    ConfabDocument.id == doc_id
                ).first()
                doc_cache[doc_id] = doc

            doc = doc_cache.get(doc_id)
            filename = doc.filename if doc else "unknown"

            enriched_results.append(SearchResultWithSource(
                chunk_id=result.chunk_id,
                document_id=doc_id or 0,
                filename=filename,
                content=result.content,
                score=result.score,
                chunk_index=result.metadata.get("chunk_index", 0),
                source_type=result.metadata.get("type", "document"),
                metadata=result.metadata
            ))

        return enriched_results

    async def get_context_for_query(
        self,
        confab_id: int,
        query: str,
        max_tokens: int = 2000
    ) -> ContextResult:
        """
        Get formatted context for a query (for RAG).

        Args:
            confab_id: The confab ID
            query: User's query
            max_tokens: Maximum context length (rough estimate: 4 chars per token)

        Returns:
            ContextResult with formatted context and sources
        """
        max_chars = max_tokens * 4  # Rough estimate

        # Get more results than needed, then trim
        results = await self.search(confab_id, query, top_k=10)

        context_parts = []
        sources = []
        current_length = 0

        for result in results:
            chunk_text = f"[Source: {result.filename}]\n{result.content}\n"
            if current_length + len(chunk_text) > max_chars:
                break

            context_parts.append(chunk_text)
            current_length += len(chunk_text)

            # Track source
            source_entry = {
                "document_id": result.document_id,
                "filename": result.filename,
                "chunk_index": result.chunk_index,
                "score": result.score
            }
            if source_entry not in sources:
                sources.append(source_entry)

        context = "\n---\n".join(context_parts)

        return ContextResult(
            context=context,
            sources=sources,
            total_chunks=len(context_parts)
        )

    async def index_learning(self, confab_id: int, learning_id: int) -> bool:
        """
        Index a single approved learning.

        Args:
            confab_id: The confab ID
            learning_id: The learning ID to index

        Returns:
            True if indexed successfully
        """
        from models import ConfabLearning

        learning = self.db.query(ConfabLearning).filter(
            ConfabLearning.id == learning_id,
            ConfabLearning.confab_id == confab_id,
            ConfabLearning.status == "approved"
        ).first()

        if not learning:
            return False

        # Process learning content
        processed, _ = await self.processor.process_document(
            learning.content,
            f"learning_{learning_id}.md",
            "text/markdown"
        )

        # Generate embeddings
        chunk_texts = [c.content for c in processed.chunks]
        embeddings = await self.embedding_service.get_embeddings(chunk_texts)

        # Prepare chunks for vector store
        vector_chunks = []
        for i, chunk in enumerate(processed.chunks):
            vector_id = f"learning_{learning_id}_chunk_{i}"
            vector_chunks.append({
                "id": vector_id,
                "content": chunk.content,
                "document_id": learning_id,  # Use learning_id as document_id for filtering
                "chunk_index": i,
                "type": "learning",
                "learning_id": learning_id,
                "metadata": {
                    "summary": learning.summary,
                    "tags": learning.tags
                }
            })

        # Add to vector store
        await self.vector_store.add_chunks(confab_id, vector_chunks, embeddings)

        logger.info(f"Indexed learning {learning_id} with {len(processed.chunks)} chunks")
        return True

    async def sync_learnings(self, confab_id: int) -> int:
        """
        Index all approved learnings for a confab.

        Returns:
            Number of learnings indexed
        """
        from models import ConfabLearning

        learnings = self.db.query(ConfabLearning).filter(
            ConfabLearning.confab_id == confab_id,
            ConfabLearning.status == "approved"
        ).all()

        count = 0
        for learning in learnings:
            if await self.index_learning(confab_id, learning.id):
                count += 1

        logger.info(f"Synced {count} learnings for confab {confab_id}")
        return count

    async def reindex_documents(self, confab_id: int) -> int:
        """
        Re-index all documents for a confab.

        Useful after changing embedding model.

        Returns:
            Number of documents reindexed
        """
        from models import ConfabDocument

        # Clear existing vectors
        await self.vector_store.clear_collection(confab_id)

        # Re-index each document
        docs = self.db.query(ConfabDocument).filter(
            ConfabDocument.confab_id == confab_id,
            ConfabDocument.status == "indexed"
        ).all()

        count = 0
        for doc in docs:
            content = doc.raw_content
            if not content and doc.file_path:
                with open(doc.file_path, 'rb') as f:
                    content = f.read()

            if content:
                result = await self.upload_document(
                    confab_id,
                    content,
                    doc.filename,
                    doc.content_type,
                    doc.source,
                    doc.source_url,
                    doc.metadata_json
                )
                if result.status == "indexed":
                    count += 1

        # Also reindex learnings
        await self.sync_learnings(confab_id)

        logger.info(f"Reindexed {count} documents for confab {confab_id}")
        return count

    async def clear_document_store(self, confab_id: int) -> bool:
        """
        Delete all documents and vectors for a confab.

        Returns:
            True if cleared successfully
        """
        from models import ConfabDocument

        # Delete all documents (cascades to chunks)
        docs = self.db.query(ConfabDocument).filter(
            ConfabDocument.confab_id == confab_id
        ).all()

        for doc in docs:
            if doc.file_path and os.path.exists(doc.file_path):
                os.remove(doc.file_path)
            self.db.delete(doc)

        # Clear vector collection
        await self.vector_store.clear_collection(confab_id)

        self.db.commit()

        logger.info(f"Cleared document store for confab {confab_id}")
        return True

    async def get_stats(self, confab_id: int) -> Dict[str, Any]:
        """Get document store statistics."""
        from models import ConfabDocument

        docs = self.db.query(ConfabDocument).filter(
            ConfabDocument.confab_id == confab_id
        ).all()

        total_chunks = sum(doc.chunk_count for doc in docs)
        total_size = sum(
            len(doc.raw_content) if doc.raw_content else 0
            for doc in docs
        )

        vector_stats = await self.vector_store.get_collection_stats(confab_id)

        return {
            "document_count": len(docs),
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "vector_store": vector_stats,
            "embedding_model": self.embedding_service.model_name,
            "embedding_provider": self.embedding_service.provider_name
        }

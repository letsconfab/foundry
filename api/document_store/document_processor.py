"""
Document processor for loading and chunking documents.

Supports:
- Plain text (.txt)
- Markdown (.md)
- PDF (.pdf)
"""

import os
import hashlib
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import tempfile
import base64

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of a document."""
    content: str
    chunk_index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessedDocument:
    """Result of processing a document."""
    content: str  # Full content (for text/markdown)
    chunks: List[DocumentChunk]
    content_hash: str
    metadata: Dict[str, Any]


class DocumentProcessor:
    """
    Processes documents into chunks for embedding.

    Uses LangChain's RecursiveCharacterTextSplitter for intelligent chunking.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        Initialize processor.

        Args:
            chunk_size: Target chunk size in characters (default from env or 500)
            chunk_overlap: Overlap between chunks (default from env or 50)
        """
        self.chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "50"))

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        logger.info(f"Initialized DocumentProcessor with chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _chunk_text(self, text: str) -> List[DocumentChunk]:
        """Split text into chunks with position tracking."""
        if not text.strip():
            return []

        # Use LangChain splitter
        chunks = self._splitter.split_text(text)

        result = []
        current_pos = 0

        for i, chunk_content in enumerate(chunks):
            # Find position in original text
            start = text.find(chunk_content, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_content)
            current_pos = end - self.chunk_overlap  # Account for overlap

            result.append(DocumentChunk(
                content=chunk_content,
                chunk_index=i,
                start_char=start,
                end_char=end
            ))

        return result

    async def process_text(
        self,
        content: str,
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> ProcessedDocument:
        """
        Process plain text content.

        Args:
            content: Text content
            filename: Original filename
            metadata: Optional metadata

        Returns:
            ProcessedDocument with chunks
        """
        chunks = self._chunk_text(content)
        content_hash = self._compute_hash(content)

        return ProcessedDocument(
            content=content,
            chunks=chunks,
            content_hash=content_hash,
            metadata=metadata or {}
        )

    async def process_markdown(
        self,
        content: str,
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> ProcessedDocument:
        """
        Process markdown content.

        For now, treats markdown as text. Future: could use markdown-aware splitting.
        """
        # Strip YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        return await self.process_text(content, filename, metadata)

    async def process_pdf(
        self,
        content: bytes,
        filename: str,
        metadata: Dict[str, Any] = None,
        save_path: str = None
    ) -> Tuple[ProcessedDocument, Optional[str]]:
        """
        Process PDF content.

        Args:
            content: PDF bytes (or base64 string)
            filename: Original filename
            metadata: Optional metadata
            save_path: Optional path to save the PDF file

        Returns:
            Tuple of (ProcessedDocument, saved_file_path or None)
        """
        from pypdf import PdfReader
        import io

        # Handle base64 encoded content
        if isinstance(content, str):
            content = base64.b64decode(content)

        # Save file if path provided
        saved_path = None
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(content)
            saved_path = save_path

        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(content))
        text_parts = []

        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {page_num + 1}]\n{page_text}")

        full_text = "\n\n".join(text_parts)

        # Process as text
        chunks = self._chunk_text(full_text)
        content_hash = self._compute_hash(full_text)

        return ProcessedDocument(
            content=full_text,
            chunks=chunks,
            content_hash=content_hash,
            metadata={
                **(metadata or {}),
                "page_count": len(pdf_reader.pages),
                "pdf_metadata": dict(pdf_reader.metadata) if pdf_reader.metadata else {}
            }
        ), saved_path

    async def process_document(
        self,
        content: str | bytes,
        filename: str,
        content_type: str,
        metadata: Dict[str, Any] = None,
        save_path: str = None
    ) -> Tuple[ProcessedDocument, Optional[str]]:
        """
        Process a document based on content type.

        Args:
            content: Document content (text or bytes)
            filename: Original filename
            content_type: MIME type
            metadata: Optional metadata
            save_path: Optional path to save file (for PDFs)

        Returns:
            Tuple of (ProcessedDocument, saved_file_path or None)
        """
        if content_type == "application/pdf":
            return await self.process_pdf(content, filename, metadata, save_path)
        elif content_type == "text/markdown":
            doc = await self.process_markdown(content, filename, metadata)
            return doc, None
        else:  # text/plain and others
            doc = await self.process_text(content, filename, metadata)
            return doc, None

    def estimate_chunks(self, content_length: int) -> int:
        """Estimate number of chunks for a given content length."""
        if content_length <= self.chunk_size:
            return 1
        effective_chunk_size = self.chunk_size - self.chunk_overlap
        return max(1, (content_length - self.chunk_overlap) // effective_chunk_size + 1)

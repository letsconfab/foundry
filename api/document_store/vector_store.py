"""
ChromaDB vector store wrapper with per-confab collection isolation.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector search."""
    chunk_id: str
    document_id: int
    content: str
    score: float
    metadata: Dict[str, Any]


class VectorStore:
    """
    ChromaDB wrapper with per-confab collection isolation.

    Each confab gets its own collection named `confab_{confab_id}_documents`.
    Supports both documents and learnings in the same collection with type metadata.
    """

    def __init__(self, persist_directory: str = None):
        """
        Initialize ChromaDB client.

        Args:
            persist_directory: Directory for persistent storage.
                              Defaults to CHROMADB_PERSIST_DIR env var or ./data/chromadb
        """
        self.persist_directory = persist_directory or os.getenv(
            "CHROMADB_PERSIST_DIR",
            os.path.join(os.path.dirname(__file__), "..", "data", "chromadb")
        )

        # Ensure directory exists
        os.makedirs(self.persist_directory, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        logger.info(f"Initialized ChromaDB at {self.persist_directory}")

    def _collection_name(self, confab_id: int) -> str:
        """Generate collection name for a confab."""
        return f"confab_{confab_id}_documents"

    def _get_or_create_collection(self, confab_id: int):
        """Get or create a collection for a confab."""
        return self._client.get_or_create_collection(
            name=self._collection_name(confab_id),
            metadata={"confab_id": confab_id}
        )

    async def add_chunks(
        self,
        confab_id: int,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> List[str]:
        """
        Add document chunks to the vector store.

        Args:
            confab_id: The confab ID
            chunks: List of chunk dicts with keys: id, content, document_id, chunk_index, metadata
            embeddings: Corresponding embeddings for each chunk

        Returns:
            List of vector IDs assigned to the chunks
        """
        if not chunks:
            return []

        collection = self._get_or_create_collection(confab_id)

        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["content"] for chunk in chunks]
        metadatas = []

        for chunk in chunks:
            meta = {
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "type": chunk.get("type", "document"),  # "document" or "learning"
            }
            if chunk.get("metadata"):
                meta.update(chunk["metadata"])
            metadatas.append(meta)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        logger.info(f"Added {len(chunks)} chunks to collection {self._collection_name(confab_id)}")
        return ids

    async def search(
        self,
        confab_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Search for similar chunks.

        Args:
            confab_id: The confab ID
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"type": "document"})

        Returns:
            List of SearchResult objects sorted by similarity
        """
        collection = self._get_or_create_collection(confab_id)

        where = filter_metadata if filter_metadata else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances, convert to similarity score
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1.0 / (1.0 + distance)  # Convert distance to similarity

                search_results.append(SearchResult(
                    chunk_id=chunk_id,
                    document_id=results["metadatas"][0][i].get("document_id"),
                    content=results["documents"][0][i] if results["documents"] else "",
                    score=score,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {}
                ))

        return search_results

    async def delete_document_chunks(self, confab_id: int, document_id: int) -> int:
        """
        Delete all chunks for a specific document.

        Args:
            confab_id: The confab ID
            document_id: The document ID to delete chunks for

        Returns:
            Number of chunks deleted
        """
        collection = self._get_or_create_collection(confab_id)

        # Get chunks to delete
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas"]
        )

        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")
            return len(results["ids"])

        return 0

    async def delete_learning_chunks(self, confab_id: int, learning_id: int) -> int:
        """
        Delete all chunks for a specific learning.

        Args:
            confab_id: The confab ID
            learning_id: The learning ID to delete chunks for

        Returns:
            Number of chunks deleted
        """
        collection = self._get_or_create_collection(confab_id)

        # Get chunks to delete
        results = collection.get(
            where={"$and": [{"type": "learning"}, {"learning_id": learning_id}]},
            include=["metadatas"]
        )

        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for learning {learning_id}")
            return len(results["ids"])

        return 0

    async def clear_collection(self, confab_id: int) -> bool:
        """
        Delete entire collection for a confab.

        Args:
            confab_id: The confab ID

        Returns:
            True if collection was deleted
        """
        collection_name = self._collection_name(confab_id)
        try:
            self._client.delete_collection(collection_name)
            logger.info(f"Deleted collection {collection_name}")
            return True
        except ValueError:
            # Collection doesn't exist
            return False

    async def get_collection_stats(self, confab_id: int) -> Dict[str, Any]:
        """
        Get statistics for a confab's collection.

        Returns:
            Dict with count, documents, learnings counts
        """
        collection = self._get_or_create_collection(confab_id)

        total_count = collection.count()

        # Count by type
        doc_results = collection.get(
            where={"type": "document"},
            include=[]
        )
        doc_count = len(doc_results["ids"]) if doc_results["ids"] else 0

        learning_results = collection.get(
            where={"type": "learning"},
            include=[]
        )
        learning_count = len(learning_results["ids"]) if learning_results["ids"] else 0

        return {
            "total_chunks": total_count,
            "document_chunks": doc_count,
            "learning_chunks": learning_count,
            "collection_name": self._collection_name(confab_id)
        }

    async def collection_exists(self, confab_id: int) -> bool:
        """Check if a collection exists for the confab."""
        collection_name = self._collection_name(confab_id)
        try:
            self._client.get_collection(collection_name)
            return True
        except ValueError:
            return False

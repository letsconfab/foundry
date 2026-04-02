"""
Embedding service with provider abstraction.

Supports:
- sentence_transformers (default, local): all-MiniLM-L6-v2
- ollama (local): nomic-embed-text
- openai (external): text-embedding-3-small
"""

import os
import logging
from typing import List, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions for this provider."""
        pass


class SentenceTransformersProvider(EmbeddingProvider):
    """Local embedding using Sentence Transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimensions = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-MiniLM-L6-v2": 384,
        }

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    @property
    def dimensions(self) -> int:
        return self._dimensions.get(self.model_name, 384)


class OllamaProvider(EmbeddingProvider):
    """Local embedding using Ollama."""

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: str = None
    ):
        self.model_name = model_name
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._dimensions = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
        }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        import httpx

        embeddings = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": text}
                )
                response.raise_for_status()
                result = response.json()
                embeddings.append(result["embedding"])
        return embeddings

    @property
    def dimensions(self) -> int:
        return self._dimensions.get(self.model_name, 768)


class OpenAIProvider(EmbeddingProvider):
    """External embedding using OpenAI API."""

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: str = None
    ):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var.")
        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.embeddings.create(
            model=self.model_name,
            input=texts
        )
        return [item.embedding for item in response.data]

    @property
    def dimensions(self) -> int:
        return self._dimensions.get(self.model_name, 1536)


class EmbeddingService:
    """
    Main embedding service with provider abstraction.

    Usage:
        service = EmbeddingService(provider="sentence_transformers")
        embeddings = await service.get_embeddings(["hello world", "another text"])
    """

    PROVIDERS = {
        "sentence_transformers": SentenceTransformersProvider,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
    }

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        **kwargs
    ):
        """
        Initialize embedding service.

        Args:
            provider: One of "sentence_transformers", "ollama", "openai"
            model: Model name for the provider
            **kwargs: Additional provider-specific arguments
        """
        provider = provider or os.getenv("EMBEDDING_PROVIDER", "sentence_transformers")
        model = model or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        if provider not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Choose from: {list(self.PROVIDERS.keys())}")

        provider_class = self.PROVIDERS[provider]

        # Map model arg to provider-specific kwarg
        if provider == "sentence_transformers":
            self._provider = provider_class(model_name=model, **kwargs)
        elif provider == "ollama":
            self._provider = provider_class(model_name=model, **kwargs)
        elif provider == "openai":
            self._provider = provider_class(model_name=model, **kwargs)
        else:
            self._provider = provider_class(**kwargs)

        self.provider_name = provider
        self.model_name = model
        logger.info(f"Initialized EmbeddingService with {provider}/{model}")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []
        return await self._provider.get_embeddings(texts)

    async def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.get_embeddings([text])
        return embeddings[0] if embeddings else []

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for the current provider/model."""
        return self._provider.dimensions

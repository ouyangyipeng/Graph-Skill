"""
Embedding generation service for query vectorization.

Implements RFC-03 Section 3.4: Embedding 生成规范.
MUST use the same embedding model as skill vectors to ensure
cosine similarity is meaningful.

Supports two backends:
  - sentence-transformers (local, offline)
  - OpenAI-compatible API (remote, e.g. text-embedding-3-small)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

from graphskill.core.exceptions import EmbeddingTimeoutError, RoutingError

logger = logging.getLogger(__name__)


class EmbeddingGenerationError(RoutingError):
    """Embedding generation failed."""

    def __init__(self, message: str, model_name: str = ""):
        details = {"model_name": model_name} if model_name else {}
        super().__init__(message, details=details)
        self.code = "GS-2004"


class EmbeddingDimensionMismatchError(RoutingError):
    """Embedding dimension does not match expected dimension."""

    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"Embedding dimension mismatch: expected {expected}, got {actual}",
            details={"expected": expected, "actual": actual},
        )
        self.code = "GS-2005"


class EmbeddingService:
    """Embedding generation service.

    Generates query vectors using the same model as skill embeddings
    to ensure cosine similarity is well-defined.

    Args:
        model_name: Model identifier. For sentence-transformers, use
            model hub names (e.g. 'all-MiniLM-L6-v2'). For OpenAI-compatible,
            use API model names (e.g. 'text-embedding-3-small').
        dimension: Expected embedding dimension.
        backend: 'sentence-transformers' or 'openai'.
        api_base: Optional base URL for OpenAI-compatible endpoint.
        api_key: Optional API key for OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
        backend: str = "sentence-transformers",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self.backend = backend
        self.api_base = api_base
        self.api_key = api_key
        self.device = device

        self._model: Any = None
        self._client: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy-initialize the embedding backend."""
        if self._initialized:
            return

        if self.backend == "sentence-transformers":
            self._init_sentence_transformers()
        elif self.backend == "openai":
            self._init_openai()
        else:
            raise EmbeddingGenerationError(
                f"Unknown embedding backend: {self.backend}",
                model_name=self.model_name,
            )

        self._initialized = True

    def _init_sentence_transformers(self) -> None:
        """Initialize sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            # Update dimension from actual model if available
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self.dimension:
                logger.info(
                    f"Embedding dimension auto-corrected: {self.dimension} -> {actual_dim}"
                )
                self.dimension = actual_dim
            logger.info(f"Sentence-transformers model loaded: {self.model_name} (dim={self.dimension})")
        except ImportError:
            raise EmbeddingGenerationError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers",
                model_name=self.model_name,
            )
        except Exception as e:
            raise EmbeddingGenerationError(
                f"Failed to load sentence-transformers model: {e}",
                model_name=self.model_name,
            )

    def _init_openai(self) -> None:
        """Initialize OpenAI-compatible embedding client."""
        try:
            import openai

            client_kwargs: dict[str, Any] = {}
            if self.api_key:
                client_kwargs["api_key"] = self.api_key
            if self.api_base:
                client_kwargs["base_url"] = self.api_base

            self._client = openai.OpenAI(**client_kwargs)
            logger.info(f"OpenAI-compatible client initialized: {self.api_base or 'default'}")
        except ImportError:
            raise EmbeddingGenerationError(
                "openai is not installed. Install with: pip install openai",
                model_name=self.model_name,
            )
        except Exception as e:
            raise EmbeddingGenerationError(
                f"Failed to initialize OpenAI client: {e}",
                model_name=self.model_name,
            )

    async def generate(self, text: str) -> np.ndarray:
        """Generate embedding vector for input text.

        Args:
            text: Input text to embed.

        Returns:
            np.ndarray of shape (dimension,) with float32 values.

        Raises:
            EmbeddingGenerationError: On generation failure.
            EmbeddingDimensionMismatchError: If dimension doesn't match.
        """
        self._ensure_initialized()

        start = time.perf_counter()
        try:
            if self.backend == "sentence-transformers":
                vector = self._generate_st(text)
            else:
                vector = self._generate_openai(text)

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.debug(f"Embedding generated in {elapsed_ms}ms (dim={len(vector)})")

            return vector

        except (EmbeddingGenerationError, EmbeddingDimensionMismatchError):
            raise
        except Exception as e:
            raise EmbeddingGenerationError(
                f"Embedding generation failed: {e}",
                model_name=self.model_name,
            )

    def _generate_st(self, text: str) -> np.ndarray:
        """Generate embedding using sentence-transformers."""
        vector = self._model.encode(text, normalize_embeddings=True)
        arr = np.array(vector, dtype=np.float32)

        if arr.shape[0] != self.dimension:
            raise EmbeddingDimensionMismatchError(
                expected=self.dimension, actual=arr.shape[0]
            )

        return arr

    def _generate_openai(self, text: str) -> np.ndarray:
        """Generate embedding using OpenAI-compatible API."""
        response = self._client.embeddings.create(
            model=self.model_name,
            input=text,
            encoding_format="float",
        )

        vector = np.array(response.data[0].embedding, dtype=np.float32)

        if vector.shape[0] != self.dimension:
            raise EmbeddingDimensionMismatchError(
                expected=self.dimension, actual=vector.shape[0]
            )

        return vector

    @staticmethod
    def compute_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector.
            vec2: Second vector.

        Returns:
            Cosine similarity in [-1, 1].
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

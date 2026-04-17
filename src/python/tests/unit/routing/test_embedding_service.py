"""Unit tests for EmbeddingService."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from graphskill.routing.embedding_service import (
    EmbeddingService,
    EmbeddingGenerationError,
    EmbeddingDimensionMismatchError,
)


class TestEmbeddingServiceComputeSimilarity:
    """Tests for the static compute_similarity method (no backend needed)."""

    def test_identical_vectors(self) -> None:
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        sim = EmbeddingService.compute_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        vec1 = np.array([1.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0], dtype=np.float32)
        sim = EmbeddingService.compute_similarity(vec1, vec2)
        assert abs(sim) < 1e-6

    def test_opposite_vectors(self) -> None:
        vec1 = np.array([1.0, 0.0], dtype=np.float32)
        vec2 = np.array([-1.0, 0.0], dtype=np.float32)
        sim = EmbeddingService.compute_similarity(vec1, vec2)
        assert abs(sim + 1.0) < 1e-6

    def test_zero_vector(self) -> None:
        vec1 = np.array([1.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 0.0], dtype=np.float32)
        sim = EmbeddingService.compute_similarity(vec1, vec2)
        assert sim == 0.0

    def test_arbitrary_vectors(self) -> None:
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        sim = EmbeddingService.compute_similarity(vec1, vec2)
        # Expected: (4+10+18) / (sqrt(14) * sqrt(77)) ≈ 0.9746
        assert 0.9 < sim < 1.0


class TestEmbeddingServiceInit:
    """Tests for EmbeddingService initialization."""

    def test_default_config(self) -> None:
        svc = EmbeddingService()
        assert svc.model_name == "all-MiniLM-L6-v2"
        assert svc.dimension == 384
        assert svc.backend == "sentence-transformers"
        assert svc._initialized is False

    def test_custom_config(self) -> None:
        svc = EmbeddingService(
            model_name="text-embedding-3-small",
            dimension=1536,
            backend="openai",
            api_base="https://api.example.com",
            api_key="test-key",
        )
        assert svc.model_name == "text-embedding-3-small"
        assert svc.dimension == 1536
        assert svc.backend == "openai"

    def test_unknown_backend_raises(self) -> None:
        svc = EmbeddingService(backend="nonexistent")
        with pytest.raises(EmbeddingGenerationError, match="Unknown embedding backend"):
            import asyncio
            asyncio.run(svc.generate("test"))


class TestEmbeddingServiceWithMock:
    """Tests for EmbeddingService.generate() with mocked backends."""

    def test_sentence_transformers_mock(self) -> None:
        """Test generate with a mocked sentence-transformers model."""
        svc = EmbeddingService(dimension=4)

        # Mock the model
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        mock_model.get_sentence_embedding_dimension.return_value = 4
        svc._model = mock_model
        svc._initialized = True

        import asyncio
        result = asyncio.run(svc.generate("test query"))
        assert result.shape == (4,)
        assert result.dtype == np.float32

    def test_dimension_mismatch_raises(self) -> None:
        """Test that dimension mismatch raises EmbeddingDimensionMismatchError."""
        svc = EmbeddingService(dimension=4)

        mock_model = MagicMock()
        # Return vector of wrong dimension
        mock_model.encode.return_value = np.array([0.1, 0.2], dtype=np.float32)
        mock_model.get_sentence_embedding_dimension.return_value = 2
        svc._model = mock_model
        svc._initialized = True

        import asyncio
        with pytest.raises(EmbeddingDimensionMismatchError):
            asyncio.run(svc.generate("test query"))

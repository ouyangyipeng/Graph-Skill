"""
EWMA reliability decay engine unit tests per RFC-05 Section 5.

Tests ReliabilityDecayEngine: EWMA formula, bounds, deprecation,
recovery, batch computation, and async graph store integration.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from graphskill.telemetry.models import DecayConfig
from graphskill.telemetry.decay import ReliabilityDecayEngine


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_config() -> DecayConfig:
    """Default decay config per RFC-05 Section 5.4."""
    return DecayConfig()


@pytest.fixture
def custom_config() -> DecayConfig:
    """Custom decay config for testing."""
    return DecayConfig(
        decay_factor=0.9,
        min_reliability=0.2,
        deprecation_threshold=0.4,
        consecutive_failure_threshold=3,
        recovery_enabled=True,
        full_recovery_threshold=0.85,
    )


@pytest.fixture
def decay_engine(default_config: DecayConfig) -> ReliabilityDecayEngine:
    """Create decay engine without graph store (pure computation)."""
    return ReliabilityDecayEngine(config=default_config)


@pytest.fixture
def decay_engine_custom(custom_config: DecayConfig) -> ReliabilityDecayEngine:
    """Create decay engine with custom config."""
    return ReliabilityDecayEngine(config=custom_config)


@pytest.fixture
def mock_graph_store() -> MagicMock:
    """Create mock graph store."""
    store = MagicMock()
    store.get_node = AsyncMock(return_value={
        "uid": "skill:test",
        "execution_success_rate": 0.8,
        "execution_count": 100,
        "is_deprecated": False,
    })
    store.update_node = AsyncMock(return_value={"success": True})
    return store


@pytest.fixture
def decay_engine_with_store(
    mock_graph_store: MagicMock,
    default_config: DecayConfig,
) -> ReliabilityDecayEngine:
    """Create decay engine with mock graph store."""
    return ReliabilityDecayEngine(
        graph_store=mock_graph_store,
        config=default_config,
    )


# ============================================================================
# EWMA Formula Tests (Pure Computation)
# ============================================================================


class TestEWMAFormula:
    """EWMA formula computation tests (RFC-05 Section 5.2)."""

    def test_success_high_reliability(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: success with high current reliability.

        R_new = 0.95 * 0.9 + 0.05 * 1.0 = 0.855 + 0.05 = 0.905
        """
        result = decay_engine.update_reliability(0.9, success=True)
        assert result == pytest.approx(0.905, abs=0.001)

    def test_failure_high_reliability(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: failure with high current reliability.

        R_new = 0.95 * 0.9 + 0.05 * 0.0 = 0.855
        """
        result = decay_engine.update_reliability(0.9, success=False)
        assert result == pytest.approx(0.855, abs=0.001)

    def test_success_low_reliability(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: success with low current reliability.

        R_new = 0.95 * 0.3 + 0.05 * 1.0 = 0.285 + 0.05 = 0.335
        """
        result = decay_engine.update_reliability(0.3, success=True)
        assert result == pytest.approx(0.335, abs=0.001)

    def test_failure_low_reliability(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: failure with low current reliability.

        R_new = 0.95 * 0.3 + 0.05 * 0.0 = 0.285
        """
        result = decay_engine.update_reliability(0.3, success=False)
        assert result == pytest.approx(0.285, abs=0.001)

    def test_success_at_min_reliability(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: success at minimum reliability floor.

        R_new = 0.95 * 0.1 + 0.05 * 1.0 = 0.095 + 0.05 = 0.145
        """
        result = decay_engine.update_reliability(0.1, success=True)
        assert result == pytest.approx(0.145, abs=0.001)

    def test_failure_below_min_clamped(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: failure result clamped to min_reliability.

        R_new = 0.95 * 0.1 + 0.05 * 0.0 = 0.095 → clamped to 0.1
        """
        result = decay_engine.update_reliability(0.1, success=False)
        assert result == pytest.approx(0.1, abs=0.001)

    def test_success_exact_one(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA: success at reliability 1.0 stays at 1.0.

        R_new = 0.95 * 1.0 + 0.05 * 1.0 = 1.0
        """
        result = decay_engine.update_reliability(1.0, success=True)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_max_reliability_cap(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test reliability capped at max_reliability (1.0)."""
        # Even if somehow > 1.0, it should be capped
        result = decay_engine.update_reliability(1.0, success=True)
        assert result <= 1.0

    def test_ewma_decay_sequence(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA decay over multiple consecutive failures.

        Starting at 1.0, each failure should decrease reliability.
        """
        current = 1.0
        for _ in range(10):
            current = decay_engine.update_reliability(current, success=False)

        # After 10 consecutive failures: should be well below 1.0
        assert current < 0.7
        # But not below min_reliability (0.1)
        assert current >= 0.1

    def test_ewma_recovery_sequence(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test EWMA recovery after failures.

        After failures reduce reliability, successes should increase it.
        """
        current = 1.0
        # 5 failures
        for _ in range(5):
            current = decay_engine.update_reliability(current, success=False)
        low = current

        # 10 successes
        for _ in range(10):
            current = decay_engine.update_reliability(current, success=True)

        assert current > low
        assert current < 1.0  # Takes time to fully recover


class TestEWMACustomConfig:
    """EWMA tests with custom decay factor."""

    def test_custom_decay_factor_success(
        self,
        decay_engine_custom: ReliabilityDecayEngine,
    ) -> None:
        """Test EWMA with alpha=0.9.

        R_new = 0.9 * 0.8 + 0.1 * 1.0 = 0.72 + 0.1 = 0.82
        """
        result = decay_engine_custom.update_reliability(0.8, success=True)
        assert result == pytest.approx(0.82, abs=0.001)

    def test_custom_decay_factor_failure(
        self,
        decay_engine_custom: ReliabilityDecayEngine,
    ) -> None:
        """Test EWMA with alpha=0.9, failure.

        R_new = 0.9 * 0.8 + 0.1 * 0.0 = 0.72
        """
        result = decay_engine_custom.update_reliability(0.8, success=False)
        assert result == pytest.approx(0.72, abs=0.001)

    def test_custom_min_reliability(
        self,
        decay_engine_custom: ReliabilityDecayEngine,
    ) -> None:
        """Test custom min_reliability (0.2) as floor."""
        # 0.9 * 0.2 + 0.1 * 0 = 0.18 → clamped to 0.2
        result = decay_engine_custom.update_reliability(0.2, success=False)
        assert result == pytest.approx(0.2, abs=0.001)


# ============================================================================
# Async Graph Store Integration Tests
# ============================================================================


class TestDecayWithGraphStore:
    """ReliabilityDecayEngine async integration with mock graph store."""

    @pytest.mark.asyncio
    async def test_update_skill_reliability_success(
        self,
        decay_engine_with_store: ReliabilityDecayEngine,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test updating skill reliability on success."""
        # Current reliability from mock: 0.8
        # R_new = 0.95 * 0.8 + 0.05 * 1.0 = 0.76 + 0.05 = 0.81
        new_rel = await decay_engine_with_store.update_skill_reliability(
            "skill:test", success=True,
        )
        assert new_rel == pytest.approx(0.81, abs=0.001)
        mock_graph_store.update_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_skill_reliability_failure(
        self,
        decay_engine_with_store: ReliabilityDecayEngine,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test updating skill reliability on failure."""
        # Current: 0.8, R_new = 0.95 * 0.8 + 0.05 * 0 = 0.76
        new_rel = await decay_engine_with_store.update_skill_reliability(
            "skill:test", success=False,
        )
        assert new_rel == pytest.approx(0.76, abs=0.001)

    @pytest.mark.asyncio
    async def test_get_current_reliability_default(
        self,
        decay_engine_with_store: ReliabilityDecayEngine,
    ) -> None:
        """Test fetching current reliability returns 1.0 for unknown."""
        # Mock returns 0.8 for known skill
        current = await decay_engine_with_store._get_current_reliability("skill:test")
        assert current == 0.8

    @pytest.mark.asyncio
    async def test_get_current_reliability_no_store(self) -> None:
        """Test default reliability when no graph store configured."""
        engine = ReliabilityDecayEngine()
        current = await engine._get_current_reliability("skill:unknown")
        assert current == 1.0

    @pytest.mark.asyncio
    async def test_deprecation_check(
        self,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test deprecation when reliability falls below threshold."""
        # Configure low reliability in mock
        mock_graph_store.get_node.return_value = {
            "uid": "skill:dep",
            "execution_success_rate": 0.15,  # Below deprecation threshold (0.3)
            "execution_count": 50,
            "is_deprecated": False,
        }

        config = DecayConfig(deprecation_threshold=0.3)
        engine = ReliabilityDecayEngine(graph_store=mock_graph_store, config=config)

        # Update with failure → reliability drops below threshold
        new_rel = await engine.update_skill_reliability("skill:dep", success=False)
        assert new_rel < config.deprecation_threshold
        # Should have called update_node for deprecation
        assert mock_graph_store.update_node.call_count >= 2  # reliability + deprecation


class TestDecayNoGraphStore:
    """ReliabilityDecayEngine without graph store (pure computation mode)."""

    @pytest.mark.asyncio
    async def test_update_skill_reliability_no_store(self) -> None:
        """Test update_skill_reliability without graph store returns pure EWMA."""
        engine = ReliabilityDecayEngine()
        new_rel = await engine.update_skill_reliability("skill:nostore", success=True)
        # Default current = 1.0, R_new = 0.95 * 1.0 + 0.05 * 1.0 = 1.0
        assert new_rel == pytest.approx(1.0, abs=0.001)


# ============================================================================
# Batch Computation Tests
# ============================================================================


class TestBatchReliability:
    """Batch reliability computation tests."""

    def test_batch_update_success(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test batch reliability update for multiple skills."""
        current_values = {
            "skill:a": 0.9,
            "skill:b": 0.8,
            "skill:c": 0.7,
        }
        results = {
            "skill:a": True,
            "skill:b": False,
            "skill:c": True,
        }
        updated = decay_engine.compute_batch_reliability(current_values, results)

        # skill:a: 0.95 * 0.9 + 0.05 * 1 = 0.905
        assert updated["skill:a"] == pytest.approx(0.905, abs=0.001)
        # skill:b: 0.95 * 0.8 + 0.05 * 0 = 0.76
        assert updated["skill:b"] == pytest.approx(0.76, abs=0.001)
        # skill:c: 0.95 * 0.7 + 0.05 * 1 = 0.665 + 0.05 = 0.715
        assert updated["skill:c"] == pytest.approx(0.715, abs=0.001)

    def test_batch_update_missing_result_default_true(
        self,
        decay_engine: ReliabilityDecayEngine,
    ) -> None:
        """Test batch with missing skill in results defaults to success."""
        current_values = {"skill:x": 0.5}
        results = {}  # No result for skill:x → defaults True
        updated = decay_engine.compute_batch_reliability(current_values, results)
        # 0.95 * 0.5 + 0.05 * 1 = 0.475 + 0.05 = 0.525
        assert updated["skill:x"] == pytest.approx(0.525, abs=0.001)

    def test_batch_update_empty(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test batch with empty inputs."""
        updated = decay_engine.compute_batch_reliability({}, {})
        assert updated == {}

    def test_batch_update_all_failures(self, decay_engine: ReliabilityDecayEngine) -> None:
        """Test batch with all failures."""
        current_values = {"skill:a": 1.0, "skill:b": 0.9}
        results = {"skill:a": False, "skill:b": False}
        updated = decay_engine.compute_batch_reliability(current_values, results)
        assert updated["skill:a"] < 1.0
        assert updated["skill:b"] < 0.9
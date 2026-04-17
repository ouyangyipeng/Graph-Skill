"""
EWMA reliability decay engine per RFC-05 Section 5.

Implements the exponential weighted moving average (EWMA) algorithm
for node reliability decay, deprecation checking, and recovery.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from graphskill.telemetry.models import DecayConfig

logger = logging.getLogger(__name__)


# ============================================================================
# Reliability Decay Engine (RFC-05 Section 5.3)
# ============================================================================


class ReliabilityDecayEngine:
    """Node reliability decay engine using EWMA algorithm.

    Per RFC-05 Section 5.2: R_new = α * R_current + (1 - α) * S_latest

    Where:
    - R_new: updated reliability
    - R_current: current reliability
    - S_latest: latest execution result (1=success, 0=failure)
    - α: decay factor (default 0.95)

    Features:
    - EWMA decay with configurable alpha
    - Lower bound constraint (min_reliability)
    - Deprecation threshold for auto-soft-delete
    - Recovery mechanism for deprecated skills
    """

    def __init__(
        self,
        graph_store: Optional[Any] = None,
        config: Optional[DecayConfig] = None,
    ) -> None:
        self._graph_store = graph_store
        self._config = config or DecayConfig()
        self._alpha = self._config.decay_factor
        self._min_reliability = self._config.min_reliability
        self._max_reliability = self._config.max_reliability
        self._deprecation_threshold = self._config.deprecation_threshold

    def update_reliability(
        self,
        current_reliability: float,
        success: bool,
    ) -> float:
        """Update reliability using EWMA formula (pure computation).

        Per RFC-05 Section 5.2:
        R_new = α * R_current + (1 - α) * S_latest

        Args:
            current_reliability: Current reliability value (0-1).
            success: Whether the latest execution succeeded.

        Returns:
            float: Updated reliability value, clamped to [min, max].
        """
        latest_result = 1.0 if success else 0.0
        new_reliability = self._alpha * current_reliability + (1 - self._alpha) * latest_result

        # Apply bounds
        new_reliability = max(new_reliability, self._min_reliability)
        new_reliability = min(new_reliability, self._max_reliability)

        return new_reliability

    async def update_skill_reliability(
        self,
        skill_id: str,
        success: bool,
    ) -> float:
        """Update a skill node's reliability in the graph database.

        Full pipeline: fetch current → compute EWMA → update node →
        check deprecation.

        Args:
            skill_id: Skill node UID.
            success: Whether the latest execution succeeded.

        Returns:
            float: Updated reliability value.
        """
        current = await self._get_current_reliability(skill_id)
        new_reliability = self.update_reliability(current, success)

        await self._update_node_reliability(skill_id, new_reliability)

        # Check deprecation
        if new_reliability < self._deprecation_threshold:
            await self._check_deprecation(skill_id, new_reliability)

        # Check recovery
        if self._config.recovery_enabled and success:
            await self._check_recovery(skill_id, new_reliability)

        return new_reliability

    async def _get_current_reliability(self, skill_id: str) -> float:
        """Fetch current reliability from graph store.

        Returns 1.0 for unknown skills (optimistic default per RFC-05).
        """
        if self._graph_store is None:
            return 1.0

        try:
            result = await self._graph_store.get_node(skill_id)
            if result and isinstance(result, dict):
                return float(result.get("execution_success_rate", 1.0))
            return 1.0
        except Exception as e:
            logger.warning("Failed to fetch reliability for %s: %s", skill_id, e)
            return 1.0

    async def _update_node_reliability(
        self,
        skill_id: str,
        new_reliability: float,
    ) -> None:
        """Update the skill node's reliability in the graph database."""
        if self._graph_store is None:
            return

        try:
            await self._graph_store.update_node(
                skill_id,
                {"execution_success_rate": new_reliability},
            )
        except Exception as e:
            logger.error("Failed to update reliability for %s: %s", skill_id, e)

    async def _check_deprecation(
        self,
        skill_id: str,
        reliability: float,
    ) -> None:
        """Check if skill should be deprecated (soft-deleted).

        Per RFC-05 Section 5.3: skills with reliability below
        deprecation_threshold AND consecutive failures exceeding
        threshold SHOULD be deprecated.
        """
        if self._graph_store is None:
            return

        try:
            node = await self._graph_store.get_node(skill_id)
            if not node:
                return

            # Simple heuristic: if execution_count > threshold * 2 and
            # reliability < threshold, mark as deprecated
            execution_count = 0
            if isinstance(node, dict):
                execution_count = int(node.get("execution_count", 0))

            # For now, use a simplified check until metrics_db is integrated
            if reliability < self._deprecation_threshold:
                logger.warning(
                    "Skill %s reliability %.2f below deprecation threshold %.2f",
                    skill_id,
                    reliability,
                    self._deprecation_threshold,
                )
                await self._deprecate_skill(skill_id, reliability)

        except Exception as e:
            logger.error("Deprecation check failed for %s: %s", skill_id, e)

    async def _deprecate_skill(
        self,
        skill_id: str,
        reliability: float,
    ) -> None:
        """Soft-delete (deprecate) a skill node.

        Per RFC-05 Section 5.3: set is_deprecated=true,
        deprecation_reason="low_reliability".
        """
        if self._graph_store is None:
            return

        try:
            await self._graph_store.update_node(
                skill_id,
                {
                    "is_deprecated": True,
                    "deprecation_reason": "low_reliability",
                    "deprecation_reliability": reliability,
                },
            )
            logger.info("Skill %s deprecated (reliability=%.2f)", skill_id, reliability)
        except Exception as e:
            logger.error("Failed to deprecate skill %s: %s", skill_id, e)

    async def _check_recovery(
        self,
        skill_id: str,
        new_reliability: float,
    ) -> None:
        """Check if a deprecated skill has recovered enough to be un-deprecated.

        Per RFC-05 Section 5.4: if recovery is enabled and reliability
        exceeds full_recovery_threshold, cancel the deprecation flag.
        """
        if not self._config.recovery_enabled:
            return

        if self._graph_store is None:
            return

        try:
            node = await self._graph_store.get_node(skill_id)
            if not node or not isinstance(node, dict):
                return

            is_deprecated = node.get("is_deprecated", False)
            if is_deprecated and new_reliability >= self._config.full_recovery_threshold:
                await self._undeprecate_skill(skill_id, new_reliability)
        except Exception as e:
            logger.error("Recovery check failed for %s: %s", skill_id, e)

    async def _undeprecate_skill(
        self,
        skill_id: str,
        reliability: float,
    ) -> None:
        """Cancel deprecation flag on a recovered skill node."""
        if self._graph_store is None:
            return

        try:
            await self._graph_store.update_node(
                skill_id,
                {
                    "is_deprecated": False,
                    "deprecation_reason": "",
                    "recovery_reliability": reliability,
                },
            )
            logger.info("Skill %s recovered (reliability=%.2f)", skill_id, reliability)
        except Exception as e:
            logger.error("Failed to undeprecate skill %s: %s", skill_id, e)

    def compute_batch_reliability(
        self,
        current_values: dict[str, float],
        results: dict[str, bool],
    ) -> dict[str, float]:
        """Batch-compute EWMA reliability updates (pure computation).

        Args:
            current_values: Map of skill_id → current reliability.
            results: Map of skill_id → latest execution success.

        Returns:
            dict: Map of skill_id → updated reliability.
        """
        updated: dict[str, float] = {}
        for skill_id, current in current_values.items():
            success = results.get(skill_id, True)
            updated[skill_id] = self.update_reliability(current, success)
        return updated
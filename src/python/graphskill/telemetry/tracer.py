"""
Tracer implementations per RFC-05 Section 3.

Provides TracerInterface, BaseTracer with buffering/flush logic,
ExecutionTracer for skill execution events, and RoutingTracer
for routing decision events.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from graphskill.telemetry.models import (
    EventCode,
    EventType,
    TelemetryRecord,
    TracerConfig,
    TraceContext,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Tracer Interface (RFC-05 Section 3.2)
# ============================================================================


class TracerInterface:
    """Abstract tracer interface per RFC-05 Section 3.2.

    All concrete tracers MUST implement trace_event() and flush().
    """

    def trace_event(
        self,
        event_type: EventType,
        event_data: dict[str, Any],
        context: TraceContext,
    ) -> None:
        """Record a telemetry event.

        Args:
            event_type: Type of the event.
            event_data: Event payload data.
            context: Trace context with request-level metadata.
        """
        raise NotImplementedError

    def flush(self) -> None:
        """Flush buffered events to the transport layer."""
        raise NotImplementedError


# ============================================================================
# Base Tracer (buffer + flush + sampling)
# ============================================================================


class BaseTracer(TracerInterface):
    """Base tracer with buffering, sampling, and sensitive data filtering.

    Per RFC-05 Section 3.3: buffers events until buffer_size is reached
    or flush() is called explicitly. Applies sampling rates and
    sensitive field filtering before adding to buffer.
    """

    def __init__(
        self,
        producer: Optional[Any] = None,
        config: Optional[TracerConfig] = None,
    ) -> None:
        self._producer = producer
        self._config = config or TracerConfig()
        self._buffer: list[TelemetryRecord] = []

    def trace_event(
        self,
        event_type: EventType,
        event_data: dict[str, Any],
        context: TraceContext,
    ) -> None:
        """Record a telemetry event with sampling and filtering.

        Per RFC-05 Section 3.5: events are subject to sampling rates
        and sensitive data filtering before being buffered.
        """
        # Apply sampling
        if not self._config.should_sample(event_type):
            return

        # Filter sensitive data
        filtered_data = self._config.filter_sensitive_data(event_data)

        record = TelemetryRecord(
            event_type=event_type,
            trace_id=context.trace_id,
            timestamp=context.timestamp,
            session_id=context.session_id,
            skill_id=filtered_data.get("skill_id", ""),
            agent_id=context.agent_id,
            data=filtered_data,
            metadata={
                "span_id": context.span_id,
                "parent_span_id": context.parent_span_id,
            },
        )

        self._add_to_buffer(record)

    def _add_to_buffer(self, record: TelemetryRecord) -> None:
        """Add a record to the buffer and auto-flush when full.

        Per RFC-05 Section 3.3: flush when buffer reaches buffer_size.
        """
        self._buffer.append(record)

        if len(self._buffer) >= self._config.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered events to the Kafka producer.

        Per RFC-05 Section 3.3: batch-send all buffered records,
        then clear the buffer.
        """
        if not self._buffer:
            return

        if self._producer is None:
            # No producer configured; log and discard (mock mode)
            logger.debug(
                "No producer configured, discarding %d buffered events",
                len(self._buffer),
            )
            self._buffer.clear()
            return

        for record in self._buffer:
            try:
                self._producer.send(
                    topic=self._config.kafka_topic,
                    key=record.trace_id,
                    value=record.to_json(),
                )
            except Exception as e:
                logger.error("Failed to send telemetry record: %s", e)

        self._buffer.clear()

    @property
    def buffer_size(self) -> int:
        """Return current number of buffered events."""
        return len(self._buffer)

    @property
    def config(self) -> TracerConfig:
        """Return tracer configuration."""
        return self._config


# ============================================================================
# Execution Tracer (RFC-05 Section 3.3)
# ============================================================================


class ExecutionTracer(BaseTracer):
    """Skill execution tracer per RFC-05 Section 3.3.

    Records SKILL_CALLED, SKILL_SUCCESS, and SKILL_FAILED events.
    """

    def trace_skill_call(
        self,
        skill_id: str,
        session_id: str,
        parameters: dict[str, Any],
        context: TraceContext,
    ) -> None:
        """Record skill call start (E001).

        Args:
            skill_id: The skill being called.
            session_id: Session identifier.
            parameters: Call parameters (sensitive fields will be filtered).
            context: Trace context.
        """
        self.trace_event(
            EventType.SKILL_CALLED,
            {
                "skill_id": skill_id,
                "parameters": parameters,
                "span_id": context.span_id,
            },
            context,
        )

    def trace_skill_success(
        self,
        skill_id: str,
        session_id: str,
        duration_ms: float,
        result: dict[str, Any],
        context: TraceContext,
    ) -> None:
        """Record skill execution success (E002).

        Args:
            skill_id: The skill that succeeded.
            session_id: Session identifier.
            duration_ms: Execution duration in milliseconds.
            result: Execution result (will be summarized).
            context: Trace context.
        """
        self.trace_event(
            EventType.SKILL_SUCCESS,
            {
                "skill_id": skill_id,
                "duration_ms": duration_ms,
                "result_summary": self._summarize_result(result),
                "span_id": context.span_id,
            },
            context,
        )

    def trace_skill_failure(
        self,
        skill_id: str,
        session_id: str,
        error_type: str,
        error_message: str,
        context: TraceContext,
    ) -> None:
        """Record skill execution failure (E003).

        Args:
            skill_id: The skill that failed.
            session_id: Session identifier.
            error_type: Error classification.
            error_message: Error description.
            context: Trace context.
        """
        self.trace_event(
            EventType.SKILL_FAILED,
            {
                "skill_id": skill_id,
                "error_type": error_type,
                "error_message": error_message,
                "span_id": context.span_id,
            },
            context,
        )

    @staticmethod
    def _summarize_result(result: dict[str, Any]) -> str:
        """Summarize execution result, avoiding sensitive data.

        Per RFC-05 Section 3.3: only record result type, not content.
        """
        if result.get("success"):
            return "success"
        if result.get("error"):
            return f"error: {result['error'].get('type', 'unknown')}"
        return "unknown"


# ============================================================================
# Routing Tracer (RFC-05 Section 3.4)
# ============================================================================


class RoutingTracer(BaseTracer):
    """Routing decision tracer per RFC-05 Section 3.4.

    Records ROUTING_STARTED, ROUTING_COMPLETED, and ROUTING_FALLBACK events.
    """

    def trace_routing_start(
        self,
        query: str,
        query_hash: str,
        session_id: str,
        max_tokens: int,
        context: TraceContext,
    ) -> None:
        """Record routing request start (E004).

        Args:
            query: The routing query (only length is recorded).
            query_hash: Hash of the query for privacy.
            session_id: Session identifier.
            max_tokens: Token budget for the request.
            context: Trace context.
        """
        self.trace_event(
            EventType.ROUTING_STARTED,
            {
                "query_hash": query_hash,
                "query_length": len(query),
                "max_tokens": max_tokens,
                "span_id": context.span_id,
            },
            context,
        )

    def trace_routing_complete(
        self,
        query_hash: str,
        session_id: str,
        skill_ids: list[str],
        latency_ms: float,
        routing_mode: str,
        context: TraceContext,
    ) -> None:
        """Record routing request completion (E005).

        Args:
            query_hash: Hash of the original query.
            session_id: Session identifier.
            skill_ids: List of selected skill IDs.
            latency_ms: Routing latency in milliseconds.
            routing_mode: Routing mode (normal/fallback).
            context: Trace context.
        """
        self.trace_event(
            EventType.ROUTING_COMPLETED,
            {
                "query_hash": query_hash,
                "skill_count": len(skill_ids),
                "skill_ids": skill_ids,
                "latency_ms": latency_ms,
                "routing_mode": routing_mode,
                "span_id": context.span_id,
            },
            context,
        )

    def trace_routing_fallback(
        self,
        query_hash: str,
        session_id: str,
        fallback_reason: str,
        context: TraceContext,
    ) -> None:
        """Record routing fallback/degradation (E006).

        Args:
            query_hash: Hash of the original query.
            session_id: Session identifier.
            fallback_reason: Why fallback mode was activated.
            context: Trace context.
        """
        self.trace_event(
            EventType.ROUTING_FALLBACK,
            {
                "query_hash": query_hash,
                "fallback_reason": fallback_reason,
                "span_id": context.span_id,
            },
            context,
        )
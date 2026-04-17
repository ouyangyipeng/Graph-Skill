"""
Tracer unit tests per RFC-05.

Tests TracerInterface, BaseTracer buffering/flush/sampling,
ExecutionTracer skill call/success/failure, and
RoutingTracer routing start/complete/fallback.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from graphskill.telemetry.models import (
    EventCode,
    EventType,
    TelemetryRecord,
    TracerConfig,
    TraceContext,
)
from graphskill.telemetry.tracer import (
    BaseTracer,
    ExecutionTracer,
    RoutingTracer,
    TracerInterface,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def trace_context() -> TraceContext:
    """Create a trace context."""
    return TraceContext(
        trace_id="trace_test",
        session_id="sess_test",
        agent_id="agent_test",
        span_id="span_test",
        parent_span_id=None,
    )


@pytest.fixture
def mock_producer() -> MagicMock:
    """Create a mock Kafka producer."""
    producer = MagicMock()
    producer.send = MagicMock()
    return producer


@pytest.fixture
def tracer_config() -> TracerConfig:
    """Create tracer config with sampling disabled for deterministic tests."""
    return TracerConfig(
        buffer_size=5,
        flush_interval_ms=1000,
        sampling_default_rate=1.0,
        sampling_success_rate=1.0,
        sampling_failure_rate=1.0,
        sampling_fallback_rate=1.0,
    )


@pytest.fixture
def base_tracer(mock_producer: MagicMock, tracer_config: TracerConfig) -> BaseTracer:
    """Create a base tracer with mock producer."""
    return BaseTracer(producer=mock_producer, config=tracer_config)


@pytest.fixture
def execution_tracer(mock_producer: MagicMock, tracer_config: TracerConfig) -> ExecutionTracer:
    """Create an execution tracer with mock producer."""
    return ExecutionTracer(producer=mock_producer, config=tracer_config)


@pytest.fixture
def routing_tracer(mock_producer: MagicMock, tracer_config: TracerConfig) -> RoutingTracer:
    """Create a routing tracer with mock producer."""
    return RoutingTracer(producer=mock_producer, config=tracer_config)


# ============================================================================
# TracerInterface Tests
# ============================================================================


class TestTracerInterface:
    """TracerInterface abstract class tests."""

    def test_interface_raises_not_implemented(self) -> None:
        """Test calling trace_event on interface raises NotImplementedError."""
        interface = TracerInterface()
        with pytest.raises(NotImplementedError):
            interface.trace_event(EventType.SKILL_CALLED, {}, TraceContext())

    def test_interface_flush_raises_not_implemented(self) -> None:
        """Test calling flush on interface raises NotImplementedError."""
        interface = TracerInterface()
        with pytest.raises(NotImplementedError):
            interface.flush()


# ============================================================================
# BaseTracer Tests
# ============================================================================


class TestBaseTracer:
    """BaseTracer buffering, flush, and sampling tests."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        tracer = BaseTracer()
        assert tracer._producer is None
        assert tracer._config.buffer_size == 100
        assert tracer.buffer_size == 0

    def test_init_with_producer_and_config(
        self,
        mock_producer: MagicMock,
        tracer_config: TracerConfig,
    ) -> None:
        """Test initialization with producer and config."""
        tracer = BaseTracer(producer=mock_producer, config=tracer_config)
        assert tracer._producer == mock_producer
        assert tracer._config.buffer_size == 5

    def test_trace_event_adds_to_buffer(
        self,
        base_tracer: BaseTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test trace_event adds a record to the buffer."""
        base_tracer.trace_event(
            EventType.SKILL_CALLED,
            {"skill_id": "git:commit"},
            trace_context,
        )
        assert base_tracer.buffer_size == 1

    def test_auto_flush_on_buffer_full(
        self,
        base_tracer: BaseTracer,
        trace_context: TraceContext,
        mock_producer: MagicMock,
    ) -> None:
        """Test auto-flush when buffer reaches buffer_size."""
        for i in range(5):  # buffer_size = 5
            base_tracer.trace_event(
                EventType.SKILL_CALLED,
                {"skill_id": f"skill:{i}"},
                trace_context,
            )

        # Buffer should be flushed after reaching capacity
        assert base_tracer.buffer_size == 0
        assert mock_producer.send.call_count == 5

    def test_manual_flush(
        self,
        base_tracer: BaseTracer,
        trace_context: TraceContext,
        mock_producer: MagicMock,
    ) -> None:
        """Test explicit flush() sends buffered events."""
        base_tracer.trace_event(
            EventType.SKILL_CALLED,
            {"skill_id": "git:commit"},
            trace_context,
        )
        assert base_tracer.buffer_size == 1

        base_tracer.flush()
        assert base_tracer.buffer_size == 0
        assert mock_producer.send.call_count == 1

    def test_flush_empty_buffer(self) -> None:
        """Test flush on empty buffer does nothing."""
        tracer = BaseTracer(producer=MagicMock())
        tracer.flush()  # No events, no error
        assert tracer.buffer_size == 0

    def test_flush_without_producer(
        self,
        trace_context: TraceContext,
    ) -> None:
        """Test flush without producer discards events."""
        config = TracerConfig(buffer_size=5, sampling_default_rate=1.0)
        tracer_no_prod = BaseTracer(config=config)
        tracer_no_prod.trace_event(
            EventType.SKILL_CALLED,
            {"skill_id": "test"},
            trace_context,
        )
        tracer_no_prod.flush()
        assert tracer_no_prod.buffer_size == 0

    def test_sensitive_data_filtering(
        self,
        base_tracer: BaseTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test sensitive data filtering during trace_event."""
        base_tracer.trace_event(
            EventType.SKILL_CALLED,
            {"skill_id": "git:commit", "api_key": "sk-secret"},
            trace_context,
        )
        # Buffer should have filtered data
        assert base_tracer.buffer_size == 1
        record = base_tracer._buffer[0]
        assert record.data["api_key"] == "[FILTERED]"

    def test_config_accessible(
        self,
        base_tracer: BaseTracer,
        tracer_config: TracerConfig,
    ) -> None:
        """Test config property."""
        assert base_tracer.config.buffer_size == tracer_config.buffer_size


# ============================================================================
# ExecutionTracer Tests
# ============================================================================


class TestExecutionTracer:
    """ExecutionTracer skill call/success/failure tests."""

    def test_trace_skill_call(
        self,
        execution_tracer: ExecutionTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing a skill call (E001)."""
        execution_tracer.trace_skill_call(
            skill_id="git:commit",
            session_id="sess_001",
            parameters={"repo": "myproject"},
            context=trace_context,
        )
        assert execution_tracer.buffer_size == 1
        record = execution_tracer._buffer[0]
        assert record.event_type == EventType.SKILL_CALLED
        assert record.event_code == EventCode.SKILL_CALLED
        assert record.skill_id == "git:commit"

    def test_trace_skill_success(
        self,
        execution_tracer: ExecutionTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing a skill success (E002)."""
        execution_tracer.trace_skill_success(
            skill_id="git:commit",
            session_id="sess_001",
            duration_ms=1500.0,
            result={"success": True},
            context=trace_context,
        )
        assert execution_tracer.buffer_size == 1
        record = execution_tracer._buffer[0]
        assert record.event_type == EventType.SKILL_SUCCESS
        assert record.data["duration_ms"] == 1500.0
        assert record.data["result_summary"] == "success"

    def test_trace_skill_failure(
        self,
        execution_tracer: ExecutionTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing a skill failure (E003)."""
        execution_tracer.trace_skill_failure(
            skill_id="git:commit",
            session_id="sess_001",
            error_type="timeout",
            error_message="Operation timed out after 30s",
            context=trace_context,
        )
        assert execution_tracer.buffer_size == 1
        record = execution_tracer._buffer[0]
        assert record.event_type == EventType.SKILL_FAILED
        assert record.data["error_type"] == "timeout"

    def test_summarize_result_success(self) -> None:
        """Test result summary for success."""
        result = ExecutionTracer._summarize_result({"success": True})
        assert result == "success"

    def test_summarize_result_error(self) -> None:
        """Test result summary for error."""
        result = ExecutionTracer._summarize_result(
            {"error": {"type": "timeout"}}
        )
        assert result == "error: timeout"

    def test_summarize_result_unknown(self) -> None:
        """Test result summary for unknown result."""
        result = ExecutionTracer._summarize_result({})
        assert result == "unknown"

    def test_full_execution_workflow(
        self,
        execution_tracer: ExecutionTracer,
        trace_context: TraceContext,
        mock_producer: MagicMock,
    ) -> None:
        """Test complete execution trace: call → success."""
        execution_tracer.trace_skill_call(
            "git:commit", "sess_001", {"repo": "test"}, trace_context,
        )
        execution_tracer.trace_skill_success(
            "git:commit", "sess_001", 1200.0, {"success": True}, trace_context,
        )
        assert execution_tracer.buffer_size == 2
        execution_tracer.flush()
        assert mock_producer.send.call_count == 2


# ============================================================================
# RoutingTracer Tests
# ============================================================================


class TestRoutingTracer:
    """RoutingTracer routing start/complete/fallback tests."""

    def test_trace_routing_start(
        self,
        routing_tracer: RoutingTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing routing start (E004)."""
        routing_tracer.trace_routing_start(
            query="commit changes to git",
            query_hash="hash_abc",
            session_id="sess_001",
            max_tokens=8000,
            context=trace_context,
        )
        assert routing_tracer.buffer_size == 1
        record = routing_tracer._buffer[0]
        assert record.event_type == EventType.ROUTING_STARTED
        assert record.data["query_hash"] == "hash_abc"
        assert record.data["query_length"] == len("commit changes to git")
        assert record.data["max_tokens"] == 8000

    def test_trace_routing_complete(
        self,
        routing_tracer: RoutingTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing routing completion (E005)."""
        routing_tracer.trace_routing_complete(
            query_hash="hash_abc",
            session_id="sess_001",
            skill_ids=["git:commit", "git:push"],
            latency_ms=250.0,
            routing_mode="normal",
            context=trace_context,
        )
        assert routing_tracer.buffer_size == 1
        record = routing_tracer._buffer[0]
        assert record.event_type == EventType.ROUTING_COMPLETED
        assert record.data["skill_count"] == 2
        assert record.data["latency_ms"] == 250.0
        assert record.data["routing_mode"] == "normal"

    def test_trace_routing_fallback(
        self,
        routing_tracer: RoutingTracer,
        trace_context: TraceContext,
    ) -> None:
        """Test tracing routing fallback (E006)."""
        routing_tracer.trace_routing_fallback(
            query_hash="hash_abc",
            session_id="sess_001",
            fallback_reason="graph_db_down",
            context=trace_context,
        )
        assert routing_tracer.buffer_size == 1
        record = routing_tracer._buffer[0]
        assert record.event_type == EventType.ROUTING_FALLBACK
        assert record.data["fallback_reason"] == "graph_db_down"

    def test_full_routing_workflow(
        self,
        routing_tracer: RoutingTracer,
        trace_context: TraceContext,
        mock_producer: MagicMock,
    ) -> None:
        """Test complete routing trace: start → complete."""
        routing_tracer.trace_routing_start(
            "test query", "hash_xyz", "sess_002", 4000, trace_context,
        )
        routing_tracer.trace_routing_complete(
            "hash_xyz", "sess_002", ["skill:a"], 100.0, "normal", trace_context,
        )
        assert routing_tracer.buffer_size == 2
        routing_tracer.flush()
        assert mock_producer.send.call_count == 2
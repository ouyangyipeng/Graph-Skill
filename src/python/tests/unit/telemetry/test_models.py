"""
Telemetry data models unit tests per RFC-05.

Tests EventType, EventCode, TraceContext, TelemetryRecord,
TracerConfig, DecayConfig, and ImplicitEdge.
"""

from __future__ import annotations

import json
import pytest

from graphskill.telemetry.models import (
    DecayConfig,
    EventCode,
    EventType,
    ImplicitEdge,
    TelemetryRecord,
    TracerConfig,
    TraceContext,
)


# ============================================================================
# EventType Tests
# ============================================================================


class TestEventType:
    """EventType enum tests."""

    def test_all_event_types_defined(self) -> None:
        """Test all 10 event types per RFC-05 Section 3.1."""
        expected = [
            "SKILL_CALLED", "SKILL_SUCCESS", "SKILL_FAILED",
            "ROUTING_STARTED", "ROUTING_COMPLETED", "ROUTING_FALLBACK",
            "PERMISSION_CHECK", "PERMISSION_DENIED",
            "CONTEXT_OVERFLOW", "CONFLICT_DETECTED",
        ]
        for name in expected:
            assert hasattr(EventType, name)

    def test_event_type_count(self) -> None:
        """Test event type enum count matches RFC-05."""
        assert len(EventType) == 10

    def test_event_type_is_string_enum(self) -> None:
        """Test EventType values are strings."""
        assert isinstance(EventType.SKILL_CALLED, str)
        assert EventType.SKILL_CALLED.value == "SKILL_CALLED"


class TestEventCode:
    """EventCode enum tests."""

    def test_all_event_codes_defined(self) -> None:
        """Test all 10 event codes E001-E010 per RFC-05."""
        expected_codes = [
            ("SKILL_CALLED", "E001"),
            ("SKILL_SUCCESS", "E002"),
            ("SKILL_FAILED", "E003"),
            ("ROUTING_STARTED", "E004"),
            ("ROUTING_COMPLETED", "E005"),
            ("ROUTING_FALLBACK", "E006"),
            ("PERMISSION_CHECK", "E007"),
            ("PERMISSION_DENIED", "E008"),
            ("CONTEXT_OVERFLOW", "E009"),
            ("CONFLICT_DETECTED", "E010"),
        ]
        for name, value in expected_codes:
            assert hasattr(EventCode, name)
            assert EventCode[name].value == value

    def test_event_code_values(self) -> None:
        """Test event code values match RFC-05."""
        assert EventCode.SKILL_CALLED.value == "E001"
        assert EventCode.SKILL_SUCCESS.value == "E002"
        assert EventCode.SKILL_FAILED.value == "E003"
        assert EventCode.ROUTING_STARTED.value == "E004"
        assert EventCode.ROUTING_COMPLETED.value == "E005"
        assert EventCode.ROUTING_FALLBACK.value == "E006"

    def test_event_code_count(self) -> None:
        """Test event code enum count."""
        assert len(EventCode) == 10


# ============================================================================
# TraceContext Tests
# ============================================================================


class TestTraceContext:
    """TraceContext data structure tests."""

    def test_create_context_defaults(self) -> None:
        """Test auto-generated trace_id, timestamp, span_id."""
        ctx = TraceContext()
        assert ctx.trace_id != ""
        assert ctx.timestamp != ""
        assert ctx.span_id != ""
        assert ctx.parent_span_id is None

    def test_create_context_with_values(self) -> None:
        """Test context with explicit values."""
        ctx = TraceContext(
            trace_id="trace_123",
            session_id="sess_456",
            agent_id="agent_789",
            timestamp="2026-04-12T10:00:00Z",
            span_id="span_001",
            parent_span_id="span_root",
        )
        assert ctx.trace_id == "trace_123"
        assert ctx.session_id == "sess_456"
        assert ctx.agent_id == "agent_789"
        assert ctx.timestamp == "2026-04-12T10:00:00Z"
        assert ctx.span_id == "span_001"
        assert ctx.parent_span_id == "span_root"

    def test_context_to_dict(self) -> None:
        """Test serialization to dict."""
        ctx = TraceContext(
            trace_id="trace_123",
            session_id="sess_456",
            agent_id="agent_789",
            timestamp="2026-04-12T10:00:00Z",
            span_id="span_001",
            parent_span_id="span_root",
        )
        d = ctx.to_dict()
        assert d["trace_id"] == "trace_123"
        assert d["session_id"] == "sess_456"
        assert d["agent_id"] == "agent_789"
        assert d["parent_span_id"] == "span_root"

    def test_context_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "trace_id": "trace_abc",
            "session_id": "sess_def",
            "agent_id": "agent_ghi",
            "timestamp": "2026-04-12T10:00:00Z",
            "span_id": "span_002",
            "parent_span_id": None,
        }
        ctx = TraceContext.from_dict(data)
        assert ctx.trace_id == "trace_abc"
        assert ctx.session_id == "sess_def"
        assert ctx.parent_span_id is None

    def test_context_roundtrip(self) -> None:
        """Test dict roundtrip serialization."""
        ctx = TraceContext(
            trace_id="trace_rt",
            session_id="sess_rt",
            agent_id="agent_rt",
            span_id="span_rt",
            parent_span_id="parent_rt",
        )
        d = ctx.to_dict()
        ctx2 = TraceContext.from_dict(d)
        assert ctx2.trace_id == ctx.trace_id
        assert ctx2.session_id == ctx.session_id
        assert ctx2.parent_span_id == ctx.parent_span_id


# ============================================================================
# TelemetryRecord Tests
# ============================================================================


class TestTelemetryRecord:
    """TelemetryRecord data structure tests."""

    def test_create_record_defaults(self) -> None:
        """Test auto-generated fields."""
        record = TelemetryRecord()
        assert record.event_type == EventType.SKILL_CALLED
        assert record.event_code == EventCode.SKILL_CALLED
        assert record.trace_id != ""
        assert record.timestamp != ""
        assert record.data == {}
        assert record.metadata == {}

    def test_create_record_with_event_type(self) -> None:
        """Test record with explicit event type auto-derives code."""
        record = TelemetryRecord(event_type=EventType.SKILL_SUCCESS)
        assert record.event_type == EventType.SKILL_SUCCESS
        assert record.event_code == EventCode.SKILL_SUCCESS

    def test_create_record_with_all_fields(self) -> None:
        """Test record with all fields specified."""
        record = TelemetryRecord(
            event_type=EventType.SKILL_FAILED,
            event_code=EventCode.SKILL_FAILED,
            trace_id="trace_fail",
            timestamp="2026-04-12T10:00:00Z",
            session_id="sess_fail",
            skill_id="git:commit",
            agent_id="agent_001",
            data={"error_type": "timeout", "error_message": "Timed out"},
            metadata={"span_id": "span_003"},
        )
        assert record.event_type == EventType.SKILL_FAILED
        assert record.event_code == EventCode.SKILL_FAILED
        assert record.skill_id == "git:commit"
        assert record.data["error_type"] == "timeout"

    def test_record_to_dict(self) -> None:
        """Test serialization to dict."""
        record = TelemetryRecord(
            event_type=EventType.SKILL_SUCCESS,
            trace_id="trace_dict",
            skill_id="skill:test",
            data={"duration_ms": 1500.0},
        )
        d = record.to_dict()
        assert d["event_type"] == "SKILL_SUCCESS"
        assert d["event_code"] == "E002"
        assert d["trace_id"] == "trace_dict"
        assert d["skill_id"] == "skill:test"
        assert d["data"]["duration_ms"] == 1500.0

    def test_record_to_json(self) -> None:
        """Test JSON serialization."""
        record = TelemetryRecord(
            event_type=EventType.ROUTING_COMPLETED,
            trace_id="trace_json",
            data={"skill_count": 3},
        )
        json_str = record.to_json()
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "ROUTING_COMPLETED"
        assert parsed["trace_id"] == "trace_json"

    def test_record_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "event_type": "SKILL_CALLED",
            "event_code": "E001",
            "trace_id": "trace_from",
            "timestamp": "2026-04-12T10:00:00Z",
            "session_id": "sess_from",
            "skill_id": "skill:from",
            "agent_id": "agent_from",
            "data": {"key": "value"},
            "metadata": {"span_id": "span_from"},
        }
        record = TelemetryRecord.from_dict(data)
        assert record.event_type == EventType.SKILL_CALLED
        assert record.event_code == EventCode.SKILL_CALLED
        assert record.trace_id == "trace_from"
        assert record.skill_id == "skill:from"

    def test_record_from_json(self) -> None:
        """Test deserialization from JSON."""
        json_str = json.dumps({
            "event_type": "ROUTING_FALLBACK",
            "event_code": "E006",
            "trace_id": "trace_json_in",
            "data": {"fallback_reason": "graph_db_down"},
        })
        record = TelemetryRecord.from_json(json_str)
        assert record.event_type == EventType.ROUTING_FALLBACK
        assert record.event_code == EventCode.ROUTING_FALLBACK
        assert record.data["fallback_reason"] == "graph_db_down"

    def test_record_roundtrip(self) -> None:
        """Test JSON roundtrip serialization."""
        record = TelemetryRecord(
            event_type=EventType.CONFLICT_DETECTED,
            trace_id="trace_rt",
            skill_id="skill:conflict",
            data={"skill_ids": ["a", "b"], "conflict_type": "substitutes"},
        )
        json_str = record.to_json()
        record2 = TelemetryRecord.from_json(json_str)
        assert record2.event_type == record.event_type
        assert record2.trace_id == record.trace_id
        assert record2.skill_id == record.skill_id

    def test_record_auto_derive_code_from_type(self) -> None:
        """Test event_code auto-derived from event_type when mismatch."""
        # Create with mismatched code — should auto-correct
        record = TelemetryRecord(
            event_type=EventType.ROUTING_STARTED,
            event_code=EventCode.SKILL_CALLED,  # wrong code
        )
        # Post-init should have corrected it
        assert record.event_code == EventCode.ROUTING_STARTED


# ============================================================================
# TracerConfig Tests
# ============================================================================


class TestTracerConfig:
    """TracerConfig tests."""

    def test_default_config(self) -> None:
        """Test default configuration values per RFC-05 Section 3.5."""
        config = TracerConfig()
        assert config.buffer_size == 100
        assert config.flush_interval_ms == 1000
        assert config.sampling_default_rate == 1.0
        assert config.sampling_success_rate == 0.1
        assert config.sampling_failure_rate == 1.0
        assert config.sampling_fallback_rate == 1.0
        assert config.kafka_topic == "graphskill_telemetry"

    def test_sensitive_fields_default(self) -> None:
        """Test default sensitive fields per RFC-05."""
        config = TracerConfig()
        assert "password" in config.sensitive_fields
        assert "token" in config.sensitive_fields
        assert "secret" in config.sensitive_fields
        assert "api_key" in config.sensitive_fields
        assert "credential" in config.sensitive_fields

    def test_filter_sensitive_data(self) -> None:
        """Test sensitive data filtering."""
        config = TracerConfig()
        data = {
            "skill_id": "git:commit",
            "api_key": "sk-abc123",
            "parameters": {"token": "xyz", "query": "test"},
            "password": "secret123",
        }
        filtered = config.filter_sensitive_data(data)
        assert filtered["skill_id"] == "git:commit"
        assert filtered["api_key"] == "[FILTERED]"
        assert filtered["password"] == "[FILTERED]"
        assert filtered["parameters"]["token"] == "[FILTERED]"
        assert filtered["parameters"]["query"] == "test"

    def test_filter_sensitive_data_no_match(self) -> None:
        """Test filtering with no sensitive fields."""
        config = TracerConfig()
        data = {"skill_id": "test", "duration_ms": 100}
        filtered = config.filter_sensitive_data(data)
        assert filtered == data

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TracerConfig(
            buffer_size=50,
            flush_interval_ms=500,
            sampling_success_rate=0.5,
            kafka_topic="custom_topic",
        )
        assert config.buffer_size == 50
        assert config.flush_interval_ms == 500
        assert config.sampling_success_rate == 0.5
        assert config.kafka_topic == "custom_topic"


# ============================================================================
# DecayConfig Tests
# ============================================================================


class TestDecayConfig:
    """DecayConfig tests per RFC-05 Section 5.4."""

    def test_default_decay_config(self) -> None:
        """Test default EWMA decay configuration."""
        config = DecayConfig()
        assert config.decay_factor == 0.95
        assert config.min_reliability == 0.1
        assert config.max_reliability == 1.0
        assert config.deprecation_threshold == 0.3
        assert config.consecutive_failure_threshold == 5
        assert config.recovery_enabled is True
        assert config.recovery_rate == 0.05
        assert config.full_recovery_threshold == 0.8
        assert config.update_interval_seconds == 60

    def test_custom_decay_config(self) -> None:
        """Test custom decay configuration."""
        config = DecayConfig(
            decay_factor=0.99,
            min_reliability=0.2,
            deprecation_threshold=0.4,
        )
        assert config.decay_factor == 0.99
        assert config.min_reliability == 0.2
        assert config.deprecation_threshold == 0.4


# ============================================================================
# ImplicitEdge Tests
# ============================================================================


class TestImplicitEdge:
    """ImplicitEdge data structure tests."""

    def test_create_implicit_edge(self) -> None:
        """Test creating an implicit edge."""
        edge = ImplicitEdge(
            source="skill:a",
            target="skill:b",
            edge_type="REQUIRES",
            confidence=0.85,
            co_occurrence_count=100,
        )
        assert edge.source == "skill:a"
        assert edge.target == "skill:b"
        assert edge.edge_type == "REQUIRES"
        assert edge.confidence == 0.85
        assert edge.co_occurrence_count == 100

    def test_implicit_edge_defaults(self) -> None:
        """Test default values."""
        edge = ImplicitEdge()
        assert edge.source == ""
        assert edge.edge_type == "ENHANCES"
        assert edge.confidence == 0.0

    def test_implicit_edge_to_dict(self) -> None:
        """Test serialization."""
        edge = ImplicitEdge(
            source="skill:a",
            target="skill:b",
            confidence=0.9,
            co_occurrence_count=50,
        )
        d = edge.to_dict()
        assert d["source"] == "skill:a"
        assert d["confidence"] == 0.9
        assert d["co_occurrence_count"] == 50

    def test_implicit_edge_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "source": "skill:x",
            "target": "skill:y",
            "edge_type": "ENHANCES",
            "confidence": 0.7,
            "co_occurrence_count": 30,
        }
        edge = ImplicitEdge.from_dict(data)
        assert edge.source == "skill:x"
        assert edge.confidence == 0.7

    def test_implicit_edge_roundtrip(self) -> None:
        """Test dict roundtrip."""
        edge = ImplicitEdge(
            source="skill:p",
            target="skill:q",
            edge_type="REQUIRES",
            confidence=0.88,
            co_occurrence_count=75,
        )
        d = edge.to_dict()
        edge2 = ImplicitEdge.from_dict(d)
        assert edge2.source == edge.source
        assert edge2.confidence == edge.confidence
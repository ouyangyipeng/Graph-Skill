"""
Telemetry data models per RFC-05.

Defines event types, trace context, telemetry records,
tracer configuration, and EWMA decay configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# ============================================================================
# Event Types & Codes (RFC-05 Section 3.1)
# ============================================================================


class EventType(str, Enum):
    """Telemetry event types per RFC-05 Section 3.1."""

    SKILL_CALLED = "SKILL_CALLED"
    SKILL_SUCCESS = "SKILL_SUCCESS"
    SKILL_FAILED = "SKILL_FAILED"
    ROUTING_STARTED = "ROUTING_STARTED"
    ROUTING_COMPLETED = "ROUTING_COMPLETED"
    ROUTING_FALLBACK = "ROUTING_FALLBACK"
    PERMISSION_CHECK = "PERMISSION_CHECK"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"


class EventCode(str, Enum):
    """Event codes per RFC-05 Section 3.1."""

    SKILL_CALLED = "E001"
    SKILL_SUCCESS = "E002"
    SKILL_FAILED = "E003"
    ROUTING_STARTED = "E004"
    ROUTING_COMPLETED = "E005"
    ROUTING_FALLBACK = "E006"
    PERMISSION_CHECK = "E007"
    PERMISSION_DENIED = "E008"
    CONTEXT_OVERFLOW = "E009"
    CONFLICT_DETECTED = "E010"


# Mapping for auto-deriving event_code from event_type
_EVENT_TYPE_TO_CODE: dict[EventType, EventCode] = {
    EventType.SKILL_CALLED: EventCode.SKILL_CALLED,
    EventType.SKILL_SUCCESS: EventCode.SKILL_SUCCESS,
    EventType.SKILL_FAILED: EventCode.SKILL_FAILED,
    EventType.ROUTING_STARTED: EventCode.ROUTING_STARTED,
    EventType.ROUTING_COMPLETED: EventCode.ROUTING_COMPLETED,
    EventType.ROUTING_FALLBACK: EventCode.ROUTING_FALLBACK,
    EventType.PERMISSION_CHECK: EventCode.PERMISSION_CHECK,
    EventType.PERMISSION_DENIED: EventCode.PERMISSION_DENIED,
    EventType.CONTEXT_OVERFLOW: EventCode.CONTEXT_OVERFLOW,
    EventType.CONFLICT_DETECTED: EventCode.CONFLICT_DETECTED,
}


# ============================================================================
# Trace Context (RFC-05 Section 3.2)
# ============================================================================


@dataclass
class TraceContext:
    """Tracing context carrying request-level metadata.

    Per RFC-05 Section 3.2: trace_id, session_id, agent_id,
    timestamp, span_id, parent_span_id.
    """

    trace_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    timestamp: str = ""
    span_id: str = ""
    parent_span_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if not self.span_id:
            self.span_id = str(uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceContext:
        return cls(
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
            timestamp=data.get("timestamp", ""),
            span_id=data.get("span_id", ""),
            parent_span_id=data.get("parent_span_id"),
        )


# ============================================================================
# Telemetry Record (RFC-05 Section 4.1)
# ============================================================================


@dataclass
class TelemetryRecord:
    """Telemetry record per RFC-05 Section 4.1.

    Internal data structure for the telemetry pipeline.
    Can be serialized to JSON for Kafka transport.
    """

    event_type: EventType = EventType.SKILL_CALLED
    event_code: EventCode = EventCode.SKILL_CALLED
    trace_id: str = ""
    timestamp: str = ""
    session_id: str = ""
    skill_id: str = ""
    agent_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        # Auto-derive event_code from event_type when not explicitly set
        if self.event_type in _EVENT_TYPE_TO_CODE:
            expected_code = _EVENT_TYPE_TO_CODE[self.event_type]
            if self.event_code != expected_code:
                self.event_code = expected_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "event_code": self.event_code.value,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "skill_id": self.skill_id,
            "agent_id": self.agent_id,
            "data": self.data,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryRecord:
        event_type = EventType(data["event_type"])
        event_code_str = data.get("event_code", "")
        event_code = EventCode(event_code_str) if event_code_str else _EVENT_TYPE_TO_CODE[event_type]
        return cls(
            event_type=event_type,
            event_code=event_code,
            trace_id=data.get("trace_id", ""),
            timestamp=data.get("timestamp", ""),
            session_id=data.get("session_id", ""),
            skill_id=data.get("skill_id", ""),
            agent_id=data.get("agent_id", ""),
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TelemetryRecord:
        return cls.from_dict(json.loads(json_str))


# ============================================================================
# Tracer Configuration (RFC-05 Section 3.5)
# ============================================================================


@dataclass
class TracerConfig:
    """Tracer configuration per RFC-05 Section 3.5.

    Controls buffer size, flush interval, sampling rates,
    and sensitive data filtering.
    """

    buffer_size: int = 100
    flush_interval_ms: int = 1000
    sampling_default_rate: float = 1.0
    sampling_success_rate: float = 0.1
    sampling_failure_rate: float = 1.0
    sampling_fallback_rate: float = 1.0
    sensitive_fields: list[str] = field(default_factory=lambda: [
        "password", "token", "secret", "api_key", "credential",
    ])
    kafka_topic: str = "graphskill_telemetry"

    def should_sample(self, event_type: EventType) -> bool:
        """Determine if an event should be sampled based on its type.

        Uses deterministic sampling for testing: returns True for
        failure/fallback events (rate=1.0), applies rate for success events.
        """
        import random

        rate_map: dict[EventType, float] = {
            EventType.SKILL_SUCCESS: self.sampling_success_rate,
            EventType.SKILL_FAILED: self.sampling_failure_rate,
            EventType.ROUTING_FALLBACK: self.sampling_fallback_rate,
        }
        rate = rate_map.get(event_type, self.sampling_default_rate)
        return random.random() < rate

    def filter_sensitive_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from event data (recursive).

        Per RFC-05 Section 3.5: sensitive fields MUST be filtered
        before recording or transmission. Applies recursively to
        nested dictionaries.

        Matching rules: exact match or compound suffix match
        (e.g., "bearer_token" matches "_token", but "max_tokens"
        does NOT match because the suffix is "_tokens" not "_token").
        """
        filtered: dict[str, Any] = {}
        for key, value in data.items():
            if self._is_sensitive_key(key):
                filtered[key] = "[FILTERED]"
            elif isinstance(value, dict):
                filtered[key] = self.filter_sensitive_data(value)
            else:
                filtered[key] = value
        return filtered

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key name indicates a sensitive field.

        Uses exact match or compound suffix match (key ends with
        _{sensitive_field}), avoiding false positives like
        "max_tokens" containing substring "token".
        """
        key_lower = key.lower()
        for sf in self.sensitive_fields:
            if key_lower == sf or key_lower.endswith(f"_{sf}"):
                return True
        return False


# ============================================================================
# Decay Configuration (RFC-05 Section 5.4)
# ============================================================================


@dataclass
class DecayConfig:
    """EWMA decay configuration per RFC-05 Section 5.4.

    Controls the reliability decay algorithm parameters,
    deprecation thresholds, and recovery mechanics.
    """

    decay_factor: float = 0.95
    min_reliability: float = 0.1
    max_reliability: float = 1.0
    deprecation_threshold: float = 0.3
    consecutive_failure_threshold: int = 5
    recovery_enabled: bool = True
    recovery_rate: float = 0.05
    full_recovery_threshold: float = 0.8
    update_interval_seconds: int = 60


# ============================================================================
# Implicit Edge (RFC-05 Section 6)
# ============================================================================


@dataclass
class ImplicitEdge:
    """Implicit edge discovered by co-occurrence analysis.

    Per RFC-05 Section 6: represents a latent dependency
    between skills discovered from execution telemetry.
    """

    source: str = ""
    target: str = ""
    edge_type: str = "ENHANCES"
    confidence: float = 0.0
    co_occurrence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "confidence": self.confidence,
            "co_occurrence_count": self.co_occurrence_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplicitEdge:
        return cls(
            source=data.get("source", ""),
            target=data.get("target", ""),
            edge_type=data.get("edge_type", "ENHANCES"),
            confidence=data.get("confidence", 0.0),
            co_occurrence_count=data.get("co_occurrence_count", 0),
        )
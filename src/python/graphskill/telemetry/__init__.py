"""GraphSkill telemetry and self-evolution feedback loop.

Per RFC-05: provides tracer infrastructure, EWMA reliability decay,
and telemetry data models for the self-evolution feedback loop.
"""

from graphskill.telemetry.models import (
    DecayConfig,
    EventCode,
    EventType,
    ImplicitEdge,
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
from graphskill.telemetry.decay import ReliabilityDecayEngine

__all__ = [
    # Models
    "EventType",
    "EventCode",
    "TraceContext",
    "TelemetryRecord",
    "TracerConfig",
    "DecayConfig",
    "ImplicitEdge",
    # Tracers
    "TracerInterface",
    "BaseTracer",
    "ExecutionTracer",
    "RoutingTracer",
    # Decay
    "ReliabilityDecayEngine",
]
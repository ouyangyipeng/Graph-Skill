"""
GraphSkill - Topology-Aware Procedural Knowledge Routing for LLM Agents.

GraphSkill is middleware for LLM Agent ecosystems that:
- Converts SKILL.md files into knowledge graphs with topology relationships
- Handles REQUIRES, CONFLICTS_WITH, ENHANCES, SUBSTITUTES relationships
- Provides dynamic routing with conflict resolution (MWIS algorithm)
- Supports runtime self-evolution based on telemetry data

Core Components:
- Ingestion Engine: Offline skill parsing and graph construction
- Graph-Vector Store: Hybrid storage with dual-write consistency
- Routing Gateway: Online dynamic routing with MWIS pruning
- Telemetry & Feedback: Runtime tracing and self-evolution

Example:
    >>> from graphskill import RoutingGateway
    >>> gateway = RoutingGateway()
    >>> result = await gateway.route("I need to commit my changes")
    >>> print(result.selected_skills)
"""

__version__ = "0.1.0"
__author__ = "GraphSkill Team"
__email__ = "team@graphskill.dev"

from graphskill.core.models import (
    SkillNode,
    SkillEdge,
    EdgeType,
    RoutingRequest,
    RoutingResponse,
    RoutingConstraints,
    SelectedSkill,
    TelemetryEvent,
)
from graphskill.core.exceptions import (
    GraphSkillError,
    ValidationError,
    RoutingError,
    IngestionError,
    DatabaseError,
    PermissionError,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    # Core models
    "SkillNode",
    "SkillEdge",
    "EdgeType",
    "RoutingRequest",
    "RoutingResponse",
    "RoutingConstraints",
    "SelectedSkill",
    "TelemetryEvent",
    # Exceptions
    "GraphSkillError",
    "ValidationError",
    "RoutingError",
    "IngestionError",
    "DatabaseError",
    "PermissionError",
]
"""
GraphSkill core data structures.

This module defines all core data structures for the GraphSkill system,
following RFC-08 Data Structures & Schema Definitions specification.

All models use Pydantic V2 for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class EdgeType(str, Enum):
    """
    Topology edge type enumeration.
    
    Defines the four types of relationships between skill nodes:
    - REQUIRES: Hard dependency, must be satisfied
    - CONFLICTS_WITH: Logical conflict, cannot coexist
    - ENHANCES: Soft enhancement, improves success rate
    - SUBSTITUTES: Functional alternative, can replace each other
    """
    
    REQUIRES = "REQUIRES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    ENHANCES = "ENHANCES"
    SUBSTITUTES = "SUBSTITUTES"


class PermissionLevel(str, Enum):
    """
    Permission level enumeration.
    
    Defines the granularity of permission levels.
    """
    
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class SkillNode(BaseModel):
    """
    Skill node data structure.
    
    Represents a single skill entity in the graph database.
    
    Attributes:
        uid: Global unique skill identifier (format: namespace:action)
        embedding_id: Associated vector database primary key
        version: Semantic version number (SemVer 2.0.0)
        intent_description: LLM-oriented intent description for embedding
        permissions: Fine-grained permission declaration list
        trigger_conditions: Trigger precondition assertions
        execution_success_rate: Historical execution success rate (EWMA)
        execution_count: Historical execution count
        is_deprecated: Soft delete flag
        created_at: Creation timestamp
        updated_at: Last update timestamp
        tags: Classification tags
        author: Author identifier
    
    Example:
        >>> skill = SkillNode(
        ...     uid="git:commit_changes",
        ...     version="1.0.0",
        ...     intent_description="Execute Git commit operation...",
        ...     permissions=["fs:read:/tmp", "net:github.com"]
        ... )
    """
    
    uid: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        description="Global unique skill identifier (namespace:action)",
        examples=["git:commit_changes", "db:query_postgres", "fs:read_file"],
    )
    
    embedding_id: Optional[str] = Field(
        default=None,
        description="Associated vector database primary key",
    )
    
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$",
        description="Semantic version number (SemVer 2.0.0)",
        examples=["1.0.0", "2.1.3-beta", "0.5.0-alpha.1"],
    )
    
    intent_description: str = Field(
        ...,
        min_length=50,
        max_length=500,
        description="LLM-oriented intent description for embedding generation",
    )
    
    permissions: list[str] = Field(
        ...,
        min_length=1,
        description="Fine-grained permission declaration list",
    )
    
    trigger_conditions: Optional[dict[str, Any]] = Field(
        default=None,
        description="Trigger precondition assertions",
    )
    
    execution_success_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Historical execution success rate (EWMA decayed)",
    )
    
    execution_count: int = Field(
        default=0,
        ge=0,
        description="Historical execution count",
    )
    
    is_deprecated: bool = Field(
        default=False,
        description="Soft delete flag",
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )
    
    tags: Optional[list[str]] = Field(
        default=None,
        description="Classification tags",
    )
    
    author: Optional[str] = Field(
        default=None,
        description="Author identifier",
    )
    
    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: list[str]) -> list[str]:
        """Validate permission format: category:action[:resource]."""
        import re
        # Support domain names with dots in resource part
        pattern = r"^[a-z]+:[a-z]+(:[a-zA-Z0-9_/.-]+)?$"
        for perm in v:
            if not re.match(pattern, perm):
                raise ValueError(f"Invalid permission format: {perm}. Expected: category:action[:resource]")
        return v
    
    @model_validator(mode="after")
    def validate_updated_at(self) -> "SkillNode":
        """Ensure updated_at >= created_at."""
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self
    
    def update_success_rate(self, success: bool, alpha: float = 0.7) -> float:
        """
        Update execution success rate using EWMA.
        
        Formula: new_rate = α * old_rate + (1 - α) * observation
        
        Args:
            success: Whether the execution was successful
            alpha: EWMA decay factor (default 0.7)
            
        Returns:
            Updated success rate
        """
        observation = 1.0 if success else 0.0
        self.execution_success_rate = alpha * self.execution_success_rate + (1 - alpha) * observation
        self.execution_count += 1
        self.updated_at = datetime.utcnow()
        return self.execution_success_rate


class SkillEdge(BaseModel):
    """
    Skill edge data structure.
    
    Represents a relationship edge between skill nodes in the graph database.
    
    Attributes:
        source_uid: Source node skill ID
        target_uid: Target node skill ID
        edge_type: Edge type (REQUIRES/CONFLICTS_WITH/ENHANCES/SUBSTITUTES)
        weight: Edge weight for MWIS algorithm
        confidence: Relationship confidence (LLM inference result)
        is_implicit: Whether this is an implicit edge (runtime discovered)
        discovered_at: Edge discovery timestamp
        discovery_source: Edge discovery source (manual/llm/co_occurrence/deadlock)
    
    Example:
        >>> edge = SkillEdge(
        ...     source_uid="git:commit",
        ...     target_uid="git:config",
        ...     edge_type=EdgeType.REQUIRES,
        ...     confidence=0.95
        ... )
    """
    
    source_uid: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        description="Source node skill ID",
    )
    
    target_uid: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        description="Target node skill ID",
    )
    
    edge_type: EdgeType = Field(
        ...,
        description="Edge type",
    )
    
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Edge weight for MWIS algorithm",
    )
    
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relationship confidence (LLM inference)",
    )
    
    is_implicit: bool = Field(
        default=False,
        description="Whether this is an implicit edge (runtime discovered)",
    )
    
    discovered_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Edge discovery timestamp",
    )
    
    discovery_source: str = Field(
        default="manual",
        description="Edge discovery source",
        examples=["manual", "llm", "co_occurrence", "deadlock"],
    )
    
    @model_validator(mode="after")
    def validate_edge_direction(self) -> "SkillEdge":
        """
        Validate edge direction constraints.
        
        - REQUIRES and ENHANCES must be directed edges
        - CONFLICTS_WITH and SUBSTITUTES must be undirected (normalized order)
        """
        if self.edge_type in [EdgeType.CONFLICTS_WITH, EdgeType.SUBSTITUTES]:
            # Normalize order for undirected edges
            if self.source_uid > self.target_uid:
                self.source_uid, self.target_uid = self.target_uid, self.source_uid
        return self
    
    @model_validator(mode="after")
    def validate_no_self_edge(self) -> "SkillEdge":
        """Prevent self-referential edges."""
        if self.source_uid == self.target_uid:
            raise ValueError("Self-referential edges are not allowed")
        return self


class RoutingConstraints(BaseModel):
    """
    Routing constraints.
    
    Defines additional constraints for the routing algorithm.
    
    Attributes:
        required_skills: Skills that must be included
        excluded_skills: Skills that must be excluded
        skill_categories: Skill category filters
        min_reliability: Minimum reliability threshold
        max_dependency_depth: Maximum dependency depth
    """
    
    required_skills: Optional[list[str]] = Field(
        default=None,
        description="Skills that must be included",
    )
    
    excluded_skills: Optional[list[str]] = Field(
        default=None,
        description="Skills that must be excluded",
    )
    
    skill_categories: Optional[list[str]] = Field(
        default=None,
        description="Skill category filters",
    )
    
    min_reliability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum reliability threshold",
    )
    
    max_dependency_depth: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Maximum dependency depth",
    )


class RoutingRequest(BaseModel):
    """
    Routing request data structure.
    
    Represents a request to the routing gateway.
    
    Attributes:
        request_id: Unique request identifier
        query: User query text
        context: Runtime context
        constraints: Routing constraints
        max_tokens: Maximum token budget
        tenant_id: Tenant identifier
        session_id: Session identifier
        user_id: User identifier
    """
    
    request_id: UUID = Field(
        default_factory=uuid4,
        description="Unique request identifier",
    )
    
    query: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="User query text",
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime context",
    )
    
    constraints: Optional[RoutingConstraints] = Field(
        default=None,
        description="Routing constraints",
    )
    
    max_tokens: int = Field(
        default=4096,
        ge=256,
        le=32000,
        description="Maximum token budget",
    )
    
    tenant_id: str = Field(
        default="default",
        description="Tenant identifier",
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier",
    )
    
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier",
    )


class SelectedSkill(BaseModel):
    """
    Selected skill item.
    
    Represents a skill selected by the routing algorithm.
    
    Attributes:
        skill_uid: Skill ID
        skill_version: Skill version
        intent_description: Intent description
        permissions: Permission list
        score: Composite score
        is_required: Whether this is a required skill (dependency)
        dependency_depth: Dependency depth
        similarity_score: Vector similarity score
        pagerank_score: PageRank score
        reliability_score: Reliability score
    """
    
    skill_uid: str = Field(..., description="Skill ID")
    skill_version: str = Field(..., description="Skill version")
    intent_description: str = Field(..., description="Intent description")
    permissions: list[str] = Field(..., description="Permission list")
    score: float = Field(..., ge=0.0, le=1.0, description="Composite score")
    is_required: bool = Field(default=False, description="Whether this is a required skill")
    dependency_depth: int = Field(default=0, ge=0, description="Dependency depth")
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Vector similarity score")
    pagerank_score: float = Field(default=0.0, ge=0.0, le=1.0, description="PageRank score")
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Reliability score")


class RoutingResponse(BaseModel):
    """
    Routing response data structure.
    
    Represents the response from the routing gateway.
    
    Attributes:
        request_id: Associated request ID
        selected_skills: Selected skill list
        total_tokens: Total token count
        routing_time_ms: Routing time in milliseconds
        confidence: Routing confidence
        fallback_used: Whether fallback mode was used
        metadata: Metadata
    """
    
    request_id: UUID = Field(
        ...,
        description="Associated request ID",
    )
    
    selected_skills: list[SelectedSkill] = Field(
        ...,
        description="Selected skill list",
    )
    
    total_tokens: int = Field(
        ...,
        ge=0,
        description="Total token count",
    )
    
    routing_time_ms: int = Field(
        ...,
        ge=0,
        description="Routing time in milliseconds",
    )
    
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Routing confidence",
    )
    
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback mode was used",
    )
    
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata",
    )
    
    @model_validator(mode="after")
    def validate_no_conflicts(self) -> "RoutingResponse":
        """Validate that selected skills have no conflicts."""
        skill_uids = [s.skill_uid for s in self.selected_skills]
        # Check for duplicates
        if len(skill_uids) != len(set(skill_uids)):
            raise ValueError("Duplicate skills in selection")
        return self


class TelemetryEvent(BaseModel):
    """
    Telemetry event data structure.
    
    Represents a telemetry event for monitoring and self-evolution.
    
    Attributes:
        event_id: Unique event identifier
        event_type: Event type
        timestamp: Event timestamp
        skill_uid: Associated skill ID
        session_id: Session identifier
        outcome: Execution result (success/failure/timeout)
        duration_ms: Execution duration in milliseconds
        error_info: Error information
        context: Execution context
    """
    
    event_id: UUID = Field(
        default_factory=uuid4,
        description="Unique event identifier",
    )
    
    event_type: str = Field(
        ...,
        description="Event type",
        examples=["skill_execution", "skill_co_occurrence", "skill_conflict"],
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp",
    )
    
    skill_uid: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        description="Associated skill ID",
    )
    
    session_id: str = Field(
        ...,
        description="Session identifier",
    )
    
    outcome: str = Field(
        ...,
        description="Execution result",
        examples=["success", "failure", "timeout"],
    )
    
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Execution duration in milliseconds",
    )
    
    error_info: Optional[dict[str, Any]] = Field(
        default=None,
        description="Error information",
    )
    
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution context",
    )
    
    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        """Validate outcome value."""
        valid_outcomes = ["success", "failure", "timeout"]
        if v not in valid_outcomes:
            raise ValueError(f"Invalid outcome: {v}. Must be one of {valid_outcomes}")
        return v


class SkillManifest(BaseModel):
    """
    Skill manifest data structure.
    
    Represents the YAML frontmatter of a SKILL.md file.
    
    Attributes:
        skill_id: Skill identifier (same as uid)
        version: Semantic version
        intent_description: Intent description
        permissions: Permission list
        topology_hints: Human-declared topology hints
        trigger_conditions: Trigger conditions
        author: Author
        created_at: Creation time
        updated_at: Update time
        deprecated: Deprecated flag
        tags: Tags
    """
    
    skill_id: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        description="Skill identifier",
    )
    
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$",
        description="Semantic version",
    )
    
    intent_description: str = Field(
        ...,
        min_length=50,
        max_length=500,
        description="Intent description",
    )
    
    permissions: list[str] = Field(
        ...,
        min_length=1,
        description="Permission list",
    )
    
    topology_hints: Optional[dict[str, list[str]]] = Field(
        default=None,
        description="Human-declared topology hints",
    )
    
    trigger_conditions: Optional[dict[str, Any]] = Field(
        default=None,
        description="Trigger conditions",
    )
    
    author: Optional[str] = Field(
        default=None,
        description="Author",
    )
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="Creation time",
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Update time",
    )
    
    deprecated: bool = Field(
        default=False,
        description="Deprecated flag",
    )
    
    tags: Optional[list[str]] = Field(
        default=None,
        description="Tags",
    )
    
    def to_skill_node(self) -> SkillNode:
        """Convert manifest to SkillNode."""
        return SkillNode(
            uid=self.skill_id,
            version=self.version,
            intent_description=self.intent_description,
            permissions=self.permissions,
            trigger_conditions=self.trigger_conditions,
            author=self.author,
            created_at=self.created_at or datetime.utcnow(),
            updated_at=self.updated_at or datetime.utcnow(),
            is_deprecated=self.deprecated,
            tags=self.tags,
        )
"""
Runtime data models per RFC-04.

Defines data structures for context injection, permission interception,
session management, and output assembly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4


# ============================================================================
# Context Injection Models (RFC-04 Section 3)
# ============================================================================


class InjectionPosition(str):
    """Injection position per RFC-04 Section 3.5."""
    AFTER_SYSTEM = "after_system"
    BEFORE_QUERY = "before_query"
    CUSTOM = "custom"


@dataclass
class InjectionConfig:
    """Injection configuration per RFC-04 Section 3.5."""

    position: str = "after_system"
    system_prompt_reserved: int = 500
    conversation_history_reserved: int = 1000
    skills_context_max: int = 4000
    strategy_mode: str = "dynamic"
    refresh_on_query: bool = True
    cache_injected_context: bool = True
    format_type: str = "xml"
    include_permissions: bool = True
    include_dependencies: bool = True


@dataclass
class AgentPrompt:
    """Agent prompt structure per RFC-04 Section 3.3.

    Represents the original prompt from the Agent framework
    before skill context injection.
    """

    system_prompt: str = ""
    user_query: str = ""
    conversation_history: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_query": self.user_query,
            "conversation_history": self.conversation_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPrompt:
        return cls(
            system_prompt=data.get("system_prompt", ""),
            user_query=data.get("user_query", ""),
            conversation_history=data.get("conversation_history", ""),
        )


@dataclass
class InjectedPrompt:
    """Result of context injection per RFC-04 Section 3.4.

    Contains the original prompt, injected context, final assembled
    prompt, routing result reference, and token count.
    """

    original_prompt: AgentPrompt = field(default_factory=AgentPrompt)
    injected_context: str = ""
    final_prompt: str = ""
    routing_result_id: str = ""
    token_count: int = 0
    injection_position: str = "after_system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_prompt": self.original_prompt.to_dict(),
            "injected_context": self.injected_context,
            "final_prompt": self.final_prompt,
            "routing_result_id": self.routing_result_id,
            "token_count": self.token_count,
            "injection_position": self.injection_position,
        }


# ============================================================================
# Permission Interception Models (RFC-04 Section 5)
# ============================================================================


@dataclass
class ActionRequest:
    """Agent action request per RFC-04 Section 5.3."""

    tool_call: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: str = ""
    request_id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        if not self.request_id:
            self.request_id = str(uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call": self.tool_call,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
        }


@dataclass
class ParsedAction:
    """Parsed action per RFC-04 Section 5.3."""

    skill_id: str = ""
    tool_name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    resource_type: str = ""
    action_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "resource_type": self.resource_type,
            "action_type": self.action_type,
        }


@dataclass
class PermissionInfo:
    """Permission declaration per RFC-04 Section 5.3."""

    resource_type: str = ""
    action: str = ""
    target: str = "*"

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "action": self.action,
            "target": self.target,
        }

    @classmethod
    def from_string(cls, perm_str: str) -> PermissionInfo:
        """Parse permission string (e.g., 'fs:read:/tmp') into PermissionInfo."""
        parts = perm_str.split(":")
        return cls(
            resource_type=parts[0] if len(parts) > 0 else "",
            action=parts[1] if len(parts) > 1 else "",
            target=parts[2] if len(parts) > 2 else "*",
        )


@dataclass
class InterceptionResult:
    """Interception result per RFC-04 Section 5.3."""

    allowed: bool = False
    reason: str = ""
    error_code: str = ""
    skill_id: str = ""
    action: Optional[ParsedAction] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "error_code": self.error_code,
            "skill_id": self.skill_id,
            "action": self.action.to_dict() if self.action else None,
        }

    def to_agent_response(self) -> dict[str, Any]:
        """Convert to Agent-understandable response per RFC-04 Section 5.4."""
        response: dict[str, Any] = {
            "allowed": self.allowed,
            "reason": self.reason,
        }
        if not self.allowed:
            response["error"] = {
                "type": "permission_denied" if self.error_code == "PERMISSION_DENIED" else "skill_not_in_context",
                "code": self.error_code,
                "message": self.reason,
                "skill_id": self.skill_id,
                "suggestion": self._generate_suggestion(),
            }
            if self.action:
                response["error"]["action"] = self.action.to_dict()
        return response

    def _generate_suggestion(self) -> str:
        """Generate repair suggestion per RFC-04 Section 5.4."""
        if self.error_code == "PERMISSION_DENIED":
            if self.action:
                return f"Request additional permission: {self.action.resource_type}:{self.action.action_type}"
            return "Review skill permissions and session authorization"
        elif self.error_code == "SKILL_NOT_IN_CONTEXT":
            return f"Request skill '{self.skill_id}' to be loaded into context"
        return "Review skill permissions and session authorization"


# ============================================================================
# Session Management Models (RFC-04 Section 6)
# ============================================================================


@dataclass
class SessionContext:
    """Session skill context per RFC-04 Section 6.1."""

    skills: list[str] = field(default_factory=list)
    routing_mode: str = "none"
    last_routing_time: Optional[str] = None
    token_count: int = 0
    query_hash: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skills": self.skills,
            "routing_mode": self.routing_mode,
            "last_routing_time": self.last_routing_time,
            "token_count": self.token_count,
            "query_hash": self.query_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionContext:
        return cls(
            skills=data.get("skills", []),
            routing_mode=data.get("routing_mode", "none"),
            last_routing_time=data.get("last_routing_time"),
            token_count=data.get("token_count", 0),
            query_hash=data.get("query_hash"),
        )


@dataclass
class SessionAuthorization:
    """Session authorization scope per RFC-04 Section 5.3."""

    session_id: str = ""
    authorized_permissions: list[PermissionInfo] = field(default_factory=list)
    authorized_skills: list[str] = field(default_factory=list)
    expires_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "authorized_permissions": [p.to_dict() for p in self.authorized_permissions],
            "authorized_skills": self.authorized_skills,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionAuthorization:
        perms = [
            PermissionInfo.from_string(p) if isinstance(p, str)
            else PermissionInfo(**p)
            for p in data.get("authorized_permissions", [])
        ]
        return cls(
            session_id=data.get("session_id", ""),
            authorized_permissions=perms,
            authorized_skills=data.get("authorized_skills", []),
            expires_at=data.get("expires_at"),
        )


@dataclass
class ExecutionState:
    """Execution state per RFC-04 Section 6.1."""

    status: str = "idle"
    current_skill: Optional[str] = None
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    error_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current_skill": self.current_skill,
            "pending_actions": self.pending_actions,
            "error_history": self.error_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionState:
        return cls(
            status=data.get("status", "idle"),
            current_skill=data.get("current_skill"),
            pending_actions=data.get("pending_actions", []),
            error_history=data.get("error_history", []),
        )


@dataclass
class AgentSession:
    """Agent session per RFC-04 Section 6.1."""

    session_id: str = ""
    agent_id: str = ""
    created_at: str = ""
    expires_at: str = ""
    current_context: SessionContext = field(default_factory=SessionContext)
    context_history: list[dict[str, Any]] = field(default_factory=list)
    authorization: SessionAuthorization = field(default_factory=SessionAuthorization)
    execution_state: ExecutionState = field(default_factory=ExecutionState)
    skill_call_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = f"sess_{uuid4().hex[:16]}"
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.expires_at:
            self.expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "current_context": self.current_context.to_dict(),
            "context_history": self.context_history,
            "authorization": self.authorization.to_dict(),
            "execution_state": self.execution_state.to_dict(),
            "skill_call_history": self.skill_call_history,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSession:
        return cls(
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
            current_context=SessionContext.from_dict(data.get("current_context", {})),
            context_history=data.get("context_history", []),
            authorization=SessionAuthorization.from_dict(data.get("authorization", {})),
            execution_state=ExecutionState.from_dict(data.get("execution_state", {})),
            skill_call_history=data.get("skill_call_history", []),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> AgentSession:
        return cls.from_dict(json.loads(json_str))


@dataclass
class SessionConfig:
    """Session configuration per RFC-04 Section 6.3."""

    session_ttl: int = 86400  # 24 hours in seconds
    max_context_history: int = 50
    max_skill_call_history: int = 100
    max_sessions_per_agent: int = 10
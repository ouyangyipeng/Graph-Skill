"""
Runtime data models unit tests per RFC-04.

Tests AgentPrompt, InjectedPrompt, ActionRequest, ParsedAction,
PermissionInfo, InterceptionResult, SessionContext, SessionAuthorization,
ExecutionState, AgentSession, InjectionConfig, SessionConfig.
"""

from __future__ import annotations

import json
import pytest

from graphskill.runtime.models import (
    ActionRequest,
    AgentPrompt,
    AgentSession,
    ExecutionState,
    InjectionConfig,
    InjectedPrompt,
    InterceptionResult,
    ParsedAction,
    PermissionInfo,
    SessionAuthorization,
    SessionConfig,
    SessionContext,
)


# ============================================================================
# AgentPrompt Tests
# ============================================================================


class TestAgentPrompt:
    """AgentPrompt data structure tests."""

    def test_create_defaults(self) -> None:
        """Test default prompt is empty strings."""
        prompt = AgentPrompt()
        assert prompt.system_prompt == ""
        assert prompt.user_query == ""
        assert prompt.conversation_history == ""

    def test_create_with_values(self) -> None:
        """Test prompt with all fields."""
        prompt = AgentPrompt(
            system_prompt="You are an AI assistant",
            user_query="Please help me commit code",
            conversation_history="Previous messages...",
        )
        assert prompt.system_prompt == "You are an AI assistant"
        assert prompt.user_query == "Please help me commit code"

    def test_to_dict(self) -> None:
        """Test serialization."""
        prompt = AgentPrompt(system_prompt="sys", user_query="usr")
        d = prompt.to_dict()
        assert d["system_prompt"] == "sys"
        assert d["user_query"] == "usr"

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {"system_prompt": "sys", "user_query": "usr", "conversation_history": "hist"}
        prompt = AgentPrompt.from_dict(data)
        assert prompt.system_prompt == "sys"
        assert prompt.conversation_history == "hist"


# ============================================================================
# InjectedPrompt Tests
# ============================================================================


class TestInjectedPrompt:
    """InjectedPrompt data structure tests."""

    def test_create_defaults(self) -> None:
        """Test default values."""
        result = InjectedPrompt()
        assert result.injected_context == ""
        assert result.final_prompt == ""
        assert result.token_count == 0
        assert result.injection_position == "after_system"

    def test_create_with_values(self) -> None:
        """Test with injected content."""
        result = InjectedPrompt(
            original_prompt=AgentPrompt(system_prompt="sys"),
            injected_context="<Skills>...</Skills>",
            final_prompt="sys\n\n<Skills>...</Skills>\n\nusr",
            token_count=500,
        )
        assert result.original_prompt.system_prompt == "sys"
        assert result.token_count == 500

    def test_to_dict(self) -> None:
        """Test serialization."""
        result = InjectedPrompt(
            injected_context="skills",
            final_prompt="full",
            token_count=100,
        )
        d = result.to_dict()
        assert d["injected_context"] == "skills"
        assert d["token_count"] == 100


# ============================================================================
# InjectionConfig Tests
# ============================================================================


class TestInjectionConfig:
    """InjectionConfig tests per RFC-04 Section 3.5."""

    def test_default_config(self) -> None:
        """Test default values."""
        config = InjectionConfig()
        assert config.position == "after_system"
        assert config.system_prompt_reserved == 500
        assert config.skills_context_max == 4000
        assert config.format_type == "xml"

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = InjectionConfig(
            position="before_query",
            skills_context_max=8000,
            format_type="json",
        )
        assert config.position == "before_query"
        assert config.skills_context_max == 8000


# ============================================================================
# ActionRequest Tests
# ============================================================================


class TestActionRequest:
    """ActionRequest data structure tests."""

    def test_create_defaults(self) -> None:
        """Test auto-generated fields."""
        req = ActionRequest()
        assert req.tool_call == {}
        assert req.session_id == ""
        assert req.timestamp != ""
        assert req.request_id != ""

    def test_create_with_tool_call(self) -> None:
        """Test with tool call data."""
        req = ActionRequest(
            tool_call={"name": "git_commit", "parameters": {"message": "fix"}},
            session_id="sess_001",
        )
        assert req.tool_call["name"] == "git_commit"

    def test_to_dict(self) -> None:
        """Test serialization."""
        req = ActionRequest(
            tool_call={"name": "test"},
            session_id="sess_001",
        )
        d = req.to_dict()
        assert d["session_id"] == "sess_001"


# ============================================================================
# ParsedAction Tests
# ============================================================================


class TestParsedAction:
    """ParsedAction data structure tests."""

    def test_create_defaults(self) -> None:
        """Test default values."""
        action = ParsedAction()
        assert action.skill_id == ""
        assert action.tool_name == ""

    def test_create_with_values(self) -> None:
        """Test with all fields."""
        action = ParsedAction(
            skill_id="git:commit",
            tool_name="git_commit",
            resource_type="fs",
            action_type="write",
        )
        assert action.skill_id == "git:commit"

    def test_to_dict(self) -> None:
        """Test serialization."""
        action = ParsedAction(skill_id="test", resource_type="exec")
        d = action.to_dict()
        assert d["skill_id"] == "test"


# ============================================================================
# PermissionInfo Tests
# ============================================================================


class TestPermissionInfo:
    """PermissionInfo tests."""

    def test_create_defaults(self) -> None:
        """Test default values with wildcard target."""
        perm = PermissionInfo()
        assert perm.resource_type == ""
        assert perm.target == "*"

    def test_create_with_values(self) -> None:
        """Test with explicit values."""
        perm = PermissionInfo(resource_type="fs", action="read", target="/tmp")
        assert perm.resource_type == "fs"
        assert perm.target == "/tmp"

    def test_from_string(self) -> None:
        """Test parsing permission string."""
        perm = PermissionInfo.from_string("fs:read:/tmp")
        assert perm.resource_type == "fs"
        assert perm.action == "read"
        assert perm.target == "/tmp"

    def test_from_string_two_parts(self) -> None:
        """Test parsing 2-part permission string."""
        perm = PermissionInfo.from_string("exec:run")
        assert perm.resource_type == "exec"
        assert perm.action == "run"
        assert perm.target == "*"

    def test_from_string_one_part(self) -> None:
        """Test parsing 1-part permission string."""
        perm = PermissionInfo.from_string("fs")
        assert perm.resource_type == "fs"
        assert perm.action == ""

    def test_from_string_empty(self) -> None:
        """Test parsing empty string."""
        perm = PermissionInfo.from_string("")
        assert perm.resource_type == ""

    def test_to_dict(self) -> None:
        """Test serialization."""
        perm = PermissionInfo(resource_type="net", action="connect", target="github.com")
        d = perm.to_dict()
        assert d["resource_type"] == "net"


# ============================================================================
# InterceptionResult Tests
# ============================================================================


class TestInterceptionResult:
    """InterceptionResult tests."""

    def test_create_allowed(self) -> None:
        """Test allowed result."""
        result = InterceptionResult(
            allowed=True,
            reason="Permission check passed",
            skill_id="git:commit",
        )
        assert result.allowed is True
        assert result.error_code == ""

    def test_create_denied(self) -> None:
        """Test denied result."""
        result = InterceptionResult(
            allowed=False,
            reason="Permission denied",
            error_code="PERMISSION_DENIED",
            skill_id="git:commit",
            action=ParsedAction(resource_type="fs", action_type="write"),
        )
        assert result.allowed is False
        assert result.error_code == "PERMISSION_DENIED"

    def test_to_agent_response_allowed(self) -> None:
        """Test agent response for allowed."""
        result = InterceptionResult(allowed=True, reason="OK")
        response = result.to_agent_response()
        assert response["allowed"] is True

    def test_to_agent_response_denied(self) -> None:
        """Test agent response for denied includes error."""
        result = InterceptionResult(
            allowed=False,
            reason="Not in context",
            error_code="SKILL_NOT_IN_CONTEXT",
            skill_id="git:push",
        )
        response = result.to_agent_response()
        assert "error" in response
        assert response["error"]["code"] == "SKILL_NOT_IN_CONTEXT"
        assert "suggestion" in response["error"]

    def test_suggestion_permission_denied(self) -> None:
        """Test suggestion for permission denied."""
        result = InterceptionResult(
            allowed=False,
            error_code="PERMISSION_DENIED",
            action=ParsedAction(resource_type="fs", action_type="write"),
        )
        response = result.to_agent_response()
        assert "fs:write" in response["error"]["suggestion"]

    def test_suggestion_not_in_context(self) -> None:
        """Test suggestion for skill not in context."""
        result = InterceptionResult(
            allowed=False,
            error_code="SKILL_NOT_IN_CONTEXT",
            skill_id="git:push",
        )
        response = result.to_agent_response()
        assert "git:push" in response["error"]["suggestion"]

    def test_to_dict(self) -> None:
        """Test serialization."""
        result = InterceptionResult(
            allowed=True,
            reason="OK",
            skill_id="test",
            action=ParsedAction(skill_id="test"),
        )
        d = result.to_dict()
        assert d["allowed"] is True
        assert d["action"]["skill_id"] == "test"


# ============================================================================
# SessionContext Tests
# ============================================================================


class TestSessionContext:
    """SessionContext data structure tests."""

    def test_create_defaults(self) -> None:
        """Test default context."""
        ctx = SessionContext()
        assert ctx.skills == []
        assert ctx.routing_mode == "none"
        assert ctx.token_count == 0

    def test_create_with_skills(self) -> None:
        """Test context with skills."""
        ctx = SessionContext(
            skills=["git:commit", "git:push"],
            routing_mode="normal",
            token_count=2000,
        )
        assert len(ctx.skills) == 2

    def test_to_dict(self) -> None:
        """Test serialization."""
        ctx = SessionContext(skills=["a"], routing_mode="dynamic")
        d = ctx.to_dict()
        assert d["skills"] == ["a"]

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {"skills": ["git:commit"], "routing_mode": "normal", "token_count": 1500}
        ctx = SessionContext.from_dict(data)
        assert ctx.skills == ["git:commit"]
        assert ctx.token_count == 1500

    def test_roundtrip(self) -> None:
        """Test dict roundtrip."""
        ctx = SessionContext(skills=["a", "b"], routing_mode="fallback", token_count=500)
        d = ctx.to_dict()
        ctx2 = SessionContext.from_dict(d)
        assert ctx2.skills == ctx.skills


# ============================================================================
# SessionAuthorization Tests
# ============================================================================


class TestSessionAuthorization:
    """SessionAuthorization tests."""

    def test_create_defaults(self) -> None:
        """Test default authorization."""
        auth = SessionAuthorization()
        assert auth.session_id == ""
        assert auth.authorized_permissions == []
        assert auth.authorized_skills == []

    def test_create_with_permissions(self) -> None:
        """Test with permission list."""
        auth = SessionAuthorization(
            session_id="sess_001",
            authorized_permissions=[
                PermissionInfo(resource_type="fs", action="read", target="/"),
            ],
            authorized_skills=["git:commit"],
        )
        assert len(auth.authorized_permissions) == 1

    def test_to_dict(self) -> None:
        """Test serialization."""
        auth = SessionAuthorization(
            session_id="sess_001",
            authorized_skills=["a"],
        )
        d = auth.to_dict()
        assert d["session_id"] == "sess_001"

    def test_from_dict_with_string_perms(self) -> None:
        """Test deserialization with string permissions."""
        data = {
            "session_id": "sess_001",
            "authorized_permissions": ["fs:read:/tmp", "exec:run:git"],
            "authorized_skills": ["git:commit"],
        }
        auth = SessionAuthorization.from_dict(data)
        assert len(auth.authorized_permissions) == 2
        assert auth.authorized_permissions[0].resource_type == "fs"

    def test_from_dict_with_dict_perms(self) -> None:
        """Test deserialization with dict permissions."""
        data = {
            "session_id": "sess_001",
            "authorized_permissions": [
                {"resource_type": "fs", "action": "read", "target": "/tmp"},
            ],
        }
        auth = SessionAuthorization.from_dict(data)
        assert auth.authorized_permissions[0].target == "/tmp"


# ============================================================================
# ExecutionState Tests
# ============================================================================


class TestExecutionState:
    """ExecutionState tests."""

    def test_create_defaults(self) -> None:
        """Test default idle state."""
        state = ExecutionState()
        assert state.status == "idle"
        assert state.current_skill is None

    def test_create_executing(self) -> None:
        """Test executing state."""
        state = ExecutionState(status="executing", current_skill="git:commit")
        assert state.status == "executing"

    def test_to_dict_from_dict(self) -> None:
        """Test roundtrip."""
        state = ExecutionState(status="error", error_history=[{"type": "timeout"}])
        d = state.to_dict()
        state2 = ExecutionState.from_dict(d)
        assert state2.status == "error"


# ============================================================================
# AgentSession Tests
# ============================================================================


class TestAgentSession:
    """AgentSession tests per RFC-04 Section 6.1."""

    def test_create_defaults(self) -> None:
        """Test auto-generated session_id, timestamps."""
        session = AgentSession()
        assert session.session_id.startswith("sess_")
        assert session.created_at != ""
        assert session.expires_at != ""
        assert session.current_context.routing_mode == "none"

    def test_create_with_agent_id(self) -> None:
        """Test session with agent_id."""
        session = AgentSession(agent_id="agent_001")
        assert session.agent_id == "agent_001"

    def test_to_dict(self) -> None:
        """Test serialization."""
        session = AgentSession(
            agent_id="agent_test",
            current_context=SessionContext(skills=["git:commit"]),
        )
        d = session.to_dict()
        assert d["agent_id"] == "agent_test"
        assert d["current_context"]["skills"] == ["git:commit"]

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        session = AgentSession(agent_id="agent_json")
        json_str = session.to_json()
        parsed = json.loads(json_str)
        assert parsed["agent_id"] == "agent_json"

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "session_id": "sess_manual",
            "agent_id": "agent_from",
            "current_context": {"skills": ["a"], "routing_mode": "normal"},
            "authorization": {"session_id": "sess_manual", "authorized_skills": ["a"]},
        }
        session = AgentSession.from_dict(data)
        assert session.session_id == "sess_manual"
        assert session.current_context.skills == ["a"]

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        json_str = json.dumps({
            "session_id": "sess_json",
            "agent_id": "agent_json_in",
            "current_context": {"skills": [], "routing_mode": "none"},
        })
        session = AgentSession.from_json(json_str)
        assert session.session_id == "sess_json"

    def test_roundtrip(self) -> None:
        """Test JSON roundtrip."""
        session = AgentSession(
            agent_id="agent_rt",
            current_context=SessionContext(skills=["git:commit", "git:push"]),
            authorization=SessionAuthorization(
                authorized_skills=["git:commit"],
                authorized_permissions=[PermissionInfo(resource_type="fs", action="read")],
            ),
        )
        json_str = session.to_json()
        session2 = AgentSession.from_json(json_str)
        assert session2.agent_id == session.agent_id
        assert session2.current_context.skills == session.current_context.skills


# ============================================================================
# SessionConfig Tests
# ============================================================================


class TestSessionConfig:
    """SessionConfig tests per RFC-04 Section 6.3."""

    def test_default_config(self) -> None:
        """Test default 24-hour TTL."""
        config = SessionConfig()
        assert config.session_ttl == 86400
        assert config.max_context_history == 50

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SessionConfig(
            session_ttl=3600,
            max_context_history=10,
        )
        assert config.session_ttl == 3600
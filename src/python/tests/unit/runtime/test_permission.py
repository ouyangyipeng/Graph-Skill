"""
Permission interceptor unit tests per RFC-04 Section 5.

Tests PermissionInterceptor: intercept, action parsing, permission matching,
session authorization, and context checking.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from graphskill.runtime.models import (
    ActionRequest,
    InterceptionResult,
    ParsedAction,
    PermissionInfo,
    SessionAuthorization,
    SessionContext,
)
from graphskill.runtime.permission import PermissionInterceptor


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_graph_store() -> MagicMock:
    """Create mock graph store with skill permissions."""
    store = MagicMock()
    store.get_node = AsyncMock(return_value={
        "uid": "git:commit",
        "permissions": ["fs:read:/", "exec:run:git"],
    })
    return store


@pytest.fixture
def mock_session_manager() -> MagicMock:
    """Create mock session manager."""
    manager = MagicMock()
    manager.get_authorization = AsyncMock(return_value=SessionAuthorization(
        session_id="sess_001",
        authorized_permissions=[
            PermissionInfo(resource_type="fs", action="read", target="/"),
            PermissionInfo(resource_type="exec", action="run", target="git"),
        ],
        authorized_skills=["git:commit", "run:git:command"],
    ))
    manager.get_current_context = AsyncMock(return_value=SessionContext(
        skills=["git:commit", "git:push", "run:git:command"],
    ))
    return manager


@pytest.fixture
def interceptor(
    mock_graph_store: MagicMock,
    mock_session_manager: MagicMock,
) -> PermissionInterceptor:
    """Create interceptor with mock stores."""
    return PermissionInterceptor(
        graph_store=mock_graph_store,
        session_manager=mock_session_manager,
    )


@pytest.fixture
def interceptor_no_deps() -> PermissionInterceptor:
    """Create interceptor without graph store or session manager."""
    return PermissionInterceptor()


@pytest.fixture
def action_request_allowed() -> ActionRequest:
    """Create action request that should be allowed.

    'run_git_command' → action_type='run', resource_type='exec'
    Matches skill permission 'exec:run:git' (target='git').
    """
    return ActionRequest(
        tool_call={
            "name": "run_git_command",
            "parameters": {"command": "git", "target": "git"},
        },
        session_id="sess_001",
    )


@pytest.fixture
def action_request_denied() -> ActionRequest:
    """Create action request that should be denied."""
    return ActionRequest(
        tool_call={
            "name": "db_drop_table",
            "parameters": {"table": "users"},
        },
        session_id="sess_001",
    )


# ============================================================================
# Action Parsing Tests
# ============================================================================


class TestActionParsing:
    """Action parsing tests per RFC-04 Section 5.2."""

    def test_parse_tool_call(self, interceptor: PermissionInterceptor) -> None:
        """Test parsing tool call to ParsedAction."""
        req = ActionRequest(
            tool_call={"name": "git_commit", "parameters": {"message": "fix"}},
            session_id="sess_001",
        )
        action = interceptor._parse_action(req)
        assert action.skill_id == "git:commit"
        assert action.tool_name == "git_commit"

    def test_parse_tool_with_colon(self, interceptor: PermissionInterceptor) -> None:
        """Test parsing tool name already in skill_id format."""
        req = ActionRequest(
            tool_call={"name": "git:commit", "parameters": {}},
        )
        action = interceptor._parse_action(req)
        assert action.skill_id == "git:commit"

    def test_map_tool_to_skill(self, interceptor: PermissionInterceptor) -> None:
        """Test tool-to-skill mapping convention."""
        assert interceptor._map_tool_to_skill("git_commit") == "git:commit"
        assert interceptor._map_tool_to_skill("git:commit") == "git:commit"

    def test_infer_resource_type_fs(self, interceptor: PermissionInterceptor) -> None:
        """Test fs resource type inference."""
        assert interceptor._infer_resource_type({"path": "/tmp"}) == "fs"
        assert interceptor._infer_resource_type({"file": "test.py"}) == "fs"

    def test_infer_resource_type_net(self, interceptor: PermissionInterceptor) -> None:
        """Test net resource type inference."""
        assert interceptor._infer_resource_type({"url": "http://example.com"}) == "net"

    def test_infer_resource_type_db(self, interceptor: PermissionInterceptor) -> None:
        """Test db resource type inference."""
        assert interceptor._infer_resource_type({"query": "SELECT *"}) == "db"

    def test_infer_resource_type_exec(self, interceptor: PermissionInterceptor) -> None:
        """Test exec resource type inference."""
        assert interceptor._infer_resource_type({"command": "ls -la"}) == "exec"

    def test_infer_resource_type_unknown(self, interceptor: PermissionInterceptor) -> None:
        """Test unknown resource type."""
        assert interceptor._infer_resource_type({"foo": "bar"}) == "unknown"

    def test_infer_action_type_read(self, interceptor: PermissionInterceptor) -> None:
        """Test read action type inference."""
        assert interceptor._infer_action_type("git_read_file") == "read"
        assert interceptor._infer_action_type("list_files") == "read"
        assert interceptor._infer_action_type("check_status") == "read"

    def test_infer_action_type_write(self, interceptor: PermissionInterceptor) -> None:
        """Test write action type inference."""
        assert interceptor._infer_action_type("git_commit") == "write"
        assert interceptor._infer_action_type("create_file") == "write"
        assert interceptor._infer_action_type("push_changes") == "write"

    def test_infer_action_type_delete(self, interceptor: PermissionInterceptor) -> None:
        """Test delete action type inference."""
        assert interceptor._infer_action_type("delete_file") == "delete"

    def test_infer_action_type_run(self, interceptor: PermissionInterceptor) -> None:
        """Test run action type inference."""
        assert interceptor._infer_action_type("run_test") == "run"

    def test_infer_action_type_unknown(self, interceptor: PermissionInterceptor) -> None:
        """Test unknown action type."""
        assert interceptor._infer_action_type("unknown_op") == "unknown"


# ============================================================================
# Permission Matching Tests
# ============================================================================


class TestPermissionMatching:
    """Permission matching tests per RFC-04 Section 5.2."""

    def test_match_exact_permission(self, interceptor: PermissionInterceptor) -> None:
        """Test exact permission match."""
        action = ParsedAction(
            resource_type="fs", action_type="read",
            parameters={"target": "/tmp"},
        )
        perm = PermissionInfo(resource_type="fs", action="read", target="/tmp")
        assert interceptor._match_permission(action, perm) is True

    def test_match_wildcard_target(self, interceptor: PermissionInterceptor) -> None:
        """Test wildcard target matching."""
        action = ParsedAction(resource_type="fs", action_type="read")
        perm = PermissionInfo(resource_type="fs", action="read", target="*")
        assert interceptor._match_permission(action, perm) is True

    def test_mismatch_resource_type(self, interceptor: PermissionInterceptor) -> None:
        """Test mismatched resource type."""
        action = ParsedAction(resource_type="net", action_type="read")
        perm = PermissionInfo(resource_type="fs", action="read", target="*")
        assert interceptor._match_permission(action, perm) is False

    def test_mismatch_action_type(self, interceptor: PermissionInterceptor) -> None:
        """Test mismatched action type."""
        action = ParsedAction(resource_type="fs", action_type="write")
        perm = PermissionInfo(resource_type="fs", action="read", target="*")
        assert interceptor._match_permission(action, perm) is False

    def test_match_path_prefix(self, interceptor: PermissionInterceptor) -> None:
        """Test path prefix matching for fs resources."""
        action = ParsedAction(
            resource_type="fs",
            action_type="read",
            parameters={"path": "/tmp/project/file.py"},
        )
        perm = PermissionInfo(resource_type="fs", action="read", target="/tmp*")
        assert interceptor._match_permission(action, perm) is True


# ============================================================================
# Session Authorization Tests
# ============================================================================


class TestSessionAuthorization:
    """Session authorization check tests."""

    def test_check_session_auth_allowed(self, interceptor: PermissionInterceptor) -> None:
        """Test permission within session auth scope."""
        perm = PermissionInfo(resource_type="fs", action="read", target="/")
        auth = SessionAuthorization(
            authorized_permissions=[PermissionInfo(resource_type="fs", action="read", target="*")],
        )
        assert interceptor._check_session_authorization(perm, auth) is True

    def test_check_session_auth_denied(self, interceptor: PermissionInterceptor) -> None:
        """Test permission outside session auth scope."""
        perm = PermissionInfo(resource_type="exec", action="run", target="rm")
        auth = SessionAuthorization(
            authorized_permissions=[PermissionInfo(resource_type="fs", action="read", target="/")],
        )
        assert interceptor._check_session_authorization(perm, auth) is False

    def test_check_session_auth_empty_auth(self, interceptor: PermissionInterceptor) -> None:
        """Test default allow when no auth permissions defined."""
        perm = PermissionInfo(resource_type="fs", action="read", target="/")
        auth = SessionAuthorization()  # empty auth
        assert interceptor._check_session_authorization(perm, auth) is True


# ============================================================================
# Interception Integration Tests
# ============================================================================


class TestInterception:
    """Full interception flow tests."""

    @pytest.mark.asyncio
    async def test_intercept_allowed(
        self,
        interceptor: PermissionInterceptor,
        action_request_allowed: ActionRequest,
        mock_graph_store: MagicMock,
        mock_session_manager: MagicMock,
    ) -> None:
        """Test allowed action: git_commit with fs:read + exec:run:git."""
        result = await interceptor.intercept(
            action_request_allowed, "sess_001",
        )
        assert result.allowed is True
        assert result.skill_id == "run:git:command"

    @pytest.mark.asyncio
    async def test_intercept_denied_permission(
        self,
        interceptor: PermissionInterceptor,
        action_request_denied: ActionRequest,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test denied action: db_drop_table not in skill permissions."""
        # Override mock for the denied skill (no permissions)
        mock_graph_store.get_node = AsyncMock(return_value={
            "uid": "db:drop_table",
            "permissions": ["db:read"],  # Only read, not write/delete
        })
        result = await interceptor.intercept(
            action_request_denied, "sess_001",
        )
        assert result.allowed is False
        assert result.error_code in ("PERMISSION_DENIED", "SKILL_NOT_IN_CONTEXT")

    @pytest.mark.asyncio
    async def test_intercept_no_deps(
        self,
        interceptor_no_deps: PermissionInterceptor,
        action_request_allowed: ActionRequest,
    ) -> None:
        """Test interception without graph store or session manager."""
        result = await interceptor_no_deps.intercept(
            action_request_allowed, "sess_001",
        )
        # Without deps, context check defaults to True
        # But permission check depends on whether permissions were found
        # (none found → action_matched=False → but empty perms → validation passes)
        # This should be allowed by default
        assert result.allowed is True


class TestGetSkillPermissions:
    """Skill permissions retrieval tests."""

    @pytest.mark.asyncio
    async def test_get_permissions_from_store(
        self,
        interceptor: PermissionInterceptor,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test getting permissions from graph store."""
        perms = await interceptor._get_skill_permissions("git:commit")
        assert len(perms) == 2
        assert perms[0].resource_type == "fs"

    @pytest.mark.asyncio
    async def test_get_permissions_no_store(self, interceptor_no_deps: PermissionInterceptor) -> None:
        """Test getting permissions without graph store returns empty."""
        perms = await interceptor_no_deps._get_skill_permissions("git:commit")
        assert perms == []

    @pytest.mark.asyncio
    async def test_get_permissions_unknown_skill(
        self,
        interceptor: PermissionInterceptor,
        mock_graph_store: MagicMock,
    ) -> None:
        """Test getting permissions for unknown skill."""
        mock_graph_store.get_node = AsyncMock(return_value=None)
        perms = await interceptor._get_skill_permissions("unknown:skill")
        assert perms == []
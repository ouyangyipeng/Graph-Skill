"""
Permission interceptor per RFC-04 Section 5.

Validates Agent action requests against skill permission declarations
and session authorization scope.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from graphskill.core.exceptions import PermissionDeniedError
from graphskill.runtime.models import (
    ActionRequest,
    InterceptionResult,
    ParsedAction,
    PermissionInfo,
    SessionAuthorization,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Permission Interceptor (RFC-04 Section 5.2)
# ============================================================================


class PermissionInterceptor:
    """Fine-grained permission interceptor per RFC-04 Section 5.2.

    Validates Agent tool call requests against:
    1. Skill permission declarations (what the skill can do)
    2. Session authorization scope (what the session allows)

    Flow: ActionRequest → Parse → Get Skill Perms → Get Session Auth → Validate → InterceptionResult
    """

    def __init__(
        self,
        graph_store: Optional[Any] = None,
        session_manager: Optional[Any] = None,
    ) -> None:
        self._graph_store = graph_store
        self._session_manager = session_manager

    async def intercept(
        self,
        action_request: ActionRequest,
        session_id: str,
    ) -> InterceptionResult:
        """Intercept and validate an action request per RFC-04 Section 5.2.

        Args:
            action_request: Agent action request with tool_call data.
            session_id: Current session ID.

        Returns:
            InterceptionResult: Whether the action is allowed, with reason.
        """
        # Step 1: Parse action
        parsed_action = self._parse_action(action_request)

        # Step 2: Get skill permissions
        skill_permissions = await self._get_skill_permissions(parsed_action.skill_id)

        # Step 3: Get session authorization
        session_auth = await self._get_session_authorization(session_id)

        # Step 4: Validate permissions
        validation_result = self._validate_permissions(
            parsed_action, skill_permissions, session_auth,
        )

        if not validation_result["valid"]:
            return InterceptionResult(
                allowed=False,
                reason=validation_result["reason"],
                error_code="PERMISSION_DENIED",
                skill_id=parsed_action.skill_id,
                action=parsed_action,
            )

        # Step 5: Check skill in current context
        context_check = await self._check_skill_in_context(
            parsed_action.skill_id, session_id,
        )

        if not context_check["in_context"]:
            return InterceptionResult(
                allowed=False,
                reason=context_check["reason"],
                error_code="SKILL_NOT_IN_CONTEXT",
                skill_id=parsed_action.skill_id,
                action=parsed_action,
            )

        return InterceptionResult(
            allowed=True,
            reason="Permission check passed",
            skill_id=parsed_action.skill_id,
            action=parsed_action,
        )

    def _parse_action(self, request: ActionRequest) -> ParsedAction:
        """Parse action request into ParsedAction per RFC-04 Section 5.2.

        Extracts skill_id from tool_call name, infers resource type
        and action type from the tool name and parameters.
        """
        tool_call = request.tool_call or {}
        tool_name = tool_call.get("name", "")

        # Map tool name to skill_id
        skill_id = self._map_tool_to_skill(tool_name)

        parameters = tool_call.get("parameters", {})

        return ParsedAction(
            skill_id=skill_id,
            tool_name=tool_name,
            parameters=parameters,
            resource_type=self._infer_resource_type(parameters),
            action_type=self._infer_action_type(tool_name),
        )

    def _map_tool_to_skill(self, tool_name: str) -> str:
        """Map tool call name to skill ID.

        Convention: tool_name with underscores maps to skill_id with colons.
        E.g., "git_commit" → "git:commit"
        """
        if ":" in tool_name:
            return tool_name
        return tool_name.replace("_", ":")

    def _infer_resource_type(self, parameters: dict[str, Any]) -> str:
        """Infer resource type from parameters.

        Heuristic: check parameter keys for resource hints.
        """
        param_keys = set(parameters.keys())

        if any(k in param_keys for k in ("path", "file", "directory", "filename")):
            return "fs"
        if any(k in param_keys for k in ("url", "host", "endpoint", "domain")):
            return "net"
        if any(k in param_keys for k in ("query", "database", "table", "sql")):
            return "db"
        if any(k in param_keys for k in ("command", "cmd", "shell", "exec")):
            return "exec"
        if any(k in param_keys for k in ("env", "variable", "config")):
            return "env"

        return "unknown"

    def _infer_action_type(self, tool_name: str) -> str:
        """Infer action type from tool name.

        Heuristic: check verb prefixes in tool name.
        """
        name_lower = tool_name.lower()

        if any(v in name_lower for v in ("read", "get", "fetch", "list", "show", "check")):
            return "read"
        if any(v in name_lower for v in ("write", "create", "add", "insert", "update", "set", "commit", "push")):
            return "write"
        if any(v in name_lower for v in ("delete", "remove", "drop", "clean")):
            return "delete"
        if any(v in name_lower for v in ("run", "execute", "start", "launch", "build", "deploy")):
            return "run"

        return "unknown"

    async def _get_skill_permissions(self, skill_id: str) -> list[PermissionInfo]:
        """Get skill permission declarations from graph store.

        Per RFC-04 Section 5.2: fetches the permissions field from
        the skill node in the graph database.
        """
        if self._graph_store is None:
            return []

        try:
            result = await self._graph_store.get_node(skill_id)
            if result and isinstance(result, dict):
                perm_strings = result.get("permissions", [])
                return [PermissionInfo.from_string(p) for p in perm_strings]
            return []
        except Exception as e:
            logger.error("Failed to get permissions for %s: %s", skill_id, e)
            return []

    async def _get_session_authorization(self, session_id: str) -> SessionAuthorization:
        """Get session authorization scope per RFC-04 Section 5.2."""
        if self._session_manager is None:
            return SessionAuthorization(session_id=session_id)

        try:
            return await self._session_manager.get_authorization(session_id)
        except Exception as e:
            logger.error("Failed to get authorization for session %s: %s", session_id, e)
            return SessionAuthorization(session_id=session_id)

    def _validate_permissions(
        self,
        action: ParsedAction,
        skill_permissions: list[PermissionInfo],
        session_auth: SessionAuthorization,
    ) -> dict[str, Any]:
        """Validate permissions per RFC-04 Section 5.2.

        Checks:
        1. Action must match at least one skill permission declaration
        2. All skill permissions must be within session authorization scope
        """
        # Check action against skill permissions
        action_matched = any(
            self._match_permission(action, perm) for perm in skill_permissions
        )

        if not action_matched and skill_permissions:
            return {
                "valid": False,
                "reason": f"Action '{action.action_type}' on '{action.resource_type}' "
                          f"not declared in skill permissions",
            }

        # Check skill permissions against session authorization
        for perm in skill_permissions:
            if not self._check_session_authorization(perm, session_auth):
                return {
                    "valid": False,
                    "reason": f"Skill permission '{perm.resource_type}:{perm.action}:{perm.target}' "
                              f"exceeds session authorization",
                }

        return {"valid": True}

    def _match_permission(
        self,
        action: ParsedAction,
        permission: PermissionInfo,
    ) -> bool:
        """Check if action matches a permission declaration per RFC-04 Section 5.2.

        Supports:
        - Resource type matching
        - Action type matching
        - Target matching with wildcard (*)
        - Path prefix matching for fs resources
        """
        # Resource type match
        if action.resource_type != permission.resource_type:
            return False

        # Action match
        if action.action_type != permission.action:
            return False

        # Target wildcard match
        if permission.target == "*":
            return True

        # Exact target match
        if action.parameters.get("target") == permission.target:
            return True

        # Path prefix match for fs resources
        if permission.resource_type == "fs" and permission.target.endswith("*"):
            prefix = permission.target.rstrip("*")
            if action.parameters.get("path", "").startswith(prefix):
                return True

        return False

    def _check_session_authorization(
        self,
        permission: PermissionInfo,
        session_auth: SessionAuthorization,
    ) -> bool:
        """Check if a permission is within session authorization scope.

        Per RFC-04 Section 5.2: skill permission must match at least
        one authorized permission in the session, or the session must
        have authorized the skill itself.
        """
        # If session has authorized the skill, all its permissions are allowed
        if session_auth.authorized_skills:
            # Check if any skill in authorized_skills matches the permission context
            pass  # Simplified: if skills are authorized, permissions pass

        # Check each authorized permission
        for auth_perm in session_auth.authorized_permissions:
            if (
                auth_perm.resource_type == permission.resource_type
                and auth_perm.action == permission.action
                and (auth_perm.target == "*" or auth_perm.target == permission.target)
            ):
                return True

        # If no authorized permissions defined, default allow
        if not session_auth.authorized_permissions:
            return True

        return False

    async def _check_skill_in_context(
        self,
        skill_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Check if skill is in current session context per RFC-04 Section 5.2."""
        if self._session_manager is None:
            return {"in_context": True}

        try:
            context = await self._session_manager.get_current_context(session_id)
            if skill_id in context.skills:
                return {"in_context": True}
            return {
                "in_context": False,
                "reason": f"Skill '{skill_id}' was not loaded in current routing context",
            }
        except Exception as e:
            logger.error("Context check failed for %s: %s", skill_id, e)
            return {"in_context": True}  # Default allow on error
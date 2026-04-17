"""GraphSkill runtime integration layer for Agent frameworks.

Per RFC-04: provides context injection middleware, permission interceptor,
session manager, and runtime data models.
"""

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
from graphskill.runtime.injection import ContextInjectionMiddleware
from graphskill.runtime.permission import PermissionInterceptor
from graphskill.runtime.session import SessionManager

__all__ = [
    # Models
    "ActionRequest",
    "AgentPrompt",
    "AgentSession",
    "ExecutionState",
    "InjectionConfig",
    "InjectedPrompt",
    "InterceptionResult",
    "ParsedAction",
    "PermissionInfo",
    "SessionAuthorization",
    "SessionConfig",
    "SessionContext",
    # Middleware
    "ContextInjectionMiddleware",
    "PermissionInterceptor",
    "SessionManager",
]
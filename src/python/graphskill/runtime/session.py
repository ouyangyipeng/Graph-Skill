"""
Session manager per RFC-04 Section 6.

Manages Agent session lifecycle: creation, context updates,
skill call recording, authorization, and termination.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from graphskill.runtime.models import (
    AgentSession,
    SessionAuthorization,
    SessionConfig,
    SessionContext,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Session Manager (RFC-04 Section 6.2)
# ============================================================================


class SessionManager:
    """Session manager per RFC-04 Section 6.2.

    Manages Agent session lifecycle with Redis-backed persistence.
    Supports context updates, skill call recording, and authorization.

    Per RFC-04 Section 6.1: sessions have a 24-hour TTL by default.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        config: Optional[SessionConfig] = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or SessionConfig()

    async def create_session(
        self,
        agent_id: str,
        authorization: Optional[SessionAuthorization] = None,
    ) -> AgentSession:
        """Create a new session per RFC-04 Section 6.2.

        Args:
            agent_id: Agent instance ID.
            authorization: Initial session authorization scope.

        Returns:
            AgentSession: Newly created session.
        """
        session = AgentSession(
            agent_id=agent_id,
            current_context=SessionContext(
                skills=[],
                routing_mode="none",
                token_count=0,
            ),
            authorization=authorization or SessionAuthorization(),
        )

        await self._store_session(session)
        logger.info("Created session %s for agent %s", session.session_id, agent_id)

        return session

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get session by ID per RFC-04 Section 6.2.

        Args:
            session_id: Session identifier.

        Returns:
            Optional[AgentSession]: Session if found, None otherwise.
        """
        if self._redis is None:
            return None

        try:
            session_data = await self._redis.get(f"session:{session_id}")
            if session_data:
                return AgentSession.from_json(session_data)
            return None
        except Exception as e:
            logger.error("Failed to get session %s: %s", session_id, e)
            return None

    async def update_context(
        self,
        session_id: str,
        new_context: SessionContext,
    ) -> Optional[AgentSession]:
        """Update session context per RFC-04 Section 6.2.

        Records context change history before updating.

        Args:
            session_id: Session identifier.
            new_context: New skill context.

        Returns:
            Optional[AgentSession]: Updated session, None if not found.
        """
        session = await self.get_session(session_id)
        if session is None:
            logger.warning("Session %s not found for context update", session_id)
            return None

        # Record history before update
        from datetime import datetime
        session.context_history.append({
            "previous_context": session.current_context.to_dict(),
            "new_context": new_context.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Trim history if exceeding max
        if len(session.context_history) > self._config.max_context_history:
            session.context_history = session.context_history[-self._config.max_context_history:]

        # Update context
        session.current_context = new_context

        await self._store_session(session)
        return session

    async def record_skill_call(
        self,
        session_id: str,
        skill_call: dict[str, Any],
    ) -> None:
        """Record skill call in session per RFC-04 Section 6.2.

        Args:
            session_id: Session identifier.
            skill_call: Skill call record with skill_id, action, status.
        """
        session = await self.get_session(session_id)
        if session is None:
            return

        from datetime import datetime
        session.skill_call_history.append({
            "skill_id": skill_call.get("skill_id", ""),
            "action": skill_call.get("action", ""),
            "status": skill_call.get("status", ""),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Trim history if exceeding max
        if len(session.skill_call_history) > self._config.max_skill_call_history:
            session.skill_call_history = session.skill_call_history[-self._config.max_skill_call_history:]

        await self._store_session(session)

    async def get_authorization(self, session_id: str) -> SessionAuthorization:
        """Get session authorization scope per RFC-04 Section 5.2.

        Args:
            session_id: Session identifier.

        Returns:
            SessionAuthorization: Authorization scope (empty if session not found).
        """
        session = await self.get_session(session_id)
        if session:
            return session.authorization
        return SessionAuthorization(session_id=session_id)

    async def get_current_context(self, session_id: str) -> SessionContext:
        """Get current session context per RFC-04 Section 6.2.

        Args:
            session_id: Session identifier.

        Returns:
            SessionContext: Current context (empty if session not found).
        """
        session = await self.get_session(session_id)
        if session:
            return session.current_context
        return SessionContext()

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate session per RFC-04 Section 6.2.

        Args:
            session_id: Session identifier.

        Returns:
            bool: True if terminated successfully.
        """
        if self._redis is None:
            return False

        try:
            await self._redis.delete(f"session:{session_id}")
            logger.info("Terminated session %s", session_id)
            return True
        except Exception as e:
            logger.error("Failed to terminate session %s: %s", session_id, e)
            return False

    async def _store_session(self, session: AgentSession) -> None:
        """Store session to Redis per RFC-04 Section 6.2."""
        if self._redis is None:
            return

        try:
            key = f"session:{session.session_id}"
            value = session.to_json()
            ttl = self._config.session_ttl
            await self._redis.set_ttl(key, ttl)
            await self._redis.set(key, value)
        except Exception as e:
            logger.error("Failed to store session %s: %s", session.session_id, e)

    @property
    def config(self) -> SessionConfig:
        """Return session configuration."""
        return self._config
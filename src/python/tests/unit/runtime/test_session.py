"""
Session manager unit tests per RFC-04 Section 6.

Tests SessionManager: create, get, update context, record skill call,
get authorization, terminate, and edge cases.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from graphskill.runtime.models import (
    AgentSession,
    SessionAuthorization,
    SessionConfig,
    SessionContext,
)
from graphskill.runtime.session import SessionManager


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.set_ttl = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def session_config() -> SessionConfig:
    """Default session config."""
    return SessionConfig(session_ttl=86400)


@pytest.fixture
def session_manager(
    mock_redis: MagicMock,
    session_config: SessionConfig,
) -> SessionManager:
    """Create session manager with mock Redis."""
    return SessionManager(
        redis_client=mock_redis,
        config=session_config,
    )


@pytest.fixture
def session_manager_no_redis() -> SessionManager:
    """Create session manager without Redis."""
    return SessionManager()


@pytest.fixture
def sample_session() -> AgentSession:
    """Create a sample session for testing."""
    return AgentSession(
        agent_id="agent_001",
        current_context=SessionContext(
            skills=["git:commit", "git:push"],
            routing_mode="normal",
            token_count=2000,
        ),
        authorization=SessionAuthorization(
            session_id="sess_manual",
            authorized_skills=["git:commit", "git:push"],
        ),
    )


# ============================================================================
# Create Session Tests
# ============================================================================


class TestSessionCreate:
    """Session creation tests per RFC-04 Section 6.2."""

    @pytest.mark.asyncio
    async def test_create_session(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test creating a new session."""
        session = await session_manager.create_session("agent_001")
        assert session.session_id.startswith("sess_")
        assert session.agent_id == "agent_001"
        assert session.current_context.skills == []
        assert session.current_context.routing_mode == "none"
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_create_session_with_authorization(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test creating session with initial authorization."""
        auth = SessionAuthorization(
            authorized_skills=["git:commit"],
            authorized_permissions=[],
        )
        session = await session_manager.create_session("agent_002", auth)
        assert session.authorization.authorized_skills == ["git:commit"]

    @pytest.mark.asyncio
    async def test_create_session_no_redis(self, session_manager_no_redis: SessionManager) -> None:
        """Test creating session without Redis (in-memory only)."""
        session = await session_manager_no_redis.create_session("agent_no_redis")
        assert session.session_id.startswith("sess_")
        assert session.agent_id == "agent_no_redis"


# ============================================================================
# Get Session Tests
# ============================================================================


class TestSessionGet:
    """Session retrieval tests."""

    @pytest.mark.asyncio
    async def test_get_existing_session(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
        sample_session: AgentSession,
    ) -> None:
        """Test getting an existing session."""
        mock_redis.get.return_value = sample_session.to_json()
        session = await session_manager.get_session(sample_session.session_id)
        assert session is not None
        assert session.agent_id == "agent_001"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test getting a nonexistent session returns None."""
        mock_redis.get.return_value = None
        session = await session_manager.get_session("sess_nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_get_session_no_redis(self, session_manager_no_redis: SessionManager) -> None:
        """Test getting session without Redis returns None."""
        session = await session_manager_no_redis.get_session("sess_any")
        assert session is None


# ============================================================================
# Update Context Tests
# ============================================================================


class TestSessionUpdateContext:
    """Session context update tests per RFC-04 Section 6.2."""

    @pytest.mark.asyncio
    async def test_update_context(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
        sample_session: AgentSession,
    ) -> None:
        """Test updating session context with history recording."""
        mock_redis.get.return_value = sample_session.to_json()
        new_context = SessionContext(
            skills=["git:commit", "git:push", "git:diff"],
            routing_mode="dynamic",
            token_count=3000,
        )
        updated = await session_manager.update_context(
            sample_session.session_id, new_context,
        )
        assert updated is not None
        assert updated.current_context.skills == ["git:commit", "git:push", "git:diff"]
        # History should be recorded
        assert len(updated.context_history) == 1

    @pytest.mark.asyncio
    async def test_update_context_nonexistent(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test updating nonexistent session returns None."""
        mock_redis.get.return_value = None
        result = await session_manager.update_context("sess_none", SessionContext())
        assert result is None

    @pytest.mark.asyncio
    async def test_context_history_trimmed(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test context history is trimmed when exceeding max."""
        config = SessionConfig(max_context_history=2)
        manager = SessionManager(redis_client=mock_redis, config=config)

        session = AgentSession(
            agent_id="agent_trim",
            context_history=[{"old": 1}, {"old": 2}],
        )
        mock_redis.get.return_value = session.to_json()

        new_ctx = SessionContext(skills=["new_skill"])
        updated = await manager.update_context(session.session_id, new_ctx)
        # After trim: should have at most 2 entries (old_2 + new)
        assert len(updated.context_history) <= 2


# ============================================================================
# Record Skill Call Tests
# ============================================================================


class TestRecordSkillCall:
    """Skill call recording tests."""

    @pytest.mark.asyncio
    async def test_record_skill_call(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
        sample_session: AgentSession,
    ) -> None:
        """Test recording a skill call in session."""
        mock_redis.get.return_value = sample_session.to_json()
        await session_manager.record_skill_call(
            sample_session.session_id,
            {"skill_id": "git:commit", "action": "execute", "status": "success"},
        )
        # Session should be stored with the new call
        assert mock_redis.set.call_count >= 1

    @pytest.mark.asyncio
    async def test_record_skill_call_nonexistent(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test recording skill call for nonexistent session does nothing."""
        mock_redis.get.return_value = None
        await session_manager.record_skill_call("sess_none", {"skill_id": "test"})
        # Should not crash


# ============================================================================
# Get Authorization Tests
# ============================================================================


class TestGetAuthorization:
    """Authorization retrieval tests."""

    @pytest.mark.asyncio
    async def test_get_authorization_existing(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
        sample_session: AgentSession,
    ) -> None:
        """Test getting authorization for existing session."""
        mock_redis.get.return_value = sample_session.to_json()
        auth = await session_manager.get_authorization(sample_session.session_id)
        assert auth.authorized_skills == ["git:commit", "git:push"]

    @pytest.mark.asyncio
    async def test_get_authorization_nonexistent(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test getting authorization for nonexistent session returns empty."""
        mock_redis.get.return_value = None
        auth = await session_manager.get_authorization("sess_none")
        assert auth.session_id == "sess_none"
        assert auth.authorized_permissions == []


# ============================================================================
# Get Current Context Tests
# ============================================================================


class TestGetCurrentContext:
    """Current context retrieval tests."""

    @pytest.mark.asyncio
    async def test_get_context_existing(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
        sample_session: AgentSession,
    ) -> None:
        """Test getting context for existing session."""
        mock_redis.get.return_value = sample_session.to_json()
        ctx = await session_manager.get_current_context(sample_session.session_id)
        assert ctx.skills == ["git:commit", "git:push"]

    @pytest.mark.asyncio
    async def test_get_context_nonexistent(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test getting context for nonexistent session returns empty."""
        mock_redis.get.return_value = None
        ctx = await session_manager.get_current_context("sess_none")
        assert ctx.skills == []


# ============================================================================
# Terminate Session Tests
# ============================================================================


class TestSessionTerminate:
    """Session termination tests."""

    @pytest.mark.asyncio
    async def test_terminate_session(
        self,
        session_manager: SessionManager,
        mock_redis: MagicMock,
    ) -> None:
        """Test terminating a session."""
        result = await session_manager.terminate_session("sess_001")
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_no_redis(self, session_manager_no_redis: SessionManager) -> None:
        """Test terminating without Redis returns False."""
        result = await session_manager_no_redis.terminate_session("sess_001")
        assert result is False


# ============================================================================
# Config Tests
# ============================================================================


class TestSessionManagerConfig:
    """Session manager configuration tests."""

    def test_config_accessible(
        self,
        session_manager: SessionManager,
        session_config: SessionConfig,
    ) -> None:
        """Test config property."""
        assert session_manager.config.session_ttl == session_config.session_ttl
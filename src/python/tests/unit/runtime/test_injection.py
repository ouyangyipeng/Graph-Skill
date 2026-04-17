"""
Context injection middleware unit tests per RFC-04 Section 3.

Tests ContextInjectionMiddleware: inject, position logic, token estimation.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from graphskill.runtime.models import (
    AgentPrompt,
    InjectionConfig,
    InjectedPrompt,
)
from graphskill.runtime.injection import ContextInjectionMiddleware


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_config() -> InjectionConfig:
    """Default injection config."""
    return InjectionConfig(position="after_system")


@pytest.fixture
def before_query_config() -> InjectionConfig:
    """Config with before_query position."""
    return InjectionConfig(position="before_query")


@pytest.fixture
def mock_gateway() -> MagicMock:
    """Create mock routing gateway."""
    gateway = MagicMock()
    response = MagicMock()
    response.metadata = {"assembled_context": "<Skills><Skill id='git:commit'/></Skills>"}
    response.request_id = "req_001"
    gateway.route = AsyncMock(return_value=response)
    return gateway


@pytest.fixture
def middleware(mock_gateway: MagicMock, default_config: InjectionConfig) -> ContextInjectionMiddleware:
    """Create middleware with mock gateway and default config."""
    return ContextInjectionMiddleware(
        routing_gateway=mock_gateway,
        config=default_config,
    )


@pytest.fixture
def middleware_before_query(
    mock_gateway: MagicMock,
    before_query_config: InjectionConfig,
) -> ContextInjectionMiddleware:
    """Create middleware with before_query config."""
    return ContextInjectionMiddleware(
        routing_gateway=mock_gateway,
        config=before_query_config,
    )


@pytest.fixture
def middleware_no_gateway(default_config: InjectionConfig) -> ContextInjectionMiddleware:
    """Create middleware without gateway."""
    return ContextInjectionMiddleware(config=default_config)


@pytest.fixture
def agent_prompt() -> AgentPrompt:
    """Create a sample Agent prompt."""
    return AgentPrompt(
        system_prompt="You are an AI assistant",
        user_query="Please help me commit code",
        conversation_history="Previous messages here",
    )


# ============================================================================
# Injection Tests
# ============================================================================


class TestContextInjectionMiddleware:
    """ContextInjectionMiddleware tests per RFC-04 Section 3.4."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        mw = ContextInjectionMiddleware()
        assert mw._routing_gateway is None
        assert mw._config.position == "after_system"

    def test_init_with_gateway_and_config(
        self,
        mock_gateway: MagicMock,
        default_config: InjectionConfig,
    ) -> None:
        """Test initialization with gateway and config."""
        mw = ContextInjectionMiddleware(
            routing_gateway=mock_gateway,
            config=default_config,
        )
        assert mw._routing_gateway == mock_gateway
        assert mw.config.position == "after_system"

    @pytest.mark.asyncio
    async def test_inject_with_gateway(
        self,
        middleware: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
        mock_gateway: MagicMock,
    ) -> None:
        """Test injection via routing gateway."""
        result = await middleware.inject(
            agent_prompt=agent_prompt,
            query="commit code",
            context_state={},
            max_tokens=8000,
        )
        assert result.injected_context != ""
        assert result.final_prompt != ""
        assert result.routing_result_id == "req_001"
        mock_gateway.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_inject_without_gateway(
        self,
        middleware_no_gateway: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
    ) -> None:
        """Test injection without gateway (empty context)."""
        result = await middleware_no_gateway.inject(
            agent_prompt=agent_prompt,
            query="commit code",
            context_state={},
            max_tokens=8000,
        )
        assert result.injected_context == ""
        # Final prompt should still contain original content
        assert "You are an AI assistant" in result.final_prompt

    @pytest.mark.asyncio
    async def test_inject_with_pre_assembled_context(
        self,
        middleware: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
        mock_gateway: MagicMock,
    ) -> None:
        """Test injection with pre-assembled skills context (skip routing)."""
        skills_ctx = "<Skills><Skill id='test'/></Skills>"
        result = await middleware.inject(
            agent_prompt=agent_prompt,
            query="test query",
            context_state={},
            max_tokens=8000,
            skills_context=skills_ctx,
        )
        assert result.injected_context == skills_ctx
        # Gateway should NOT be called
        mock_gateway.route.assert_not_called()


class TestInjectionPosition:
    """Injection position logic tests per RFC-04 Section 3.3."""

    def test_after_system_position(
        self,
        middleware: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
    ) -> None:
        """Test after_system position: System → Context → History → Query."""
        context = "<Skills>context</Skills>"
        result = middleware._inject_at_position(
            agent_prompt, context, "after_system",
        )
        # System should come before context
        sys_idx = result.index("You are an AI assistant")
        ctx_idx = result.index("<Skills>context</Skills>")
        query_idx = result.index("Please help me commit code")
        assert sys_idx < ctx_idx < query_idx

    def test_before_query_position(
        self,
        middleware_before_query: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
    ) -> None:
        """Test before_query position: System → History → Context → Query."""
        context = "<Skills>context</Skills>"
        result = middleware_before_query._inject_at_position(
            agent_prompt, context, "before_query",
        )
        sys_idx = result.index("You are an AI assistant")
        ctx_idx = result.index("<Skills>context</Skills>")
        query_idx = result.index("Please help me commit code")
        assert sys_idx < ctx_idx < query_idx

    def test_custom_position_default_after_system(
        self,
        middleware: ContextInjectionMiddleware,
        agent_prompt: AgentPrompt,
    ) -> None:
        """Test custom position falls back to after_system."""
        context = "<Skills>context</Skills>"
        result = middleware._inject_at_position(
            agent_prompt, context, "custom",
        )
        # Should still have system before context
        assert "You are an AI assistant" in result
        assert "<Skills>context</Skills>" in result

    def test_empty_parts_filtered(
        self,
        middleware: ContextInjectionMiddleware,
    ) -> None:
        """Test empty prompt parts are filtered out."""
        prompt = AgentPrompt(system_prompt="sys", user_query="", conversation_history="")
        context = "skills"
        result = middleware._inject_at_position(prompt, context, "after_system")
        assert result == "sys\n\nskills"


class TestTokenEstimation:
    """Token estimation tests."""

    def test_estimate_base_tokens(self, middleware: ContextInjectionMiddleware) -> None:
        """Test base token estimation."""
        prompt = AgentPrompt(
            system_prompt="This is a system prompt with some text",
            user_query="Short query",
        )
        tokens = middleware._estimate_base_tokens(prompt)
        assert tokens > 0

    def test_estimate_tokens(self, middleware: ContextInjectionMiddleware) -> None:
        """Test token estimation for text."""
        text = "Hello world this is a test"
        tokens = middleware._estimate_tokens(text)
        assert tokens > 0

    def test_estimate_tokens_empty(self, middleware: ContextInjectionMiddleware) -> None:
        """Test token estimation for empty text."""
        assert middleware._estimate_tokens("") == 0
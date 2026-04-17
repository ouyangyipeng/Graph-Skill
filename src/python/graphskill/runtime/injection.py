"""
Context injection middleware per RFC-04 Section 3.

Injects skill context into Agent prompts at configurable positions,
managing token budgets and supporting multiple output formats.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from graphskill.runtime.models import (
    AgentPrompt,
    InjectionConfig,
    InjectedPrompt,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Context Injection Middleware (RFC-04 Section 3.4)
# ============================================================================


class ContextInjectionMiddleware:
    """Skill context injection middleware per RFC-04 Section 3.4.

    Injects routing results into Agent prompts at configurable positions,
    managing token budgets and supporting XML/JSON/markdown formats.

    Flow: AgentPrompt → RoutingGateway → ContextAssembly → Injection → InjectedPrompt
    """

    def __init__(
        self,
        routing_gateway: Optional[Any] = None,
        config: Optional[InjectionConfig] = None,
    ) -> None:
        self._routing_gateway = routing_gateway
        self._config = config or InjectionConfig()

    async def inject(
        self,
        agent_prompt: AgentPrompt,
        query: str,
        context_state: dict[str, Any],
        max_tokens: int,
        skills_context: Optional[str] = None,
    ) -> InjectedPrompt:
        """Execute skill context injection per RFC-04 Section 3.4.

        Args:
            agent_prompt: Original Agent prompt structure.
            query: User query string.
            context_state: Current context state.
            max_tokens: Token budget for injection.
            skills_context: Pre-assembled skills context (skip routing if provided).

        Returns:
            InjectedPrompt: Result containing original, injected context, and final prompt.
        """
        # Step 1: Obtain skills context (route or use provided)
        if skills_context is None and self._routing_gateway is not None:
            routing_result = await self._routing_gateway.route(
                query=query,
                context=context_state,
                max_tokens=max_tokens - self._estimate_base_tokens(agent_prompt),
            )
            skills_context = routing_result.metadata.get("assembled_context", "")
            routing_result_id = str(routing_result.request_id)
        elif skills_context is None:
            skills_context = ""
            routing_result_id = ""
        else:
            routing_result_id = ""

        # Step 2: Inject at configured position
        final_prompt = self._inject_at_position(
            agent_prompt,
            skills_context,
            self._config.position,
        )

        # Step 3: Estimate token count
        token_count = self._estimate_tokens(final_prompt)

        return InjectedPrompt(
            original_prompt=agent_prompt,
            injected_context=skills_context,
            final_prompt=final_prompt,
            routing_result_id=routing_result_id,
            token_count=token_count,
            injection_position=self._config.position,
        )

    def _inject_at_position(
        self,
        prompt: AgentPrompt,
        context: str,
        position: str,
    ) -> str:
        """Inject context at the specified position per RFC-04 Section 3.3.

        Args:
            prompt: Original prompt structure.
            context: Assembled skills context text.
            position: Injection position (after_system, before_query, custom).

        Returns:
            str: Final assembled prompt text.
        """
        parts: list[str] = []

        if position == "after_system":
            # System → Context → History → Query
            parts.append(prompt.system_prompt)
            parts.append(context)
            parts.append(prompt.conversation_history)
            parts.append(prompt.user_query)
        elif position == "before_query":
            # System → History → Context → Query
            parts.append(prompt.system_prompt)
            parts.append(prompt.conversation_history)
            parts.append(context)
            parts.append(prompt.user_query)
        else:
            # Default: after_system
            parts.append(prompt.system_prompt)
            parts.append(context)
            parts.append(prompt.conversation_history)
            parts.append(prompt.user_query)

        # Filter empty parts and join with double newline
        return "\n\n".join(p for p in parts if p)

    def _estimate_base_tokens(self, prompt: AgentPrompt) -> int:
        """Estimate base prompt token count (without injected context).

        Uses simple heuristic: ~4 chars per token for English text.
        """
        base_text = f"{prompt.system_prompt}\n\n{prompt.user_query}"
        return len(base_text) // 4

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for assembled text.

        Uses simple heuristic: ~4 chars per token.
        """
        return len(text) // 4 if text else 0

    @property
    def config(self) -> InjectionConfig:
        """Return injection configuration."""
        return self._config
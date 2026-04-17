"""
Query processor for noise reduction and context enrichment.

Implements RFC-03 Section 3.3: Query 降噪处理.
Pipeline: clean_text → enrich_with_context → extract_intent_keywords → filter_previous_skills
"""

from __future__ import annotations

import re
import logging
from typing import Any

from graphskill.routing.models import ProcessedQuery

logger = logging.getLogger(__name__)

# Intent keyword mapping for category detection
_INTENT_PATTERNS: dict[str, list[str]] = {
    "git": ["git", "commit", "push", "pull", "branch", "merge", "clone", "checkout", "rebase"],
    "database": ["database", "query", "sql", "table", "insert", "update", "delete", "select", "postgres", "mysql"],
    "file": ["file", "read", "write", "delete", "copy", "move", "directory", "path", "folder"],
    "network": ["http", "api", "request", "fetch", "download", "upload", "url", "endpoint"],
    "docker": ["docker", "container", "image", "compose", "volume", "build"],
    "test": ["test", "pytest", "unittest", "coverage", "assert", "mock"],
    "deploy": ["deploy", "kubernetes", "k8s", "helm", "service", "ingress"],
}


class QueryProcessor:
    """Query processor implementing RFC-03 Section 3.3.

    Performs text cleaning, context enrichment, intent extraction,
    and previous-skill filtering on raw user queries.
    """

    def process(self, raw_query: str, context_state: dict[str, Any] | None = None) -> ProcessedQuery:
        """Process a raw query through the full noise-reduction pipeline.

        Args:
            raw_query: Original user query text.
            context_state: Runtime context (environment, previous_skills, etc.).

        Returns:
            ProcessedQuery with cleaned, enriched text and metadata.
        """
        if context_state is None:
            context_state = {}

        # Step 1: Text cleaning
        cleaned_query = self._clean_text(raw_query)

        # Step 2: Context enrichment
        enriched_query = self._enrich_with_context(cleaned_query, context_state)

        # Step 3: Intent keyword extraction
        intent_keywords = self._extract_intent_keywords(enriched_query)

        # Step 4: Previous-skill filtering (metadata only, does not alter text)
        previous_skills = context_state.get("previous_skills", [])

        return ProcessedQuery(
            original=raw_query,
            cleaned=cleaned_query,
            enriched=enriched_query,
            intent_keywords=intent_keywords,
            previous_skills=previous_skills,
            environment=context_state.get("environment", {}),
        )

    def _clean_text(self, text: str) -> str:
        """Clean text: normalize whitespace, remove noise, lowercase.

        Per RFC-03:
        - Remove excess whitespace
        - Remove special characters (keep CJK, ASCII alphanum)
        - Lowercase English portions
        """
        # Remove excess whitespace
        text = re.sub(r"\s+", " ", text.strip())

        # Remove special characters but keep CJK, ASCII word chars, spaces
        text = re.sub(r"[^\w\s\u4e00-\u9fff]", "", text)

        # Lowercase
        text = text.lower()

        return text

    def _enrich_with_context(self, query: str, context: dict[str, Any]) -> str:
        """Enrich query with environment context keywords.

        Appends detected environment signals (e.g. git_repo, database_connected)
        to the query to improve embedding quality.
        """
        environment = context.get("environment", {})

        env_keywords: list[str] = []
        if environment.get("git_repo"):
            env_keywords.append("git repository")
        if environment.get("database_connected"):
            env_keywords.append("database")
        if environment.get("docker_available"):
            env_keywords.append("docker")
        if environment.get("k8s_cluster"):
            env_keywords.append("kubernetes")

        if env_keywords:
            query = f"{query} context: {', '.join(env_keywords)}"

        return query

    def _extract_intent_keywords(self, query: str) -> list[str]:
        """Extract intent category keywords from the query.

        Matches query terms against known intent patterns to identify
        the domain(s) the query belongs to.
        """
        query_lower = query.lower()
        keywords: list[str] = []

        for category, patterns in _INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    keywords.append(category)
                    break  # One match per category is enough

        return keywords

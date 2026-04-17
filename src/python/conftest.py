"""
GraphSkill pytest configuration and fixtures.

This module provides shared fixtures and configuration for all tests.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from uuid import uuid4

from graphskill.core.models import (
    SkillNode,
    SkillEdge,
    EdgeType,
    RoutingRequest,
    RoutingResponse,
    SelectedSkill,
    TelemetryEvent,
)


# ============================================
# Skill Node Fixtures
# ============================================

@pytest.fixture
def sample_skill_node() -> SkillNode:
    """Create a sample skill node for testing."""
    return SkillNode(
        uid="git:commit_changes",
        version="1.0.0",
        intent_description="Execute Git commit operation, committing current working directory changes to the local repository. Requires Git user information to be configured first. Supports adding commit messages.",
        permissions=["fs:read:/tmp", "fs:write:/tmp", "net:http:github.com"],
        execution_success_rate=0.95,
        execution_count=100,
        is_deprecated=False,
        tags=["git", "version-control", "commit"],
        author="test-author",
    )


@pytest.fixture
def sample_skill_node_minimal() -> SkillNode:
    """Create a minimal skill node for testing."""
    return SkillNode(
        uid="fs:read_file",
        version="1.0.0",
        intent_description="Read file content from the specified path. This skill handles various file formats and provides error handling for missing files or permission issues.",
        permissions=["fs:read:/tmp"],
    )


@pytest.fixture
def sample_skill_nodes() -> list[SkillNode]:
    """Create multiple sample skill nodes for testing."""
    return [
        SkillNode(
            uid="git:commit_changes",
            version="1.0.0",
            intent_description="Execute Git commit operation, committing current working directory changes to the local repository. Requires Git user information to be configured first.",
            permissions=["fs:read:/tmp", "fs:write:/tmp"],
            execution_success_rate=0.95,
        ),
        SkillNode(
            uid="git:config_user",
            version="1.0.0",
            intent_description="Configure Git user information including name and email. This is a prerequisite for most Git operations like commit and push.",
            permissions=["fs:read:/tmp", "fs:write:/tmp"],
            execution_success_rate=0.98,
        ),
        SkillNode(
            uid="git:push_remote",
            version="1.0.0",
            intent_description="Push local commits to remote Git repository. Requires network access and proper authentication credentials.",
            permissions=["net:github.com", "net:gitlab.com"],
            execution_success_rate=0.90,
        ),
    ]


# ============================================
# Skill Edge Fixtures
# ============================================

@pytest.fixture
def sample_skill_edge() -> SkillEdge:
    """Create a sample skill edge for testing."""
    return SkillEdge(
        source_uid="git:commit_changes",
        target_uid="git:config_user",
        edge_type=EdgeType.REQUIRES,
        weight=1.0,
        confidence=0.95,
        is_implicit=False,
        discovery_source="manual",
    )


@pytest.fixture
def sample_conflict_edge() -> SkillEdge:
    """Create a sample conflict edge for testing."""
    return SkillEdge(
        source_uid="fs:delete_recursive",
        target_uid="fs:safe_delete",
        edge_type=EdgeType.CONFLICTS_WITH,
        weight=1.0,
        confidence=0.90,
    )


@pytest.fixture
def sample_skill_edges() -> list[SkillEdge]:
    """Create multiple sample skill edges for testing."""
    return [
        SkillEdge(
            source_uid="git:commit_changes",
            target_uid="git:config_user",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
            confidence=1.0,
        ),
        SkillEdge(
            source_uid="git:push_remote",
            target_uid="git:commit_changes",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
            confidence=0.95,
        ),
        SkillEdge(
            source_uid="db:query_mysql",
            target_uid="db:query_postgres",
            edge_type=EdgeType.SUBSTITUTES,
            weight=0.8,
            confidence=0.85,
        ),
    ]


# ============================================
# Routing Request/Response Fixtures
# ============================================

@pytest.fixture
def sample_routing_request() -> RoutingRequest:
    """Create a sample routing request for testing."""
    return RoutingRequest(
        query="I need to commit my changes to the git repository",
        max_tokens=4096,
        tenant_id="default",
        session_id="test-session-123",
    )


@pytest.fixture
def sample_routing_request_with_constraints() -> RoutingRequest:
    """Create a routing request with constraints for testing."""
    from graphskill.core.models import RoutingConstraints
    return RoutingRequest(
        query="I need to query the database",
        constraints=RoutingConstraints(
            required_skills=["db:connect"],
            excluded_skills=["db:delete"],
            min_reliability=0.7,
        ),
        max_tokens=2048,
    )


@pytest.fixture
def sample_selected_skill() -> SelectedSkill:
    """Create a sample selected skill for testing."""
    return SelectedSkill(
        skill_uid="git:commit_changes",
        skill_version="1.0.0",
        intent_description="Execute Git commit operation...",
        permissions=["fs:read:/tmp", "fs:write:/tmp"],
        score=0.85,
        is_required=False,
        dependency_depth=1,
        similarity_score=0.90,
        pagerank_score=0.75,
        reliability_score=0.95,
    )


@pytest.fixture
def sample_routing_response() -> RoutingResponse:
    """Create a sample routing response for testing."""
    return RoutingResponse(
        request_id=uuid4(),
        selected_skills=[
            SelectedSkill(
                skill_uid="git:commit_changes",
                skill_version="1.0.0",
                intent_description="Execute Git commit operation...",
                permissions=["fs:read:/tmp"],
                score=0.85,
            ),
        ],
        total_tokens=500,
        routing_time_ms=150,
        confidence=0.90,
        fallback_used=False,
    )


# ============================================
# Telemetry Event Fixtures
# ============================================

@pytest.fixture
def sample_telemetry_event() -> TelemetryEvent:
    """Create a sample telemetry event for testing."""
    return TelemetryEvent(
        event_type="skill_execution",
        skill_uid="git:commit_changes",
        session_id="test-session-123",
        outcome="success",
        duration_ms=250,
    )


@pytest.fixture
def sample_failure_telemetry_event() -> TelemetryEvent:
    """Create a sample failure telemetry event for testing."""
    return TelemetryEvent(
        event_type="skill_execution",
        skill_uid="git:push_remote",
        session_id="test-session-123",
        outcome="failure",
        duration_ms=5000,
        error_info={
            "error_code": "AUTH_FAILED",
            "error_message": "Authentication credentials not found",
        },
    )


# ============================================
# Test Configuration
# ============================================

@pytest.fixture
def test_config() -> dict:
    """Create test configuration."""
    return {
        "neo4j_uri": "bolt://localhost:7687",
        "neo4j_user": "neo4j",
        "neo4j_password": "test_password",
        "milvus_host": "localhost",
        "milvus_port": 19530,
        "redis_host": "localhost",
        "redis_port": 6379,
        "embedding_dimension": 1536,
        "default_top_k": 10,
        "ewma_alpha": 0.7,
    }


# ============================================
# Pytest Configuration
# ============================================

def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify test collection to add default markers."""
    for item in items:
        # Add unit marker to tests in tests/unit
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        # Add integration marker to tests in tests/integration
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        # Add e2e marker to tests in tests/e2e
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        # Add performance marker to tests in tests/performance
        if "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
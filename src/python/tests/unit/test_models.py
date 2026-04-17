"""
Unit tests for GraphSkill core data structures.

Tests for models defined in graphskill/core/models.py.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import re

from graphskill.core.models import (
    SkillNode,
    SkillEdge,
    EdgeType,
    RoutingRequest,
    RoutingResponse,
    RoutingConstraints,
    SelectedSkill,
    TelemetryEvent,
    SkillManifest,
)


class TestSkillNode:
    """Tests for SkillNode model."""
    
    def test_create_skill_node_minimal(self) -> None:
        """Test creating a minimal skill node."""
        skill = SkillNode(
            uid="git:commit",
            version="1.0.0",
            intent_description="Execute Git commit operation with proper configuration and message handling for version control.",
            permissions=["fs:read:/tmp"],
        )
        
        assert skill.uid == "git:commit"
        assert skill.version == "1.0.0"
        assert skill.execution_success_rate == 1.0  # default
        assert skill.execution_count == 0  # default
        assert skill.is_deprecated is False  # default
    
    def test_create_skill_node_full(self, sample_skill_node: SkillNode) -> None:
        """Test creating a full skill node with all fields."""
        assert sample_skill_node.uid == "git:commit_changes"
        assert sample_skill_node.version == "1.0.0"
        assert sample_skill_node.execution_success_rate == 0.95
        assert sample_skill_node.execution_count == 100
        assert len(sample_skill_node.permissions) == 3
        assert "git" in sample_skill_node.tags
    
    def test_uid_validation_valid(self) -> None:
        """Test valid UID patterns."""
        valid_uids = [
            "git:commit",
            "db:query_postgres",
            "fs:read_file",
            "net:http_request",
            "a:b",  # minimal
            "namespace-123:action-456",
        ]
        for uid in valid_uids:
            skill = SkillNode(
                uid=uid,
                version="1.0.0",
                intent_description="Test skill description that meets minimum length requirement of fifty characters.",
                permissions=["fs:read:/tmp"],
            )
            assert skill.uid == uid
    
    def test_uid_validation_invalid(self) -> None:
        """Test invalid UID patterns."""
        invalid_uids = [
            "Git:commit",  # uppercase
            "git:Commit",  # uppercase
            "git-commit",  # no colon
            "git:",  # empty action
            ":commit",  # empty namespace
            "git:commit:extra",  # extra colon
            "GIT:COMMIT",  # all uppercase
        ]
        for uid in invalid_uids:
            with pytest.raises(ValueError, match="uid"):
                SkillNode(
                    uid=uid,
                    version="1.0.0",
                    intent_description="Test skill description that meets minimum length requirement.",
                    permissions=["fs:read:/tmp"],
                )
    
    def test_version_validation_valid(self) -> None:
        """Test valid version patterns."""
        valid_versions = ["1.0.0", "2.1.3", "0.5.0", "1.0.0-beta", "2.3.4-alpha"]
        for version in valid_versions:
            skill = SkillNode(
                uid="test:skill",
                version=version,
                intent_description="Test skill description that meets minimum length requirement.",
                permissions=["fs:read:/tmp"],
            )
            assert skill.version == version
    
    def test_version_validation_invalid(self) -> None:
        """Test invalid version patterns."""
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "latest"]
        for version in invalid_versions:
            with pytest.raises(ValueError, match="version"):
                SkillNode(
                    uid="test:skill",
                    version=version,
                    intent_description="Test skill description that meets minimum length requirement.",
                    permissions=["fs:read:/tmp"],
                )
    
    def test_intent_description_length(self) -> None:
        """Test intent description length constraints."""
        # Too short
        with pytest.raises(ValueError, match="intent_description"):
            SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="Too short description",
                permissions=["fs:read:/tmp"],
            )
        
        # Too long
        with pytest.raises(ValueError, match="intent_description"):
            SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="x" * 501,
                permissions=["fs:read:/tmp"],
            )
    
    def test_permission_validation_valid(self) -> None:
        """Test valid permission patterns."""
        valid_permissions = [
            ["fs:read:/tmp"],
            ["fs:read:/tmp", "fs:write:/tmp"],
            ["net:http:github.com"],
            ["db:query:postgres"],
            ["sys:env:HOME"],
        ]
        for perms in valid_permissions:
            skill = SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="Test skill description that meets minimum length requirement.",
                permissions=perms,
            )
            assert skill.permissions == perms
    
    def test_permission_validation_invalid(self) -> None:
        """Test invalid permission patterns."""
        invalid_permissions = [
            ["FS:read:/tmp"],  # uppercase category
            ["fs:Read:/tmp"],  # uppercase action
            ["fsread:/tmp"],  # no colon
        ]
        for perms in invalid_permissions:
            with pytest.raises(ValueError, match="permission"):
                SkillNode(
                    uid="test:skill",
                    version="1.0.0",
                    intent_description="Test skill description that meets minimum length requirement.",
                    permissions=perms,
                )
    
    def test_execution_success_rate_range(self) -> None:
        """Test execution success rate range."""
        # Valid range
        for rate in [0.0, 0.5, 1.0]:
            skill = SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="Test skill description that meets minimum length requirement.",
                permissions=["fs:read:/tmp"],
                execution_success_rate=rate,
            )
            assert skill.execution_success_rate == rate
        
        # Invalid range
        with pytest.raises(ValueError, match="execution_success_rate"):
            SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="Test skill description that meets minimum length requirement.",
                permissions=["fs:read:/tmp"],
                execution_success_rate=1.5,
            )
    
    def test_update_success_rate(self, sample_skill_node: SkillNode) -> None:
        """Test EWMA success rate update."""
        initial_rate = sample_skill_node.execution_success_rate
        
        # Successful execution
        rate_after_success = sample_skill_node.update_success_rate(success=True, alpha=0.7)
        assert rate_after_success >= initial_rate  # 成功后率应该增加或保持
        assert sample_skill_node.execution_count == 101
        
        # Failed execution - 比较失败后的率与成功后的率
        rate_after_failure = sample_skill_node.update_success_rate(success=False, alpha=0.7)
        assert rate_after_failure <= rate_after_success  # 失败后率应该减少或保持
    
    def test_updated_at_validation(self) -> None:
        """Test updated_at >= created_at validation."""
        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="updated_at"):
            SkillNode(
                uid="test:skill",
                version="1.0.0",
                intent_description="Test skill description that meets minimum length requirement.",
                permissions=["fs:read:/tmp"],
                created_at=now,
                updated_at=past,
            )


class TestSkillEdge:
    """Tests for SkillEdge model."""
    
    def test_create_skill_edge(self, sample_skill_edge: SkillEdge) -> None:
        """Test creating a skill edge."""
        assert sample_skill_edge.source_uid == "git:commit_changes"
        assert sample_skill_edge.target_uid == "git:config_user"
        assert sample_skill_edge.edge_type == EdgeType.REQUIRES
        assert sample_skill_edge.weight == 1.0
        assert sample_skill_edge.confidence == 0.95
    
    def test_edge_type_enum(self) -> None:
        """Test edge type enum values."""
        assert EdgeType.REQUIRES.value == "REQUIRES"
        assert EdgeType.CONFLICTS_WITH.value == "CONFLICTS_WITH"
        assert EdgeType.ENHANCES.value == "ENHANCES"
        assert EdgeType.SUBSTITUTES.value == "SUBSTITUTES"
    
    def test_undirected_edge_normalization(self) -> None:
        """Test undirected edge normalization for CONFLICTS_WITH and SUBSTITUTES."""
        # Create edge with reversed order - uid must match namespace:name pattern
        edge = SkillEdge(
            source_uid="skill:b",  # namespace:name format
            target_uid="skill:a",
            edge_type=EdgeType.CONFLICTS_WITH,
        )
        
        # Should be normalized to (skill:a, skill:b) alphabetically
        assert edge.source_uid == "skill:a"
        assert edge.target_uid == "skill:b"
    
    def test_directed_edge_no_normalization(self) -> None:
        """Test directed edges are not normalized."""
        edge = SkillEdge(
            source_uid="skill:b",  # namespace:name format
            target_uid="skill:a",
            edge_type=EdgeType.REQUIRES,
        )
        
        # Should remain unchanged for directed edges
        assert edge.source_uid == "skill:b"
        assert edge.target_uid == "skill:a"
    
    def test_self_edge_prevention(self) -> None:
        """Test self-referential edges are prevented."""
        with pytest.raises(ValueError, match="Self-referential"):
            SkillEdge(
                source_uid="skill:a",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
            )
    
    def test_weight_range(self) -> None:
        """Test weight range validation."""
        # Valid weights
        for weight in [0.0, 0.5, 1.0]:
            edge = SkillEdge(
                source_uid="skill:a",
                target_uid="skill:b",
                edge_type=EdgeType.REQUIRES,
                weight=weight,
            )
            assert edge.weight == weight
        
        # Invalid weight
        with pytest.raises(ValueError):
            SkillEdge(
                source_uid="skill:a",
                target_uid="skill:b",
                edge_type=EdgeType.REQUIRES,
                weight=1.5,
            )


class TestRoutingRequest:
    """Tests for RoutingRequest model."""
    
    def test_create_routing_request(self, sample_routing_request: RoutingRequest) -> None:
        """Test creating a routing request."""
        assert sample_routing_request.query == "I need to commit my changes to the git repository"
        assert sample_routing_request.max_tokens == 4096
        assert sample_routing_request.tenant_id == "default"
    
    def test_request_id_auto_generated(self) -> None:
        """Test request_id is auto-generated."""
        request = RoutingRequest(query="Test query with sufficient length")
        assert request.request_id is not None
        assert isinstance(request.request_id, UUID)
    
    def test_query_length_validation(self) -> None:
        """Test query length validation."""
        # Too short
        with pytest.raises(ValueError, match="query"):
            RoutingRequest(query="Too short")
        
        # Too long
        with pytest.raises(ValueError, match="query"):
            RoutingRequest(query="x" * 2001)
    
    def test_max_tokens_range(self) -> None:
        """Test max_tokens range validation."""
        # Too small
        with pytest.raises(ValueError):
            RoutingRequest(
                query="Valid query length",
                max_tokens=100,
            )
        
        # Too large
        with pytest.raises(ValueError):
            RoutingRequest(
                query="Valid query length",
                max_tokens=50000,
            )


class TestRoutingResponse:
    """Tests for RoutingResponse model."""
    
    def test_create_routing_response(self, sample_routing_response: RoutingResponse) -> None:
        """Test creating a routing response."""
        assert len(sample_routing_response.selected_skills) == 1
        assert sample_routing_response.total_tokens == 500
        assert sample_routing_response.routing_time_ms == 150
    
    def test_no_duplicate_skills(self) -> None:
        """Test duplicate skills are rejected."""
        with pytest.raises(ValueError, match="Duplicate"):
            RoutingResponse(
                request_id=uuid4(),
                selected_skills=[
                    SelectedSkill(
                        skill_uid="skill:a",
                        skill_version="1.0.0",
                        intent_description="Test skill",
                        permissions=["fs:read"],
                        score=0.8,
                    ),
                    SelectedSkill(
                        skill_uid="skill:a",  # duplicate
                        skill_version="1.0.0",
                        intent_description="Test skill",
                        permissions=["fs:read"],
                        score=0.8,
                    ),
                ],
                total_tokens=100,
                routing_time_ms=50,
            )


class TestTelemetryEvent:
    """Tests for TelemetryEvent model."""
    
    def test_create_telemetry_event(self, sample_telemetry_event: TelemetryEvent) -> None:
        """Test creating a telemetry event."""
        assert sample_telemetry_event.event_type == "skill_execution"
        assert sample_telemetry_event.outcome == "success"
        assert sample_telemetry_event.duration_ms == 250
    
    def test_outcome_validation(self) -> None:
        """Test outcome validation."""
        # Valid outcomes
        for outcome in ["success", "failure", "timeout"]:
            event = TelemetryEvent(
                event_type="test",
                skill_uid="test:skill",
                session_id="test-session",
                outcome=outcome,
                duration_ms=100,
            )
            assert event.outcome == outcome
        
        # Invalid outcome
        with pytest.raises(ValueError, match="outcome"):
            TelemetryEvent(
                event_type="test",
                skill_uid="test:skill",
                session_id="test-session",
                outcome="invalid",
                duration_ms=100,
            )


class TestSkillManifest:
    """Tests for SkillManifest model."""
    
    def test_create_skill_manifest(self) -> None:
        """Test creating a skill manifest."""
        manifest = SkillManifest(
            skill_id="git:commit",
            version="1.0.0",
            intent_description="Execute Git commit operation with proper configuration handling.",
            permissions=["fs:read:/tmp"],
        )
        
        assert manifest.skill_id == "git:commit"
        assert manifest.deprecated is False  # default
    
    def test_to_skill_node(self) -> None:
        """Test converting manifest to SkillNode."""
        manifest = SkillManifest(
            skill_id="git:commit",
            version="1.0.0",
            intent_description="Execute Git commit operation with proper configuration handling.",
            permissions=["fs:read:/tmp"],
            author="test-author",
            tags=["git", "test"],
        )
        
        skill_node = manifest.to_skill_node()
        
        assert skill_node.uid == manifest.skill_id
        assert skill_node.version == manifest.version
        assert skill_node.intent_description == manifest.intent_description
        assert skill_node.permissions == manifest.permissions
        assert skill_node.author == manifest.author
        assert skill_node.tags == manifest.tags
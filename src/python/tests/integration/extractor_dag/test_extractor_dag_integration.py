"""
Extractor-DAG Integration Tests.

Test the collaboration workflow between topology extractor and DAG validator modules.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any
from datetime import datetime

from graphskill.ingestion.extractor.topology_extractor import (
    TopologyExtractor,
    InferredRelation,
    TopologyInferenceResult,
)
from graphskill.ingestion.extractor.relation_resolver import (
    RelationResolver,
    ResolutionStrategy,
    ResolvedTopology,
)
from graphskill.ingestion.dag.dag_validator import DAGValidator, DAGValidationResult
from graphskill.ingestion.dag.cycle_detector import TarjanCycleDetector
from graphskill.ingestion.dag.dependency_resolver import DependencyResolver
from graphskill.core.models import EdgeType, SkillNode, SkillEdge


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def dag_validator() -> DAGValidator:
    """Create DAG validator instance."""
    return DAGValidator(strict_mode=False)


@pytest.fixture
def cycle_detector() -> TarjanCycleDetector:
    """Create cycle detector instance."""
    return TarjanCycleDetector()


@pytest.fixture
def dependency_resolver() -> DependencyResolver:
    """Create dependency resolver instance."""
    return DependencyResolver()


@pytest.fixture
def relation_resolver() -> RelationResolver:
    """Create relation resolver instance."""
    return RelationResolver()


@pytest.fixture
def topology_extractor() -> TopologyExtractor:
    """Create topology extractor instance (without LLM client)."""
    return TopologyExtractor(openai_client=None)


@pytest.fixture
def valid_skill_nodes() -> list[dict[str, Any]]:
    """Create valid skill nodes for testing."""
    return [
        {
            "uid": "git:init_repo",
            "skill_id": "git:init",
            "version": "1.0.0",
            "intent_description": "Initialize a new Git repository in the specified directory with proper configuration.",
            "permissions": ["fs:write:/tmp"],
        },
        {
            "uid": "git:commit_changes",
            "skill_id": "git:commit",
            "version": "1.0.0",
            "intent_description": "Execute Git commit operation with proper message formatting and staging verification.",
            "permissions": ["fs:read:/tmp", "fs:write:/tmp"],
        },
        {
            "uid": "git:push_changes",
            "skill_id": "git:push",
            "version": "1.0.0",
            "intent_description": "Push local commits to remote Git repository with authentication handling.",
            "permissions": ["net:http:github.com"],
        },
        {
            "uid": "git:pull_changes",
            "skill_id": "git:pull",
            "version": "1.0.0",
            "intent_description": "Pull remote changes from Git repository and merge with local branch.",
            "permissions": ["net:http:github.com"],
        },
    ]


@pytest.fixture
def valid_dependency_edges() -> list[tuple[str, str]]:
    """Create valid dependency edges (no cycles)."""
    return [
        ("git:commit_changes", "git:init_repo"),  # commit requires init
        ("git:push_changes", "git:commit_changes"),  # push requires commit
        ("git:pull_changes", "git:init_repo"),  # pull requires init
    ]


@pytest.fixture
def cyclic_dependency_edges() -> list[tuple[str, str]]:
    """Create cyclic dependency edges."""
    return [
        ("skill_a:action", "skill_b:action"),
        ("skill_b:action", "skill_c:action"),
        ("skill_c:action", "skill_a:action"),  # Creates cycle
    ]


@pytest.fixture
def inferred_relations() -> list[InferredRelation]:
    """Create inferred relations for testing."""
    return [
        InferredRelation(
            source_uid="git:commit_changes",
            target_uid="git:init_repo",
            edge_type=EdgeType.REQUIRES,
            confidence=0.95,
            reasoning="Commit operation requires an initialized repository",
            is_declared=True,
        ),
        InferredRelation(
            source_uid="git:push_changes",
            target_uid="git:commit_changes",
            edge_type=EdgeType.REQUIRES,
            confidence=0.90,
            reasoning="Push requires commits to push",
            is_declared=False,
        ),
        InferredRelation(
            source_uid="git:commit_changes",
            target_uid="git:reset_hard",
            edge_type=EdgeType.CONFLICTS_WITH,
            confidence=0.85,
            reasoning="Reset hard conflicts with commit workflow",
            is_declared=False,
        ),
    ]


# ============================================================================
# Cycle Detector Integration Tests
# ============================================================================


class TestCycleDetectorIntegration:
    """Cycle detector integration tests."""
    
    @pytest.mark.asyncio
    async def test_cycle_detector_no_cycle(
        self, cycle_detector: TarjanCycleDetector, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test cycle detector with valid DAG (no cycles)."""
        nodes = ["git:init_repo", "git:commit_changes", "git:push_changes", "git:pull_changes"]
        result = cycle_detector.detect(valid_dependency_edges, nodes)
        
        assert result.has_cycle == False
        assert result.cycle_count == 0
    
    @pytest.mark.asyncio
    async def test_cycle_detector_with_cycle(
        self, cycle_detector: TarjanCycleDetector, cyclic_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test cycle detector detecting cycles."""
        nodes = ["skill_a:action", "skill_b:action", "skill_c:action"]
        result = cycle_detector.detect(cyclic_dependency_edges, nodes)
        
        assert result.has_cycle == True
        assert result.cycle_count >= 1
        # Check cycle contains expected nodes
        cycle_nodes = result.cycles[0].nodes
        assert len(cycle_nodes) == 3
    
    @pytest.mark.asyncio
    async def test_cycle_detector_incremental(
        self, cycle_detector: TarjanCycleDetector, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test incremental cycle detection."""
        nodes = ["git:init_repo", "git:commit_changes", "git:push_changes", "git:pull_changes"]
        
        # First, validate existing edges
        existing_result = cycle_detector.detect(valid_dependency_edges, nodes)
        assert existing_result.has_cycle == False
        
        # Add a new edge that would NOT create a cycle
        # Note: detect_incremental expects new_edges as a list of tuples
        # Adding pull -> commit (pull depends on commit) is valid
        new_edges = [("git:pull_changes", "git:commit_changes")]
        incremental_result = cycle_detector.detect_incremental(
            valid_dependency_edges, new_edges, existing_result
        )
        
        # This edge should not create a cycle
        assert incremental_result.has_cycle == False
        
        # Now test with an edge that WOULD create a cycle
        # The existing graph is: commit -> init, push -> commit, pull -> init
        # Adding init -> push would create: init -> push -> commit -> init (cycle!)
        # Note: edge direction is (source, target) where source depends on target
        cycle_edges = [("git:init_repo", "git:push_changes")]
        cycle_result = cycle_detector.detect_incremental(
            valid_dependency_edges, cycle_edges, existing_result
        )
        
        # This edge SHOULD create a cycle
        assert cycle_result.has_cycle == True


# ============================================================================
# DAG Validator Integration Tests
# ============================================================================


class TestDAGValidatorIntegration:
    """DAG validator integration tests."""
    
    @pytest.mark.asyncio
    async def test_dag_validator_valid_dag(
        self, dag_validator: DAGValidator, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test DAG validator with valid dependency graph."""
        result = dag_validator.validate(valid_dependency_edges)
        
        assert result.is_valid == True
        assert result.error_count == 0
        assert result.has_cycles == False
    
    @pytest.mark.asyncio
    async def test_dag_validator_cyclic_dag(
        self, dag_validator: DAGValidator, cyclic_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test DAG validator detecting cyclic dependencies."""
        result = dag_validator.validate(cyclic_dependency_edges)
        
        assert result.is_valid == False
        assert result.error_count > 0
        assert result.has_cycles == True
    
    @pytest.mark.asyncio
    async def test_dag_validator_self_reference(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test DAG validator detecting self-references."""
        edges = [("skill:self_action", "skill:self_action")]
        result = dag_validator.validate(edges)
        
        assert result.is_valid == False
        # Should have self-reference error
        error_types = [e.error_type for e in result.errors]
        assert "self_reference" in error_types
    
    @pytest.mark.asyncio
    async def test_dag_validator_with_isolated_nodes(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test DAG validator handling isolated nodes."""
        edges = [("skill_a:action", "skill_b:action")]
        nodes = ["skill_a:action", "skill_b:action", "skill_c:isolated"]
        result = dag_validator.validate(edges, nodes)
        
        # Should be valid but have warning about isolated node
        assert result.is_valid == True
        assert len(result.warnings) > 0
        assert "isolated" in result.warnings[0].lower()


# ============================================================================
# Dependency Resolver Integration Tests
# ============================================================================


class TestDependencyResolverIntegration:
    """Dependency resolver integration tests."""
    
    @pytest.mark.asyncio
    async def test_dependency_resolver_execution_order(
        self, dependency_resolver: DependencyResolver, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test dependency resolver computing execution order."""
        graph = dependency_resolver.resolve(valid_dependency_edges)
        
        # Get execution order (topological sort)
        execution_order = dependency_resolver.get_execution_order(graph)
        
        assert len(execution_order) == 4
        # init_repo should come before commit_changes
        init_idx = execution_order.index("git:init_repo")
        commit_idx = execution_order.index("git:commit_changes")
        assert init_idx < commit_idx
        
        # commit_changes should come before push_changes
        push_idx = execution_order.index("git:push_changes")
        assert commit_idx < push_idx
    
    @pytest.mark.asyncio
    async def test_dependency_resolver_load_order(
        self, dependency_resolver: DependencyResolver, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test dependency resolver computing load order (reverse of execution)."""
        graph = dependency_resolver.resolve(valid_dependency_edges)
        load_order = dependency_resolver.get_load_order(graph)
        
        assert len(load_order) == 4
        # Load order is reverse of execution order
        # push_changes should be loaded first (leaf node)
        assert load_order[0] == "git:push_changes" or load_order[0] == "git:pull_changes"
    
    @pytest.mark.asyncio
    async def test_dependency_resolver_critical_path(
        self, dependency_resolver: DependencyResolver, valid_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test dependency resolver finding critical path."""
        graph = dependency_resolver.resolve(valid_dependency_edges)
        critical_path = dependency_resolver.find_critical_path(graph)
        
        # Critical path should be the longest dependency chain
        assert len(critical_path) >= 2
        # Should include init -> commit -> push chain
        assert "git:init_repo" in critical_path
    
    @pytest.mark.asyncio
    async def test_dependency_resolver_with_cycle(
        self, dependency_resolver: DependencyResolver, cyclic_dependency_edges: list[tuple[str, str]]
    ) -> None:
        """Test dependency resolver handling cyclic dependencies."""
        graph = dependency_resolver.resolve(cyclic_dependency_edges)
        
        # Should still resolve but mark cycle nodes
        assert graph is not None
        # Execution order may be incomplete due to cycle
        execution_order = dependency_resolver.get_execution_order(graph)
        # Cycle nodes may not all appear in execution order
        assert len(execution_order) <= 3


# ============================================================================
# Relation Resolver Integration Tests
# ============================================================================


class TestRelationResolverIntegration:
    """Relation resolver integration tests."""
    
    @pytest.mark.asyncio
    async def test_relation_resolver_resolve_conflicts(
        self, relation_resolver: RelationResolver, inferred_relations: list[InferredRelation]
    ) -> None:
        """Test relation resolver resolving conflicting relations."""
        # Create declared relations (from topology_hints)
        declared_relations = [
            InferredRelation(
                source_uid="git:commit_changes",
                target_uid="git:init_repo",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,  # Declared relations have high confidence
                reasoning="Declared in topology_hints",
                is_declared=True,
            ),
        ]
        
        # Create inferred relations (from LLM) with conflicting type
        inferred_relations_conflict = [
            InferredRelation(
                source_uid="git:commit_changes",
                target_uid="git:init_repo",
                edge_type=EdgeType.ENHANCES,  # Conflicts with declared REQUIRES
                confidence=0.70,
                reasoning="Alternative interpretation from LLM",
                is_declared=False,
            ),
        ]
        
        resolved = relation_resolver.resolve(
            declared_relations, inferred_relations_conflict, "git:commit_changes"
        )
        
        # Should keep the declared relation (higher priority)
        assert resolved.relation_count > 0
        # Check that REQUIRES (declared) is kept
        requires_relations = [r for r in resolved.relations if r.edge_type == EdgeType.REQUIRES]
        assert len(requires_relations) > 0
    
    @pytest.mark.asyncio
    async def test_relation_resolver_declared_priority(
        self, relation_resolver: RelationResolver
    ) -> None:
        """Test relation resolver prioritizing declared relations."""
        # Declared relation
        declared_relations = [
            InferredRelation(
                source_uid="skill:action",
                target_uid="skill:dependency",
                edge_type=EdgeType.ENHANCES,
                confidence=1.0,  # Declared has high confidence
                reasoning="Declared in topology_hints",
                is_declared=True,
            ),
        ]
        
        # Inferred relation with different type
        inferred_relations = [
            InferredRelation(
                source_uid="skill:action",
                target_uid="skill:dependency",
                edge_type=EdgeType.REQUIRES,
                confidence=0.60,  # Lower confidence
                reasoning="Inferred relation",
                is_declared=False,
            ),
        ]
        
        resolved = relation_resolver.resolve(
            declared_relations, inferred_relations, "skill:action"
        )
        
        # Declared relation should be prioritized
        assert resolved.relation_count >= 1
        # Check that the declared relation is kept
        declared_kept = [r for r in resolved.relations if r.resolution_strategy == ResolutionStrategy.KEEP_DECLARED]
        assert len(declared_kept) > 0


# ============================================================================
# Extractor to DAG Pipeline Tests
# ============================================================================


class TestExtractorDAGPipeline:
    """Test complete pipeline from extractor to DAG validation."""
    
    @pytest.mark.asyncio
    async def test_inferred_relations_to_dag_validation(
        self, dag_validator: DAGValidator, inferred_relations: list[InferredRelation]
    ) -> None:
        """Test converting inferred relations to DAG edges and validating."""
        # Convert InferredRelation to edge tuples (only REQUIRES edges for DAG)
        requires_edges = [
            (r.source_uid, r.target_uid)
            for r in inferred_relations
            if r.edge_type == EdgeType.REQUIRES
        ]
        
        # Validate DAG
        result = dag_validator.validate(requires_edges)
        
        assert result.is_valid == True
        assert result.has_cycles == False
    
    @pytest.mark.asyncio
    async def test_topology_hints_to_dag(
        self, dag_validator: DAGValidator, valid_skill_nodes: list[dict[str, Any]]
    ) -> None:
        """Test converting topology hints from skill nodes to DAG."""
        # Simulate topology hints extraction
        edges = []
        for skill in valid_skill_nodes:
            # Simulate declared hints
            if skill["uid"] == "git:commit_changes":
                edges.append((skill["uid"], "git:init_repo"))
            elif skill["uid"] == "git:push_changes":
                edges.append((skill["uid"], "git:commit_changes"))
        
        # Validate DAG
        result = dag_validator.validate(edges)
        
        assert result.is_valid == True
    
    @pytest.mark.asyncio
    async def test_full_extraction_validation_pipeline(
        self, topology_extractor: TopologyExtractor, dag_validator: DAGValidator,
        dependency_resolver: DependencyResolver, valid_skill_nodes: list[dict[str, Any]]
    ) -> None:
        """Test full pipeline: extraction -> resolution -> DAG validation."""
        # Step 1: Create inferred relations from declared hints
        # (In real scenario, this would come from LLM extraction)
        declared_hints = {
            "git:commit_changes": {
                "requires": ["git:init_repo"],
                "conflicts_with": ["git:reset_hard"],
            },
            "git:push_changes": {
                "requires": ["git:commit_changes"],
            },
        }
        
        # Step 2: Convert to edges
        edges = []
        for source_uid, hints in declared_hints.items():
            for target_uid in hints.get("requires", []):
                edges.append((source_uid, target_uid))
        
        # Step 3: Validate DAG
        dag_result = dag_validator.validate(edges)
        assert dag_result.is_valid == True
        
        # Step 4: Resolve dependencies
        graph = dependency_resolver.resolve(edges)
        execution_order = dependency_resolver.get_execution_order(graph)
        
        # Verify execution order respects dependencies
        assert len(execution_order) == 3
        assert execution_order.index("git:init_repo") < execution_order.index("git:commit_changes")
        assert execution_order.index("git:commit_changes") < execution_order.index("git:push_changes")


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_edges_validation(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test validating empty edge list."""
        result = dag_validator.validate([])
        
        assert result.is_valid == True
        assert result.edge_count == 0
    
    @pytest.mark.asyncio
    async def test_single_edge_validation(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test validating single edge."""
        result = dag_validator.validate([("skill_a:action", "skill_b:action")])
        
        assert result.is_valid == True
        assert result.edge_count == 1
    
    @pytest.mark.asyncio
    async def test_complex_dag_validation(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test validating complex DAG with multiple branches."""
        # Diamond dependency pattern
        edges = [
            ("root:skill", "branch_a:skill"),
            ("root:skill", "branch_b:skill"),
            ("branch_a:skill", "leaf:skill"),
            ("branch_b:skill", "leaf:skill"),
        ]
        
        result = dag_validator.validate(edges)
        
        assert result.is_valid == True
        assert result.has_cycles == False
    
    @pytest.mark.asyncio
    async def test_multiple_cycles_detection(
        self, cycle_detector: TarjanCycleDetector
    ) -> None:
        """Test detecting multiple independent cycles."""
        edges = [
            ("a:skill", "b:skill"),
            ("b:skill", "a:skill"),  # Cycle 1
            ("x:skill", "y:skill"),
            ("y:skill", "z:skill"),
            ("z:skill", "x:skill"),  # Cycle 2
        ]
        nodes = ["a:skill", "b:skill", "x:skill", "y:skill", "z:skill"]
        
        result = cycle_detector.detect(edges, nodes)
        
        assert result.has_cycle == True
        assert result.cycle_count >= 2


# ============================================================================
# SkillEdge Integration Tests
# ============================================================================


class TestSkillEdgeIntegration:
    """Test SkillEdge model integration with DAG."""
    
    @pytest.mark.asyncio
    async def test_skill_edges_to_dag_edges(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test converting SkillEdge objects to DAG edge tuples."""
        skill_edges = [
            SkillEdge(
                source_uid="git:commit",
                target_uid="git:init",
                edge_type=EdgeType.REQUIRES,
                weight=0.95,
                confidence=0.95,
            ),
            SkillEdge(
                source_uid="git:push",
                target_uid="git:commit",
                edge_type=EdgeType.REQUIRES,
                weight=0.90,
                confidence=0.90,
            ),
        ]
        
        # Convert to DAG edges (only REQUIRES type)
        dag_edges = [
            (e.source_uid, e.target_uid)
            for e in skill_edges
            if e.edge_type == EdgeType.REQUIRES
        ]
        
        result = dag_validator.validate(dag_edges)
        
        assert result.is_valid == True
    
    @pytest.mark.asyncio
    async def test_skill_edge_confidence_filtering(
        self, dag_validator: DAGValidator
    ) -> None:
        """Test filtering SkillEdges by confidence before DAG validation."""
        skill_edges = [
            SkillEdge(
                source_uid="skill:a",
                target_uid="skill:b",
                edge_type=EdgeType.REQUIRES,
                weight=0.95,
                confidence=0.95,  # High confidence
            ),
            SkillEdge(
                source_uid="skill:a",
                target_uid="skill:c",
                edge_type=EdgeType.REQUIRES,
                weight=0.30,
                confidence=0.30,  # Low confidence
            ),
        ]
        
        # Filter by confidence threshold
        min_confidence = 0.5
        filtered_edges = [
            (e.source_uid, e.target_uid)
            for e in skill_edges
            if e.edge_type == EdgeType.REQUIRES and e.confidence >= min_confidence
        ]
        
        # Only high confidence edge should remain
        assert len(filtered_edges) == 1
        assert filtered_edges[0] == ("skill:a", "skill:b")
        
        result = dag_validator.validate(filtered_edges)
        assert result.is_valid == True
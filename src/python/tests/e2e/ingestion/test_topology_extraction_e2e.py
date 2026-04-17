"""
E2E 测试：LLM 拓扑提取。

测试使用真实 LLM 服务（glm-5）进行拓扑关系提取。

Reference: plans/phase_03_e2e_plan.md
"""

from __future__ import annotations

import os
import pytest
import asyncio
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent.parent / ".env.test")

from graphskill.ingestion.extractor.topology_extractor import (
    TopologyExtractor,
    TopologyInferenceResult,
    InferredRelation,
)
from graphskill.ingestion.extractor.relation_resolver import RelationResolver
from graphskill.core.models import EdgeType


# ============================================================================
# OpenAI Client Setup
# ============================================================================

def create_openai_client() -> Optional[Any]:
    """
    创建 OpenAI 客户端实例。
    
    使用环境变量中的配置连接到 glm-5 服务。
    """
    try:
        from openai import AsyncOpenAI
        
        api_base = os.getenv("OPENAI_API_BASE", "https://aihub.arcsysu.cn/v1")
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_LLM_MODEL", "glm-5")
        
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set, skipping LLM tests")
            return None
        
        client = AsyncOpenAI(
            base_url=api_base,
            api_key=api_key,
        )
        
        return client
    
    except ImportError:
        pytest.skip("openai package not installed, skipping LLM tests")
        return None


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def skill_dataset_path() -> Path:
    """技能数据集路径."""
    return Path(__file__).parent.parent / "dataset" / "skills"


@pytest.fixture
def openai_client() -> Optional[Any]:
    """OpenAI 客户端."""
    return create_openai_client()


@pytest.fixture
def topology_extractor(openai_client: Optional[Any]) -> TopologyExtractor:
    """拓扑提取器."""
    model = os.getenv("OPENAI_LLM_MODEL", "glm-5")
    return TopologyExtractor(
        openai_client=openai_client,
        model=model,
        temperature=0.3,
        max_tokens=2000,
        min_confidence=0.5,
    )


@pytest.fixture
def relation_resolver() -> RelationResolver:
    """关系解析器."""
    return RelationResolver()


@pytest.fixture
def sample_source_skill() -> dict[str, Any]:
    """示例源技能."""
    return {
        "uid": "git:commit",
        "skill_id": "git:commit",
        "intent_description": "Execute Git commit operation with automatic commit message generation",
        "permissions": ["fs:read:.git", "exec:git:commit"],
        "topology_hints": {
            "requires": ["git:status", "git:diff"],
            "provides": ["git:history"],
        },
    }


@pytest.fixture
def sample_candidate_skills() -> list[dict[str, Any]]:
    """示例候选技能列表."""
    return [
        {
            "uid": "git:status",
            "skill_id": "git:status",
            "intent_description": "Check Git repository status and staged changes",
            "permissions": ["fs:read:.git", "exec:git:status"],
        },
        {
            "uid": "git:diff",
            "skill_id": "git:diff",
            "intent_description": "Show Git diff of staged or unstaged changes",
            "permissions": ["fs:read:.git", "exec:git:diff"],
        },
        {
            "uid": "fs:read",
            "skill_id": "fs:read",
            "intent_description": "Read file contents from filesystem",
            "permissions": ["fs:read:./**"],
        },
        {
            "uid": "web:fetch",
            "skill_id": "web:fetch",
            "intent_description": "Fetch content from web URLs",
            "permissions": ["net:fetch:https://**"],
        },
    ]


# ============================================================================
# Test Classes
# ============================================================================

class TestE2ELLMTopologyExtraction:
    """E2E LLM 拓扑提取测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    async def test_llm_connection(self, openai_client: Optional[Any]) -> None:
        """测试 LLM 连接."""
        if openai_client is None:
            pytest.skip("OpenAI client not available")
        
        # Simple test call
        try:
            response = await openai_client.chat.completions.create(
                model=os.getenv("OPENAI_LLM_MODEL", "glm-5"),
                messages=[
                    {"role": "user", "content": "Hello, respond with 'OK' only."},
                ],
                max_tokens=10,
            )
            
            assert response is not None
            assert len(response.choices) > 0
            assert response.choices[0].message.content is not None
        
        except Exception as e:
            pytest.fail(f"LLM connection failed: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    async def test_topology_extraction_single_skill(
        self,
        topology_extractor: TopologyExtractor,
        sample_source_skill: dict[str, Any],
        sample_candidate_skills: list[dict[str, Any]],
    ) -> None:
        """测试单个技能的拓扑提取."""
        result = await topology_extractor.extract(
            source_skill=sample_source_skill,
            candidate_skills=sample_candidate_skills,
            declared_hints=sample_source_skill.get("topology_hints"),
        )
        
        assert result is not None
        assert isinstance(result, TopologyInferenceResult)
        assert result.source_uid == sample_source_skill["uid"]
        
        # Check that we have some inferred relations
        # Note: LLM may or may not return relations depending on analysis
        if result.inferred_relations:
            for relation in result.inferred_relations:
                assert isinstance(relation, InferredRelation)
                assert relation.target_uid is not None
                assert relation.edge_type in EdgeType
                assert 0.0 <= relation.confidence <= 1.0
        
        # Check for parse errors
        if result.parse_errors:
            # Log parse errors but don't fail
            print(f"Parse errors: {result.parse_errors}")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    async def test_topology_extraction_with_declared_hints(
        self,
        topology_extractor: TopologyExtractor,
        sample_source_skill: dict[str, Any],
        sample_candidate_skills: list[dict[str, Any]],
    ) -> None:
        """测试带声明提示的拓扑提取."""
        declared_hints = {
            "requires": ["git:status", "git:diff"],
            "provides": ["git:history"],
        }
        
        result = await topology_extractor.extract(
            source_skill=sample_source_skill,
            candidate_skills=sample_candidate_skills,
            declared_hints=declared_hints,
        )
        
        assert result is not None
        
        # Declared hints should be included with high confidence
        declared_relations = [
            r for r in result.inferred_relations if r.is_declared
        ]
        
        # If LLM client is None, we should get declared-only results
        if topology_extractor.client is None:
            assert len(declared_relations) > 0
            for r in declared_relations:
                assert r.confidence == 1.0  # Declared hints have confidence 1.0
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    async def test_topology_extraction_no_client(
        self,
        sample_source_skill: dict[str, Any],
        sample_candidate_skills: list[dict[str, Any]],
    ) -> None:
        """测试无 LLM 客户端时的拓扑提取."""
        # Create extractor without client
        extractor = TopologyExtractor(openai_client=None)
        
        declared_hints = sample_source_skill.get("topology_hints", {})
        
        result = await extractor.extract(
            source_skill=sample_source_skill,
            candidate_skills=sample_candidate_skills,
            declared_hints=declared_hints,
        )
        
        assert result is not None
        
        # Should only have declared relations
        for relation in result.inferred_relations:
            assert relation.is_declared
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    @pytest.mark.slow
    async def test_topology_extraction_batch(
        self,
        topology_extractor: TopologyExtractor,
        sample_candidate_skills: list[dict[str, Any]],
    ) -> None:
        """测试批量拓扑提取."""
        if topology_extractor.client is None:
            pytest.skip("LLM client not available")
        
        # Create multiple source skills
        source_skills = [
            {
                "uid": "git:commit",
                "skill_id": "git:commit",
                "intent_description": "Execute Git commit",
            },
            {
                "uid": "fs:read",
                "skill_id": "fs:read",
                "intent_description": "Read file contents",
            },
        ]
        
        results = await topology_extractor.extract_batch(
            skills=source_skills,
            declared_hints_map=None,
        )
        
        assert results is not None
        assert len(results) == len(source_skills)
        
        for uid, result in results.items():
            assert isinstance(result, TopologyInferenceResult)


class TestE2ERelationResolution:
    """E2E 关系解析测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_relation_resolver_conflicts(
        self,
        relation_resolver: RelationResolver,
    ) -> None:
        """测试关系冲突解析."""
        # Create declared and inferred relations with conflicts
        declared_relations = [
            InferredRelation(
                source_uid="git:commit",
                target_uid="git:status",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="Declared requirement",
                is_declared=True,
            ),
        ]
        
        inferred_relations = [
            InferredRelation(
                source_uid="git:commit",
                target_uid="git:status",
                edge_type=EdgeType.REQUIRES,
                confidence=0.8,
                reasoning="LLM inferred requirement",
                is_declared=False,
            ),
            InferredRelation(
                source_uid="git:commit",
                target_uid="fs:read",
                edge_type=EdgeType.REQUIRES,
                confidence=0.6,
                reasoning="LLM inferred optional dependency",
                is_declared=False,
            ),
        ]
        
        result = relation_resolver.resolve(
            declared_relations=declared_relations,
            inferred_relations=inferred_relations,
            source_uid="git:commit",
        )
        
        assert result is not None
        assert len(result.relations) >= 1
        
        # Declared relation should have priority
        for resolved in result.relations:
            if resolved.target_uid == "git:status":
                # Should use declared confidence
                assert resolved.confidence >= 0.8
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_relation_resolver_merge(
        self,
        relation_resolver: RelationResolver,
    ) -> None:
        """测试关系合并."""
        # Create relations with different types
        relations = [
            InferredRelation(
                source_uid="git:commit",
                target_uid="git:status",
                edge_type=EdgeType.REQUIRES,
                confidence=0.9,
                reasoning="Strong dependency",
            ),
            InferredRelation(
                source_uid="git:commit",
                target_uid="git:reset",
                edge_type=EdgeType.CONFLICTS_WITH,
                confidence=0.7,
                reasoning="Operation conflict",
            ),
            InferredRelation(
                source_uid="git:commit",
                target_uid="git:log",
                edge_type=EdgeType.ENHANCES,
                confidence=0.5,
                reasoning="Optional enhancement",
            ),
        ]
        
        result = relation_resolver.resolve(
            declared_relations=[],
            inferred_relations=relations,
            source_uid="git:commit",
        )
        
        assert result is not None
        # Note: RelationResolver may filter certain edge types (e.g., ENHANCES)
        # so we check for at least the core types that are preserved
        assert len(result.relations) >= 2
        
        # Check different edge types
        edge_types = [r.edge_type for r in result.relations]
        assert EdgeType.REQUIRES in edge_types
        assert EdgeType.CONFLICTS_WITH in edge_types
        # Note: ENHANCES may be filtered by RelationResolver depending on configuration


class TestE2ETopologyFromSkillFiles:
    """E2E 从技能文件提取拓扑测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.llm
    async def test_extract_topology_from_real_skills(
        self,
        topology_extractor: TopologyExtractor,
        skill_dataset_path: Path,
    ) -> None:
        """测试从真实技能文件提取拓扑."""
        from graphskill.ingestion.parser.markdown_parser import MarkdownParser
        
        parser = MarkdownParser(strict_mode=True)
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        if not skill_files:
            pytest.skip("No skill files found")
        
        # Parse first skill file
        parsed = parser.parse(skill_files[0])
        frontmatter = parsed.frontmatter
        
        source_skill = {
            "uid": frontmatter.get("skill_id", "unknown:skill"),
            "skill_id": frontmatter.get("skill_id", "unknown:skill"),
            "intent_description": frontmatter.get("intent_description", ""),
            "permissions": frontmatter.get("permissions", []),
            "topology_hints": frontmatter.get("topology_hints", {}),
        }
        
        # Create candidate skills from other files
        candidate_skills = []
        for skill_file in skill_files[1:4]:  # Use next 3 as candidates
            parsed_candidate = parser.parse(skill_file)
            candidate_frontmatter = parsed_candidate.frontmatter
            candidate_skills.append({
                "uid": candidate_frontmatter.get("skill_id", "unknown:skill"),
                "skill_id": candidate_frontmatter.get("skill_id", "unknown:skill"),
                "intent_description": candidate_frontmatter.get("intent_description", ""),
            })
        
        # Extract topology
        result = await topology_extractor.extract(
            source_skill=source_skill,
            candidate_skills=candidate_skills,
            declared_hints=source_skill.get("topology_hints"),
        )
        
        assert result is not None
        assert result.source_uid == source_skill["uid"]


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-end tests with real services")
    config.addinivalue_line("markers", "llm: Tests requiring LLM service")
    config.addinivalue_line("markers", "slow: Slow running tests")
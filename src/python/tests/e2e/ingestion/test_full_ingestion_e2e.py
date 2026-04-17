"""
E2E 测试：完整导入流程。

测试从技能文件扫描到数据库导入的完整流程，
使用真实的数据库连接和 LLM 服务。

Reference: plans/phase_03_e2e_plan.md
"""

from __future__ import annotations

import os
import pytest
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent.parent / ".env.test")

from graphskill.ingestion.parser.markdown_parser import MarkdownParser
from graphskill.ingestion.parser.yaml_parser import YAMLParser
from graphskill.ingestion.validator.schema_validator import SchemaValidator
from graphskill.ingestion.validator.permission_validator import PermissionValidator
from graphskill.ingestion.validator.static_validator import StaticValidator
from graphskill.ingestion.dag.cycle_detector import TarjanCycleDetector
from graphskill.ingestion.dag.dag_validator import DAGValidator
from graphskill.storage.graph_db import Neo4jClient
from graphskill.storage.vector_db import MilvusClient
from graphskill.storage.cache import RedisClient
from graphskill.core.models import SkillNode, SkillEdge, EdgeType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def skill_dataset_path() -> Path:
    """技能数据集路径."""
    return Path(__file__).parent.parent / "dataset" / "skills"


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Markdown 解析器."""
    return MarkdownParser(strict_mode=True)


@pytest.fixture
def yaml_parser() -> YAMLParser:
    """YAML 解析器."""
    return YAMLParser(strict_mode=True)


@pytest.fixture
def schema_validator() -> SchemaValidator:
    """Schema 验证器."""
    return SchemaValidator(strict_mode=False)


@pytest.fixture
def permission_validator() -> PermissionValidator:
    """权限验证器."""
    return PermissionValidator(strict_mode=False)


@pytest.fixture
def static_validator() -> StaticValidator:
    """静态验证器."""
    return StaticValidator()


@pytest.fixture
def dag_validator() -> DAGValidator:
    """DAG 验证器."""
    return DAGValidator(strict_mode=True)


@pytest.fixture
def cycle_detector() -> TarjanCycleDetector:
    """环路检测器."""
    return TarjanCycleDetector()


@pytest.fixture
async def neo4j_client() -> Neo4jClient:
    """Neo4j 客户端."""
    client = Neo4jClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password123"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def milvus_client() -> MilvusClient:
    """Milvus 客户端."""
    client = MilvusClient(
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=int(os.getenv("MILVUS_PORT", "19530")),
        collection_name=os.getenv("MILVUS_COLLECTION_NAME", "test_skill_embeddings_e2e"),
    )
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def redis_client() -> RedisClient:
    """Redis 客户端."""
    client = RedisClient(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD", None),
    )
    await client.connect()
    yield client
    await client.close()


# ============================================================================
# Test Classes
# ============================================================================

class TestE2ESkillParsing:
    """E2E 技能解析测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_parse_all_skill_files(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
    ) -> None:
        """测试解析所有技能文件."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        assert len(skill_files) >= 5, "Should have at least 5 skill files"
        
        parsed_skills = []
        for skill_file in skill_files:
            parsed = markdown_parser.parse(skill_file)
            assert parsed is not None
            assert parsed.frontmatter is not None
            assert len(parsed.code_blocks) > 0
            parsed_skills.append(parsed)
        
        assert len(parsed_skills) == len(skill_files)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_yaml_frontmatter_validation(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        yaml_parser: YAMLParser,
        schema_validator: SchemaValidator,
    ) -> None:
        """测试 YAML frontmatter 验证."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        for skill_file in skill_files:
            parsed = markdown_parser.parse(skill_file)
            frontmatter_dict = parsed.frontmatter
            
            # Validate schema
            result = schema_validator.validate(frontmatter_dict)
            assert result.is_valid, f"Schema validation failed for {skill_file}: {result.errors}"
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_permission_validation(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        permission_validator: PermissionValidator,
    ) -> None:
        """测试权限验证."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        for skill_file in skill_files:
            parsed = markdown_parser.parse(skill_file)
            permissions = parsed.frontmatter.get("permissions", [])
            
            result = permission_validator.validate(permissions)
            assert result.is_valid, f"Permission validation failed for {skill_file}: {result.errors}"


class TestE2EDAGValidation:
    """E2E DAG 验证测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_skill_dag_no_cycles(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        dag_validator: DAGValidator,
    ) -> None:
        """测试技能 DAG 无环路."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        # Build edges from topology_hints
        edges = []
        for skill_file in skill_files:
            parsed = markdown_parser.parse(skill_file)
            skill_id = parsed.frontmatter.get("skill_id", "")
            topology_hints = parsed.frontmatter.get("topology_hints", {})
            
            # Add requires edges
            for required in topology_hints.get("requires", []):
                edges.append((required, skill_id))
            
            # Add provides edges (reverse direction)
            for provided in topology_hints.get("provides", []):
                edges.append((skill_id, provided))
        
        # Validate DAG
        if edges:
            result = dag_validator.validate(edges)
            assert result.is_valid, f"DAG validation failed: cycles detected - {result.cycle_info}"
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_skill_dependency_graph(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        cycle_detector: TarjanCycleDetector,
    ) -> None:
        """测试技能依赖图."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        # Build dependency edges
        edges = []
        skill_ids = []
        
        for skill_file in skill_files:
            parsed = markdown_parser.parse(skill_file)
            skill_id = parsed.frontmatter.get("skill_id", "")
            skill_ids.append(skill_id)
            
            topology_hints = parsed.frontmatter.get("topology_hints", {})
            for required in topology_hints.get("requires", []):
                edges.append((required, skill_id))
        
        # Detect cycles
        result = cycle_detector.detect(edges)
        assert not result.has_cycle, f"Cycles detected in skill dependencies: {result.cycles}"


class TestE2EDatabaseStorage:
    """E2E 数据库存储测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_neo4j_skill_node_creation(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        neo4j_client: Neo4jClient,
    ) -> None:
        """测试 Neo4j 技能节点创建."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        created_nodes = []
        for skill_file in skill_files[:2]:  # Only test first 2 to save time
            parsed = markdown_parser.parse(skill_file)
            frontmatter = parsed.frontmatter
            
            # Create SkillNode
            skill_id = frontmatter.get("skill_id", "")
            # Convert skill_id format to uid format (namespace:name)
            uid = skill_id.replace(":", "_") if ":" in skill_id else f"default:{skill_id}"
            
            node = SkillNode(
                uid=f"e2e_test:{uid}",
                version=frontmatter.get("version", "1.0.0"),
                intent_description=frontmatter.get("intent_description", ""),
                permissions=frontmatter.get("permissions", []),
                execution_success_rate=1.0,
                execution_count=0,
                is_deprecated=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                tags=frontmatter.get("tags", []),
                author=frontmatter.get("author", ""),
            )
            
            # Create node in Neo4j
            result = await neo4j_client.create_node(node)
            assert result is not None
            created_nodes.append(node.uid)
        
        # Verify nodes exist
        for node_uid in created_nodes:
            retrieved = await neo4j_client.get_node(node_uid)
            assert retrieved is not None
        
        # Cleanup
        for node_uid in created_nodes:
            await neo4j_client.delete_node(node_uid)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_milvus_vector_insertion(
        self,
        milvus_client: MilvusClient,
    ) -> None:
        """测试 Milvus 向量插入."""
        # Generate test embedding (1536 dimensions for text-embedding-3-small)
        import random
        test_embedding = [random.random() for _ in range(1536)]
        
        # Insert vector
        test_id = "e2e_test:skill_vector_001"
        await milvus_client.insert(
            uid=test_id,
            embedding=test_embedding,
            metadata={"skill_id": "test:skill", "source": "e2e_test"}
        )
        
        # Search for the vector
        results = await milvus_client.search(
            query_vector=test_embedding,
            top_k=1,
            filter_expr=f"id == '{test_id}'"
        )
        
        assert results.total_count >= 1
        assert len(results.results) >= 1
        
        # Cleanup
        await milvus_client.delete(uid=test_id)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_redis_skill_cache(
        self,
        redis_client: RedisClient,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
    ) -> None:
        """测试 Redis 技能缓存."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        if skill_files:
            parsed = markdown_parser.parse(skill_files[0])
            skill_id = parsed.frontmatter.get("skill_id", "test:skill")
            
            # Cache skill data
            cache_key = f"skill:e2e_test:{skill_id}"
            skill_data = parsed.frontmatter
            
            await redis_client.set(cache_key, str(skill_data), ttl=300)
            
            # Retrieve cached data
            cached = await redis_client.get(cache_key)
            assert cached is not None
            
            # Cleanup
            await redis_client.delete(cache_key)


class TestE2EFullPipeline:
    """E2E 完整流程测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_full_ingestion_pipeline(
        self,
        skill_dataset_path: Path,
        markdown_parser: MarkdownParser,
        yaml_parser: YAMLParser,
        schema_validator: SchemaValidator,
        permission_validator: PermissionValidator,
        dag_validator: DAGValidator,
        neo4j_client: Neo4jClient,
        redis_client: RedisClient,
    ) -> None:
        """测试完整导入流程."""
        skill_files = list(skill_dataset_path.glob("*.SKILL.md"))
        
        # Phase 1: Parse and Validate
        parsed_skills = []
        for skill_file in skill_files:
            # Parse
            parsed = markdown_parser.parse(skill_file)
            frontmatter = parsed.frontmatter
            
            # Validate schema
            schema_result = schema_validator.validate(frontmatter)
            assert schema_result.is_valid
            
            # Validate permissions
            permissions = frontmatter.get("permissions", [])
            perm_result = permission_validator.validate(permissions)
            assert perm_result.is_valid
            
            parsed_skills.append({
                "file": skill_file,
                "parsed": parsed,
                "frontmatter": frontmatter,
            })
        
        # Phase 2: Build DAG edges
        edges = []
        skill_ids = []
        for skill_data in parsed_skills:
            skill_id = skill_data["frontmatter"].get("skill_id", "")
            skill_ids.append(skill_id)
            
            topology_hints = skill_data["frontmatter"].get("topology_hints", {})
            for required in topology_hints.get("requires", []):
                edges.append((required, skill_id))
        
        # Validate DAG
        if edges:
            dag_result = dag_validator.validate(edges)
            assert dag_result.is_valid
        
        # Phase 3: Create nodes in Neo4j
        created_uids = []
        for skill_data in parsed_skills[:3]:  # Only first 3 to save time
            frontmatter = skill_data["frontmatter"]
            skill_id = frontmatter.get("skill_id", "")
            uid = f"e2e:{skill_id.replace(':', '_')}"
            
            node = SkillNode(
                uid=uid,
                version=frontmatter.get("version", "1.0.0"),
                intent_description=frontmatter.get("intent_description", ""),
                permissions=frontmatter.get("permissions", []),
                execution_success_rate=1.0,
                execution_count=0,
                is_deprecated=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                tags=frontmatter.get("tags", []),
                author=frontmatter.get("author", ""),
            )
            
            await neo4j_client.create_node(node)
            created_uids.append(uid)
            
            # Cache in Redis
            cache_key = f"skill:{uid}"
            await redis_client.set(cache_key, str(frontmatter), ttl=300)
        
        # Verify all nodes created
        for uid in created_uids:
            node = await neo4j_client.get_node(uid)
            assert node is not None
            
            cached = await redis_client.get(f"skill:{uid}")
            assert cached is not None
        
        # Cleanup
        for uid in created_uids:
            await neo4j_client.delete_node(uid)
            await redis_client.delete(f"skill:{uid}")


# ============================================================================
# Test Markers
# ============================================================================

# Add custom markers
def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-end tests with real services")
    config.addinivalue_line("markers", "slow: Slow running tests")
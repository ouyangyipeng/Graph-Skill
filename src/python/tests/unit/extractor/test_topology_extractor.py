"""
Topology Extractor 单元测试。

测试拓扑关系抽取器的所有组件：
- InferredRelation 数据结构
- TopologyInferenceResult 数据结构
- TopologyExtractionError 异常
- TopologyExtractor 类
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from graphskill.core.models import EdgeType
from graphskill.ingestion.extractor.topology_extractor import (
    InferredRelation,
    TopologyInferenceResult,
    TopologyExtractionError,
    TopologyExtractor,
)
from graphskill.ingestion.extractor.prompts import (
    SYSTEM_PROMPT,
    build_inference_prompt,
    build_batch_inference_prompt,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def extractor_no_client() -> TopologyExtractor:
    """无客户端的抽取器。"""
    return TopologyExtractor(openai_client=None)


@pytest.fixture
def extractor_with_mock_client() -> TopologyExtractor:
    """带模拟客户端的抽取器。"""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return TopologyExtractor(openai_client=mock_client)


@pytest.fixture
def source_skill() -> dict[str, Any]:
    """源技能数据。"""
    return {
        "uid": "skill:git_commit",
        "skill_id": "skill:git_commit",
        "intent_description": "Execute git commit with message validation and pre-commit hooks",
        "tags": ["git", "version-control", "commit"],
        "permissions": ["fs:read", "fs:write", "exec:git"],
    }


@pytest.fixture
def candidate_skills() -> list[dict[str, Any]]:
    """候选技能列表。"""
    return [
        {
            "uid": "skill:git_config",
            "skill_id": "skill:git_config",
            "intent_description": "Configure git settings and user information for repository operations",
            "tags": ["git", "config"],
            "permissions": ["fs:read", "fs:write"],
        },
        {
            "uid": "skill:git_push",
            "skill_id": "skill:git_push",
            "intent_description": "Push local commits to remote repository with authentication",
            "tags": ["git", "remote"],
            "permissions": ["net:connect", "exec:git"],
        },
        {
            "uid": "skill:fs_delete",
            "skill_id": "skill:fs_delete",
            "intent_description": "Delete files and directories from the filesystem",
            "tags": ["fs", "delete"],
            "permissions": ["fs:write", "fs:delete"],
        },
    ]


@pytest.fixture
def declared_hints() -> dict[str, list[str]]:
    """人工声明的拓扑提示。"""
    return {
        "requires": ["skill:git_config"],
        "conflicts_with": ["skill:fs_delete"],
        "enhances": [],
        "substitutes": [],
    }


@pytest.fixture
def valid_llm_response() -> str:
    """有效的 LLM JSON 响应。"""
    return json.dumps({
        "inferred_relations": [
            {
                "target_uid": "skill:git_config",
                "edge_type": "requires",
                "confidence": 0.95,
                "reasoning": "Git commit requires user config for commit author info",
            },
            {
                "target_uid": "skill:git_push",
                "edge_type": "enhances",
                "confidence": 0.88,
                "reasoning": "Push operation enhances commit workflow",
            },
        ],
        "overall_confidence": 0.91,
        "reasoning": "Git commit has clear dependencies on config and push operations",
    })


@pytest.fixture
def invalid_json_response() -> str:
    """无效的 JSON 响应。"""
    return "This is not valid JSON {broken}"


@pytest.fixture
def partial_llm_response() -> str:
    """部分有效的 LLM 响应（包含无效 edge_type）。"""
    return json.dumps({
        "inferred_relations": [
            {
                "target_uid": "skill:git_config",
                "edge_type": "requires",
                "confidence": 0.85,
                "reasoning": "Valid relation",
            },
            {
                "target_uid": "skill:git_push",
                "edge_type": "invalid_edge_type",
                "confidence": 0.5,
                "reasoning": "Invalid edge type",
            },
        ],
        "overall_confidence": 0.7,
        "reasoning": "Mixed results",
    })


@pytest.fixture
def low_confidence_response() -> str:
    """低置信度响应。"""
    return json.dumps({
        "inferred_relations": [
            {
                "target_uid": "skill:git_config",
                "edge_type": "requires",
                "confidence": 0.3,  # Below threshold
                "reasoning": "Low confidence relation",
            },
        ],
        "overall_confidence": 0.3,
        "reasoning": "Low overall confidence",
    })


@pytest.fixture
def batch_skills() -> list[dict[str, Any]]:
    """批量处理技能列表。"""
    return [
        {
            "uid": "skill:a",
            "intent_description": "Skill A description",
            "tags": ["a"],
            "permissions": [],
        },
        {
            "uid": "skill:b",
            "intent_description": "Skill B description",
            "tags": ["b"],
            "permissions": [],
        },
        {
            "uid": "skill:c",
            "intent_description": "Skill C description",
            "tags": ["c"],
            "permissions": [],
        },
    ]


@pytest.fixture
def batch_llm_response() -> str:
    """批量 LLM 响应。"""
    return json.dumps({
        "topology_map": {
            "skill:a": {
                "relations": [
                    {
                        "target_uid": "skill:b",
                        "edge_type": "requires",
                        "confidence": 0.90,
                        "reasoning": "A requires B",
                    }
                ],
                "confidence": 0.90,
                "reasoning": "A analysis",
            },
            "skill:b": {
                "relations": [
                    {
                        "target_uid": "skill:c",
                        "edge_type": "enhances",
                        "confidence": 0.88,
                        "reasoning": "B enhances C",
                    }
                ],
                "confidence": 0.88,
                "reasoning": "B analysis",
            },
            "skill:c": {
                "relations": [],
                "confidence": 0.95,
                "reasoning": "C has no relations",
            },
        }
    })


# ============================================================================
# InferredRelation Tests
# ============================================================================

class TestInferredRelation:
    """InferredRelation 数据结构测试。"""
    
    def test_create_inferred_relation(self) -> None:
        """测试创建推断关系。"""
        relation = InferredRelation(
            target_uid="skill:target",
            edge_type=EdgeType.REQUIRES,
            confidence=0.85,
            reasoning="Test reasoning",
            source_uid="skill:source",
            is_declared=False,
        )
        
        assert relation.target_uid == "skill:target"
        assert relation.edge_type == EdgeType.REQUIRES
        assert relation.confidence == 0.85
        assert relation.reasoning == "Test reasoning"
        assert relation.source_uid == "skill:source"
        assert relation.is_declared is False
    
    def test_inferred_relation_defaults(self) -> None:
        """测试默认值。"""
        relation = InferredRelation(
            target_uid="skill:target",
            edge_type=EdgeType.ENHANCES,
            confidence=0.5,
            reasoning="",
        )
        
        assert relation.source_uid is None
        assert relation.is_declared is False
    
    def test_inferred_relation_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        relation = InferredRelation(
            target_uid="skill:target",
            edge_type=EdgeType.CONFLICTS_WITH,
            confidence=0.9,
            reasoning="Conflict reasoning",
            source_uid="skill:source",
            is_declared=True,
        )
        
        result = relation.to_dict()
        
        assert result["source_uid"] == "skill:source"
        assert result["target_uid"] == "skill:target"
        assert result["edge_type"] == EdgeType.CONFLICTS_WITH.value  # 大写
        assert result["confidence"] == 0.9
        assert result["reasoning"] == "Conflict reasoning"
        assert result["is_declared"] is True
    
    def test_inferred_relation_to_edge_dict(self) -> None:
        """测试 to_edge_dict 方法。"""
        relation = InferredRelation(
            target_uid="skill:target",
            edge_type=EdgeType.SUBSTITUTES,
            confidence=0.75,
            reasoning="Substitute reasoning",
            source_uid="skill:source",
        )
        
        result = relation.to_edge_dict()
        
        assert result["source_uid"] == "skill:source"
        assert result["target_uid"] == "skill:target"
        assert result["edge_type"] == EdgeType.SUBSTITUTES.value  # 大写
        assert result["weight"] == 0.75
        assert "reasoning" not in result
        assert "is_declared" not in result
    
    def test_all_edge_types(self) -> None:
        """测试所有边类型。"""
        for edge_type in EdgeType:
            relation = InferredRelation(
                target_uid="skill:target",
                edge_type=edge_type,
                confidence=0.5,
                reasoning=f"Test {edge_type.value}",
            )
            assert relation.edge_type == edge_type
            assert relation.to_dict()["edge_type"] == edge_type.value


# ============================================================================
# TopologyInferenceResult Tests
# ============================================================================

class TestTopologyInferenceResult:
    """TopologyInferenceResult 数据结构测试。"""
    
    def test_create_result(self) -> None:
        """测试创建结果。"""
        relations = [
            InferredRelation(
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=0.8,
                reasoning="R1",
                source_uid="skill:source",
            ),
            InferredRelation(
                target_uid="skill:b",
                edge_type=EdgeType.ENHANCES,
                confidence=0.7,
                reasoning="R2",
                source_uid="skill:source",
            ),
        ]
        
        result = TopologyInferenceResult(
            source_uid="skill:source",
            inferred_relations=relations,
            confidence=0.75,
            reasoning="Overall reasoning",
            raw_response="raw",
            parse_errors=[],
        )
        
        assert result.source_uid == "skill:source"
        assert len(result.inferred_relations) == 2
        assert result.confidence == 0.75
        assert result.reasoning == "Overall reasoning"
        assert result.raw_response == "raw"
        assert len(result.parse_errors) == 0
    
    def test_result_defaults(self) -> None:
        """测试默认值。"""
        result = TopologyInferenceResult(source_uid="skill:source")
        
        assert result.inferred_relations == []
        assert result.confidence == 0.0
        assert result.reasoning == ""
        assert result.raw_response is None
        assert result.parse_errors == []
    
    def test_relation_count_property(self) -> None:
        """测试 relation_count 属性。"""
        result_empty = TopologyInferenceResult(source_uid="skill:source")
        assert result_empty.relation_count == 0
        
        relations = [
            InferredRelation("skill:a", EdgeType.REQUIRES, 0.8, "R1"),
            InferredRelation("skill:b", EdgeType.ENHANCES, 0.7, "R2"),
            InferredRelation("skill:c", EdgeType.SUBSTITUTES, 0.6, "R3"),
        ]
        result_with_relations = TopologyInferenceResult(
            source_uid="skill:source",
            inferred_relations=relations,
        )
        assert result_with_relations.relation_count == 3
    
    def test_has_relations_property(self) -> None:
        """测试 has_relations 属性。"""
        result_empty = TopologyInferenceResult(source_uid="skill:source")
        assert result_empty.has_relations is False
        
        relations = [InferredRelation("skill:a", EdgeType.REQUIRES, 0.8, "R1")]
        result_with_relations = TopologyInferenceResult(
            source_uid="skill:source",
            inferred_relations=relations,
        )
        assert result_with_relations.has_relations is True
    
    def test_get_relations_by_type(self) -> None:
        """测试按类型获取关系。"""
        relations = [
            InferredRelation("skill:a", EdgeType.REQUIRES, 0.8, "R1"),
            InferredRelation("skill:b", EdgeType.REQUIRES, 0.7, "R2"),
            InferredRelation("skill:c", EdgeType.ENHANCES, 0.6, "R3"),
            InferredRelation("skill:d", EdgeType.CONFLICTS_WITH, 0.9, "R4"),
        ]
        result = TopologyInferenceResult(
            source_uid="skill:source",
            inferred_relations=relations,
        )
        
        requires = result.get_relations_by_type(EdgeType.REQUIRES)
        assert len(requires) == 2
        assert all(r.edge_type == EdgeType.REQUIRES for r in requires)
        
        enhances = result.get_relations_by_type(EdgeType.ENHANCES)
        assert len(enhances) == 1
        
        conflicts = result.get_relations_by_type(EdgeType.CONFLICTS_WITH)
        assert len(conflicts) == 1
        
        substitutes = result.get_relations_by_type(EdgeType.SUBSTITUTES)
        assert len(substitutes) == 0
    
    def test_result_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        relations = [
            InferredRelation(
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=0.8,
                reasoning="R1",
                source_uid="skill:source",
                is_declared=True,
            ),
        ]
        result = TopologyInferenceResult(
            source_uid="skill:source",
            inferred_relations=relations,
            confidence=0.8,
            reasoning="Overall",
            raw_response="raw",
            parse_errors=["error1"],
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["source_uid"] == "skill:source"
        assert result_dict["relation_count"] == 1
        assert result_dict["confidence"] == 0.8
        assert result_dict["reasoning"] == "Overall"
        assert len(result_dict["inferred_relations"]) == 1
        assert result_dict["inferred_relations"][0]["target_uid"] == "skill:a"
        assert result_dict["parse_errors"] == ["error1"]
        assert "raw_response" not in result_dict  # raw_response 不在 to_dict 中


# ============================================================================
# TopologyExtractionError Tests
# ============================================================================

class TestTopologyExtractionError:
    """TopologyExtractionError 异常测试。"""
    
    def test_error_properties(self) -> None:
        """测试错误属性。"""
        error = TopologyExtractionError(
            message="Extraction failed",
            source_uid="skill:source",
            raw_response="raw response content",
        )
        
        assert str(error) == "Extraction failed"
        assert error.code == "GS-3000"  # IngestionError 的默认 code
        assert error.source_uid == "skill:source"
        assert error.raw_response == "raw response content"
    
    def test_error_without_optional_fields(self) -> None:
        """测试无可选字段的错误。"""
        error = TopologyExtractionError(message="Basic error")
        
        assert str(error) == "Basic error"
        assert error.code == "GS-3000"
        assert error.source_uid is None
        assert error.raw_response is None
    
    def test_error_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        error = TopologyExtractionError(
            message="Test error",
            source_uid="skill:source",
            raw_response="raw response",
        )
        
        result = error.to_dict()
        
        assert result["error"]["message"] == "Test error"
        assert result["error"]["code"] == "GS-3000"
        assert result["source_uid"] == "skill:source"
        assert result["raw_response"] == "raw response"
    
    def test_error_to_dict_truncates_raw_response(self) -> None:
        """测试 to_dict 截断长 raw_response。"""
        long_response = "x" * 1000
        error = TopologyExtractionError(
            message="Error",
            raw_response=long_response,
        )
        
        result = error.to_dict()
        
        assert len(result["raw_response"]) == 500
    
    def test_error_to_dict_without_optional(self) -> None:
        """测试无可选字段时的 to_dict。"""
        error = TopologyExtractionError(message="Basic error")
        
        result = error.to_dict()
        
        assert "error" in result
        assert "source_uid" not in result
        assert "raw_response" not in result
    
    def test_error_inheritance(self) -> None:
        """测试继承关系。"""
        from graphskill.core.exceptions import IngestionError
        
        error = TopologyExtractionError(message="Test")
        assert isinstance(error, IngestionError)


# ============================================================================
# TopologyExtractor Initialization Tests
# ============================================================================

class TestTopologyExtractorInit:
    """TopologyExtractor 初始化测试。"""
    
    def test_init_with_client(self) -> None:
        """测试带客户端初始化。"""
        mock_client = MagicMock()
        extractor = TopologyExtractor(openai_client=mock_client)
        
        assert extractor.client == mock_client
        assert extractor.model == TopologyExtractor.DEFAULT_MODEL
        assert extractor.temperature == TopologyExtractor.DEFAULT_TEMPERATURE
        assert extractor.max_tokens == TopologyExtractor.DEFAULT_MAX_TOKENS
        assert extractor.min_confidence == TopologyExtractor.MIN_CONFIDENCE_THRESHOLD
    
    def test_init_without_client(self) -> None:
        """测试无客户端初始化。"""
        extractor = TopologyExtractor(openai_client=None)
        
        assert extractor.client is None
    
    def test_init_with_custom_params(self) -> None:
        """测试自定义参数初始化。"""
        mock_client = MagicMock()
        extractor = TopologyExtractor(
            openai_client=mock_client,
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=1000,
            min_confidence=0.7,
        )
        
        assert extractor.model == "gpt-3.5-turbo"
        assert extractor.temperature == 0.5
        assert extractor.max_tokens == 1000
        assert extractor.min_confidence == 0.7
    
    def test_default_constants(self) -> None:
        """测试默认常量。"""
        assert TopologyExtractor.DEFAULT_MODEL == "gpt-4-turbo-preview"
        assert TopologyExtractor.DEFAULT_TEMPERATURE == 0.3
        assert TopologyExtractor.DEFAULT_MAX_TOKENS == 2000
        assert TopologyExtractor.MIN_CONFIDENCE_THRESHOLD == 0.85  # RFC-02 要求
        assert TopologyExtractor.DECLARED_HINT_CONFIDENCE == 1.0


# ============================================================================
# TopologyExtractor Extract Tests (No Client)
# ============================================================================

class TestTopologyExtractorExtractNoClient:
    """无客户端时的 extract 测试。"""
    
    @pytest.mark.asyncio
    async def test_extract_without_client_returns_declared(
        self,
        extractor_no_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
    ) -> None:
        """测试无客户端时返回人工声明的关系。"""
        result = await extractor_no_client.extract(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        assert result.source_uid == "skill:git_commit"
        assert result.has_relations is True
        assert result.relation_count == 2  # requires + conflicts_with
        assert result.confidence == 1.0
        assert "no LLM inference" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_extract_without_client_no_hints(
        self,
        extractor_no_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
    ) -> None:
        """测试无客户端且无声明时返回空结果。"""
        result = await extractor_no_client.extract(
            source_skill,
            candidate_skills,
            None,
        )
        
        assert result.source_uid == "skill:git_commit"
        assert result.has_relations is False
        assert result.confidence == 0.0
    
    @pytest.mark.asyncio
    async def test_extract_without_client_empty_hints(
        self,
        extractor_no_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
    ) -> None:
        """测试无客户端且空声明时返回空结果。"""
        result = await extractor_no_client.extract(
            source_skill,
            candidate_skills,
            {"requires": [], "conflicts_with": [], "enhances": [], "substitutes": []},
        )
        
        assert result.has_relations is False


# ============================================================================
# TopologyExtractor Extract Tests (With Mock Client)
# ============================================================================

class TestTopologyExtractorExtractWithClient:
    """带模拟客户端的 extract 测试。"""
    
    @pytest.mark.asyncio
    async def test_extract_with_valid_response(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
        valid_llm_response: str,
    ) -> None:
        """测试有效 LLM 响应。"""
        # 设置 mock 返回
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = valid_llm_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        assert result.source_uid == "skill:git_commit"
        assert result.relation_count >= 2  # LLM + declared
        assert result.raw_response == valid_llm_response
        assert len(result.parse_errors) == 0
        
        # 验证调用参数
        call_args = extractor_with_mock_client.client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == extractor_with_mock_client.model
        assert call_args.kwargs["temperature"] == extractor_with_mock_client.temperature
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
    
    @pytest.mark.asyncio
    async def test_extract_with_invalid_json(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
        invalid_json_response: str,
    ) -> None:
        """测试无效 JSON 响应。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = invalid_json_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        assert result.source_uid == "skill:git_commit"
        assert len(result.parse_errors) > 0
        assert "JSON decode error" in result.parse_errors[0]
        # 仍然包含人工声明
        assert result.has_relations is True
    
    @pytest.mark.asyncio
    async def test_extract_with_partial_invalid(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        partial_llm_response: str,
    ) -> None:
        """测试部分无效响应。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = partial_llm_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            None,
        )
        
        # 有效关系被解析
        assert result.relation_count == 1
        assert len(result.parse_errors) > 0
    
    @pytest.mark.asyncio
    async def test_extract_filters_low_confidence(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        low_confidence_response: str,
    ) -> None:
        """测试低置信度过滤。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = low_confidence_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            None,
        )
        
        # 低置信度关系被过滤
        assert result.relation_count == 0
    
    @pytest.mark.asyncio
    async def test_extract_llm_call_failure(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
    ) -> None:
        """测试 LLM 调用失败。"""
        extractor_with_mock_client.client.chat.completions.create.side_effect = Exception("API Error")
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        assert result.has_relations is True  # 返回人工声明
        assert len(result.parse_errors) > 0
        assert "LLM call failed" in result.parse_errors[0]
    
    @pytest.mark.asyncio
    async def test_extract_empty_response(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
    ) -> None:
        """测试空响应。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            None,
        )
        
        assert result.relation_count == 0
        assert len(result.parse_errors) > 0


# ============================================================================
# TopologyExtractor Batch Extract Tests
# ============================================================================

class TestTopologyExtractorBatchExtract:
    """批量抽取测试。"""
    
    @pytest.mark.asyncio
    async def test_batch_extract_without_client(
        self,
        extractor_no_client: TopologyExtractor,
        batch_skills: list,
    ) -> None:
        """测试无客户端批量抽取。"""
        hints_map = {
            "skill:a": {"requires": ["skill:b"]},
        }
        
        results = await extractor_no_client.extract_batch(batch_skills, hints_map)
        
        assert len(results) == 3
        assert results["skill:a"].has_relations is True
        assert results["skill:b"].has_relations is False
        assert results["skill:c"].has_relations is False
    
    @pytest.mark.asyncio
    async def test_batch_extract_with_valid_response(
        self,
        extractor_with_mock_client: TopologyExtractor,
        batch_skills: list,
        batch_llm_response: str,
    ) -> None:
        """测试有效批量响应。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = batch_llm_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        results = await extractor_with_mock_client.extract_batch(batch_skills, None)
        
        assert len(results) == 3
        assert results["skill:a"].relation_count == 1
        assert results["skill:b"].relation_count == 1
        assert results["skill:c"].relation_count == 0
    
    @pytest.mark.asyncio
    async def test_batch_extract_with_declared_hints(
        self,
        extractor_with_mock_client: TopologyExtractor,
        batch_skills: list,
        batch_llm_response: str,
    ) -> None:
        """测试带人工声明的批量抽取。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = batch_llm_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        hints_map = {
            "skill:a": {"requires": ["skill:c"]},
        }
        
        results = await extractor_with_mock_client.extract_batch(batch_skills, hints_map)
        
        # skill:a 应有 LLM 推断 + 人工声明
        assert results["skill:a"].relation_count >= 1
    
    @pytest.mark.asyncio
    async def test_batch_extract_llm_failure(
        self,
        extractor_with_mock_client: TopologyExtractor,
        batch_skills: list,
    ) -> None:
        """测试批量 LLM 调用失败。"""
        extractor_with_mock_client.client.chat.completions.create.side_effect = Exception("Batch API Error")
        
        hints_map = {
            "skill:a": {"requires": ["skill:b"]},
        }
        
        results = await extractor_with_mock_client.extract_batch(batch_skills, hints_map)
        
        assert len(results) == 3
        # 返回人工声明
        assert results["skill:a"].has_relations is True
        for uid in ["skill:a", "skill:b", "skill:c"]:
            assert len(results[uid].parse_errors) > 0
            assert "Batch LLM call failed" in results[uid].parse_errors[0]
    
    @pytest.mark.asyncio
    async def test_batch_extract_invalid_json(
        self,
        extractor_with_mock_client: TopologyExtractor,
        batch_skills: list,
    ) -> None:
        """测试批量无效 JSON。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "invalid json"
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        results = await extractor_with_mock_client.extract_batch(batch_skills, None)
        
        assert len(results) == 3
        for uid in ["skill:a", "skill:b", "skill:c"]:
            assert len(results[uid].parse_errors) > 0


# ============================================================================
# TopologyExtractor Parse Response Tests
# ============================================================================

class TestTopologyExtractorParseResponse:
    """响应解析测试。"""
    
    def test_parse_valid_response(
        self,
        extractor_no_client: TopologyExtractor,
        valid_llm_response: str,
    ) -> None:
        """测试解析有效响应。"""
        result = extractor_no_client._parse_response(
            "skill:source",
            valid_llm_response,
            None,
        )
        
        assert result.source_uid == "skill:source"
        assert result.relation_count == 2
        assert result.confidence == 0.91
        assert len(result.parse_errors) == 0
    
    def test_parse_response_with_declared_hints(
        self,
        extractor_no_client: TopologyExtractor,
        valid_llm_response: str,
        declared_hints: dict,
    ) -> None:
        """测试解析带人工声明的响应。"""
        result = extractor_no_client._parse_response(
            "skill:git_commit",
            valid_llm_response,
            declared_hints,
        )
        
        # LLM 推断 + 人工声明
        assert result.relation_count >= 2
        
        # 检查人工声明的关系
        declared_relations = [r for r in result.inferred_relations if r.is_declared]
        assert len(declared_relations) == 2
    
    def test_parse_response_invalid_json(
        self,
        extractor_no_client: TopologyExtractor,
        invalid_json_response: str,
    ) -> None:
        """测试解析无效 JSON。"""
        result = extractor_no_client._parse_response(
            "skill:source",
            invalid_json_response,
            None,
        )
        
        assert result.relation_count == 0
        assert len(result.parse_errors) > 0
        assert "JSON decode error" in result.parse_errors[0]
    
    def test_parse_response_missing_fields(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试缺失字段。"""
        response = json.dumps({
            "inferred_relations": [
                {"target_uid": "skill:a"},  # 缺少 edge_type
            ],
        })
        
        result = extractor_no_client._parse_response(
            "skill:source",
            response,
            None,
        )
        
        assert len(result.parse_errors) > 0
    
    def test_parse_response_empty_relations(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试空关系列表。"""
        response = json.dumps({
            "inferred_relations": [],
            "overall_confidence": 0.5,
            "reasoning": "No relations found",
        })
        
        result = extractor_no_client._parse_response(
            "skill:source",
            response,
            None,
        )
        
        assert result.relation_count == 0
        assert result.confidence == 0.5


# ============================================================================
# TopologyExtractor Parse Declared Hints Tests
# ============================================================================

class TestTopologyExtractorParseDeclaredHints:
    """人工声明解析测试。"""
    
    def test_parse_declared_requires(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试解析 requires 声明。"""
        hints = {"requires": ["skill:a", "skill:b"]}
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 2
        assert all(r.edge_type == EdgeType.REQUIRES for r in relations)
        assert all(r.is_declared for r in relations)
        assert all(r.confidence == 1.0 for r in relations)
        assert relations[0].target_uid == "skill:a"
        assert relations[1].target_uid == "skill:b"
    
    def test_parse_declared_conflicts(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试解析 conflicts_with 声明。"""
        hints = {"conflicts_with": ["skill:x"]}
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 1
        assert relations[0].edge_type == EdgeType.CONFLICTS_WITH
        assert relations[0].is_declared
    
    def test_parse_declared_enhances(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试解析 enhances 声明。"""
        hints = {"enhances": ["skill:y"]}
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 1
        assert relations[0].edge_type == EdgeType.ENHANCES
    
    def test_parse_declared_substitutes(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试解析 substitutes 声明。"""
        hints = {"substitutes": ["skill:z"]}
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 1
        assert relations[0].edge_type == EdgeType.SUBSTITUTES
    
    def test_parse_declared_all_types(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试解析所有类型声明。"""
        hints = {
            "requires": ["skill:a"],
            "conflicts_with": ["skill:b"],
            "enhances": ["skill:c"],
            "substitutes": ["skill:d"],
        }
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 4
        
        # 检查每种类型
        types = {r.edge_type for r in relations}
        assert EdgeType.REQUIRES in types
        assert EdgeType.CONFLICTS_WITH in types
        assert EdgeType.ENHANCES in types
        assert EdgeType.SUBSTITUTES in types
    
    def test_parse_declared_empty_hints(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试空声明。"""
        hints = {}
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 0
    
    def test_parse_declared_empty_lists(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试空列表声明。"""
        hints = {
            "requires": [],
            "conflicts_with": [],
            "enhances": [],
            "substitutes": [],
        }
        
        relations = extractor_no_client._parse_declared_hints("skill:source", hints)
        
        assert len(relations) == 0


# ============================================================================
# TopologyExtractor Build Declared Only Result Tests
# ============================================================================

class TestTopologyExtractorBuildDeclaredOnlyResult:
    """构建仅人工声明结果测试。"""
    
    def test_build_with_hints(
        self,
        extractor_no_client: TopologyExtractor,
        declared_hints: dict,
    ) -> None:
        """测试带声明构建。"""
        result = extractor_no_client._build_declared_only_result(
            "skill:source",
            declared_hints,
        )
        
        assert result.source_uid == "skill:source"
        assert result.has_relations is True
        assert result.confidence == 1.0
        assert "no LLM inference" in result.reasoning
    
    def test_build_without_hints(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试无声明构建。"""
        result = extractor_no_client._build_declared_only_result(
            "skill:source",
            None,
        )
        
        assert result.has_relations is False
        assert result.confidence == 0.0


# ============================================================================
# TopologyExtractor Sync Extract Tests
# ============================================================================

class TestTopologyExtractorSyncExtract:
    """同步抽取测试。"""
    
    def test_extract_sync_without_client(
        self,
        extractor_no_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
    ) -> None:
        """测试同步抽取（无客户端）。"""
        result = extractor_no_client.extract_sync(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        assert result.source_uid == "skill:git_commit"
        assert result.has_relations is True


# ============================================================================
# TopologyExtractor Set Client and Configure Tests
# ============================================================================

class TestTopologyExtractorClientAndConfig:
    """客户端设置和配置测试。"""
    
    def test_set_client(self) -> None:
        """测试设置客户端。"""
        extractor = TopologyExtractor(openai_client=None)
        assert extractor.client is None
        
        mock_client = MagicMock()
        extractor.set_client(mock_client)
        
        assert extractor.client == mock_client
    
    def test_configure_model(self) -> None:
        """测试配置模型。"""
        extractor = TopologyExtractor(openai_client=None)
        extractor.configure(model="gpt-4")
        
        assert extractor.model == "gpt-4"
    
    def test_configure_temperature(self) -> None:
        """测试配置温度。"""
        extractor = TopologyExtractor(openai_client=None)
        extractor.configure(temperature=0.7)
        
        assert extractor.temperature == 0.7
    
    def test_configure_max_tokens(self) -> None:
        """测试配置最大 token。"""
        extractor = TopologyExtractor(openai_client=None)
        extractor.configure(max_tokens=500)
        
        assert extractor.max_tokens == 500
    
    def test_configure_min_confidence(self) -> None:
        """测试配置最小置信度。"""
        extractor = TopologyExtractor(openai_client=None)
        extractor.configure(min_confidence=0.8)
        
        assert extractor.min_confidence == 0.8
    
    def test_configure_multiple_params(self) -> None:
        """测试配置多个参数。"""
        extractor = TopologyExtractor(openai_client=None)
        extractor.configure(
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=1000,
            min_confidence=0.6,
        )
        
        assert extractor.model == "gpt-3.5-turbo"
        assert extractor.temperature == 0.5
        assert extractor.max_tokens == 1000
        assert extractor.min_confidence == 0.6
    
    def test_configure_none_values_unchanged(self) -> None:
        """测试 None 值不改变配置。"""
        extractor = TopologyExtractor(
            openai_client=None,
            model="gpt-4",
            temperature=0.3,
        )
        extractor.configure(model=None, temperature=None)
        
        assert extractor.model == "gpt-4"
        assert extractor.temperature == 0.3


# ============================================================================
# Prompts Tests
# ============================================================================

class TestPrompts:
    """Prompt 模板测试。"""
    
    def test_system_prompt_content(self) -> None:
        """测试系统提示词内容。"""
        assert "topology analysis expert" in SYSTEM_PROMPT.lower()
        assert "REQUIRES" in SYSTEM_PROMPT
        assert "CONFLICTS_WITH" in SYSTEM_PROMPT
        assert "ENHANCES" in SYSTEM_PROMPT
        assert "SUBSTITUTES" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT
    
    def test_build_inference_prompt_basic(
        self,
        source_skill: dict,
        candidate_skills: list,
    ) -> None:
        """测试构建推断 Prompt。"""
        prompt = build_inference_prompt(source_skill, candidate_skills, None)
        
        assert "skill:git_commit" in prompt
        assert "git commit" in prompt.lower()
        assert "skill:git_config" in prompt
        assert "skill:git_push" in prompt
    
    def test_build_inference_prompt_with_hints(
        self,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
    ) -> None:
        """测试带声明的推断 Prompt。"""
        prompt = build_inference_prompt(source_skill, candidate_skills, declared_hints)
        
        assert "Human-declared" in prompt
        assert "HIGH CONFIDENCE" in prompt
        assert "skill:git_config" in prompt
    
    def test_build_batch_inference_prompt(
        self,
        batch_skills: list,
    ) -> None:
        """测试批量推断 Prompt。"""
        prompt = build_batch_inference_prompt(batch_skills, None)
        
        assert "skill:a" in prompt
        assert "skill:b" in prompt
        assert "skill:c" in prompt
        assert "topology_map" in prompt
    
    def test_build_batch_inference_prompt_with_hints(
        self,
        batch_skills: list,
    ) -> None:
        """测试带声明的批量 Prompt。"""
        hints_map = {
            "skill:a": {"requires": ["skill:b"]},
        }
        
        prompt = build_batch_inference_prompt(batch_skills, hints_map)
        
        assert "topology_hints" in prompt


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """边界条件测试。"""
    
    @pytest.mark.asyncio
    async def test_extract_with_skill_id_instead_of_uid(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试使用 skill_id 而非 uid。"""
        source = {"skill_id": "skill:test"}  # 无 uid
        candidates = []
        hints = {"requires": ["skill:other"]}
        
        result = await extractor_no_client.extract(source, candidates, hints)
        
        assert result.source_uid == "skill:test"
    
    @pytest.mark.asyncio
    async def test_extract_with_unknown_source_uid(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试未知源 UID。"""
        source = {}  # 无 uid 和 skill_id
        candidates = []
        
        result = await extractor_no_client.extract(source, candidates, None)
        
        assert result.source_uid == "unknown"
    
    def test_parse_response_with_extra_fields(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试响应包含额外字段。"""
        response = json.dumps({
            "inferred_relations": [
                {
                    "target_uid": "skill:a",
                    "edge_type": "requires",
                    "confidence": 0.90,
                    "reasoning": "Test",
                    "extra_field": "ignored",
                }
            ],
            "overall_confidence": 0.90,
            "extra_top_field": "also ignored",
        })
        
        result = extractor_no_client._parse_response("skill:source", response, None)
        
        assert result.relation_count == 1
        assert len(result.parse_errors) == 0
    
    def test_parse_response_case_insensitive_edge_type(
        self,
        extractor_no_client: TopologyExtractor,
    ) -> None:
        """测试 edge_type 大小写不敏感。"""
        response = json.dumps({
            "inferred_relations": [
                {
                    "target_uid": "skill:a",
                    "edge_type": "REQUIRES",  # 大写
                    "confidence": 0.90,
                    "reasoning": "Test",
                }
            ],
        })
        
        result = extractor_no_client._parse_response("skill:source", response, None)
        
        assert result.relation_count == 1
        assert result.inferred_relations[0].edge_type == EdgeType.REQUIRES
    
    @pytest.mark.asyncio
    async def test_extract_with_none_response_content(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
    ) -> None:
        """测试响应内容为 None。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        result = await extractor_with_mock_client.extract(source_skill, candidate_skills, None)
        
        assert result.relation_count == 0
        assert len(result.parse_errors) > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试。"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_mock(
        self,
        extractor_with_mock_client: TopologyExtractor,
        source_skill: dict,
        candidate_skills: list,
        declared_hints: dict,
        valid_llm_response: str,
    ) -> None:
        """测试完整工作流。"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = valid_llm_response
        extractor_with_mock_client.client.chat.completions.create.return_value = mock_response
        
        # 执行抽取
        result = await extractor_with_mock_client.extract(
            source_skill,
            candidate_skills,
            declared_hints,
        )
        
        # 验证结果
        assert result.source_uid == "skill:git_commit"
        assert result.has_relations is True
        
        # 验证关系类型分布
        requires = result.get_relations_by_type(EdgeType.REQUIRES)
        enhances = result.get_relations_by_type(EdgeType.ENHANCES)
        
        assert len(requires) >= 1  # LLM 或声明
        assert len(enhances) >= 1  # LLM
        
        # 验证 to_dict 输出
        result_dict = result.to_dict()
        assert "source_uid" in result_dict
        assert "inferred_relations" in result_dict
    
    def test_workflow_sync(self) -> None:
        """测试同步工作流。"""
        extractor = TopologyExtractor(openai_client=None)
        
        source = {
            "uid": "skill:test",
            "intent_description": "Test skill",
        }
        hints = {
            "requires": ["skill:dep1", "skill:dep2"],
            "enhances": ["skill:enh"],
        }
        
        result = extractor.extract_sync(source, [], hints)
        
        assert result.relation_count == 3
        assert result.confidence == 1.0
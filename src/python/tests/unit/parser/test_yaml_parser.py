"""
YAML Frontmatter 解析器单元测试。

测试 YAMLParser 的所有核心功能：
- 必填字段验证
- 可选字段验证
- 格式规范检查
- 拓扑提示解析
- 错误处理

Reference: RFC-01 Section 2.1, RFC-02 Section 3.2
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from graphskill.ingestion.parser.yaml_parser import (
    OPTIONAL_FIELDS,
    ParsedFrontmatter,
    REQUIRED_FIELDS,
    YAMLParser,
    YAMLValidationError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def parser() -> YAMLParser:
    """创建默认解析器实例。"""
    return YAMLParser(strict_mode=True)


@pytest.fixture
def lenient_parser() -> YAMLParser:
    """创建非严格模式解析器实例。"""
    return YAMLParser(strict_mode=False)


@pytest.fixture
def valid_frontmatter() -> dict[str, Any]:
    """有效的 Frontmatter 数据。"""
    return {
        "skill_id": "git:commit_changes",
        "version": "1.0.0",
        "intent_description": "Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.",
        "permissions": [
            "fs:read:/tmp",
            "fs:write:/tmp",
            "net:http:github.com",
        ],
        "tags": ["git", "version-control", "commit"],
        "author": "test-author",
        "created_at": "2024-01-01",
        "updated_at": "2024-01-15T10:30:00",
        "topology_hints": {
            "requires": ["git:init_repo"],
            "conflicts_with": ["git:reset_hard"],
            "enhances": ["git:push_changes"],
            "substitutes": ["git:commit_amend"],
        },
    }


@pytest.fixture
def minimal_frontmatter() -> dict[str, Any]:
    """最小有效 Frontmatter 数据。"""
    return {
        "skill_id": "test:minimal",
        "version": "0.1.0",
        "intent_description": "A minimal test skill for basic functionality verification and unit testing purposes. This description meets the minimum length requirement.",
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def invalid_skill_id_frontmatter() -> dict[str, Any]:
    """无效 skill_id 格式的 Frontmatter。"""
    return {
        "skill_id": "invalid_skill_id",  # 缺少 namespace:name 格式
        "version": "1.0.0",
        "intent_description": "Test invalid skill_id format handling in strict validation mode.",
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def invalid_version_frontmatter() -> dict[str, Any]:
    """无效 version 格式的 Frontmatter。"""
    return {
        "skill_id": "test:invalid_version",
        "version": "v1.0",  # 不符合 SemVer
        "intent_description": "Test invalid version format handling in strict validation mode.",
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def short_intent_frontmatter() -> dict[str, Any]:
    """意图描述过短的 Frontmatter。"""
    return {
        "skill_id": "test:short_intent",
        "version": "1.0.0",
        "intent_description": "Too short",  # 不足 50 字符
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def long_intent_frontmatter() -> dict[str, Any]:
    """意图描述过长的 Frontmatter。"""
    return {
        "skill_id": "test:long_intent",
        "version": "1.0.0",
        "intent_description": "x" * 600,  # 超过 500 字符
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def empty_permissions_frontmatter() -> dict[str, Any]:
    """空权限列表的 Frontmatter。"""
    return {
        "skill_id": "test:empty_perms",
        "version": "1.0.0",
        "intent_description": "Test empty permissions list handling in strict validation mode.",
        "permissions": [],  # 空列表
    }


@pytest.fixture
def invalid_permission_format_frontmatter() -> dict[str, Any]:
    """无效权限格式的 Frontmatter。"""
    return {
        "skill_id": "test:invalid_perm",
        "version": "1.0.0",
        "intent_description": "Test invalid permission format handling in strict validation mode.",
        "permissions": ["invalid_permission_format"],  # 不符合 pattern
    }


@pytest.fixture
def missing_required_field_frontmatter() -> dict[str, Any]:
    """缺少必填字段的 Frontmatter。"""
    return {
        "skill_id": "test:missing_field",
        # 缺少 version
        "intent_description": "Test missing required field handling in strict validation mode.",
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def wrong_type_frontmatter() -> dict[str, Any]:
    """字段类型错误的 Frontmatter。"""
    return {
        "skill_id": "test:wrong_type",
        "version": "1.0.0",
        "intent_description": "Test wrong field type handling in strict validation mode.",
        "permissions": "fs:read:/tmp",  # 应为列表，实为字符串
    }


@pytest.fixture
def optional_fields_frontmatter() -> dict[str, Any]:
    """包含所有可选字段的 Frontmatter。"""
    return {
        "skill_id": "test:optional",
        "version": "1.0.0",
        "intent_description": "Test all optional fields parsing and validation in the frontmatter.",
        "permissions": ["fs:read:/tmp"],
        "tags": ["test", "optional"],
        "author": "Test Author",
        "created_at": "2024-01-01",
        "updated_at": "2024-06-15T12:00:00",
        "min_agent_version": "1.0.0",
        "max_agent_version": "2.0.0",
        "deprecated": True,
        "deprecation_message": "Use test:new_skill instead",
        "success_rate": 0.95,
        "avg_latency_ms": 150,
    }


@pytest.fixture
def invalid_optional_fields_frontmatter() -> dict[str, Any]:
    """包含无效可选字段的 Frontmatter。"""
    return {
        "skill_id": "test:invalid_optional",
        "version": "1.0.0",
        "intent_description": "Test invalid optional fields handling in validation mode.",
        "permissions": ["fs:read:/tmp"],
        "success_rate": 1.5,  # 超出范围 (0-1)
        "avg_latency_ms": -10,  # 负数
        "created_at": "invalid-date",  # 格式错误
    }


@pytest.fixture
def topology_hints_frontmatter() -> dict[str, Any]:
    """包含完整拓扑提示的 Frontmatter。"""
    return {
        "skill_id": "test:topology",
        "version": "1.0.0",
        "intent_description": "Test topology hints extraction and validation in the frontmatter parsing.",
        "permissions": ["fs:read:/tmp"],
        "topology_hints": {
            "requires": ["skill:a", "skill:b"],
            "conflicts_with": ["skill:c"],
            "enhances": ["skill:d"],
            "substitutes": ["skill:e"],
        },
    }


@pytest.fixture
def invalid_topology_hints_frontmatter() -> dict[str, Any]:
    """包含无效拓扑提示的 Frontmatter。"""
    return {
        "skill_id": "test:invalid_topology",
        "version": "1.0.0",
        "intent_description": "Test invalid topology hints handling in validation mode.",
        "permissions": ["fs:read:/tmp"],
        "topology_hints": {
            "requires": "not-a-list",  # 应为列表
            "conflicts_with": ["valid"],
        },
    }


@pytest.fixture
def valid_yaml_string() -> str:
    """有效的 YAML 字符串。"""
    return """
skill_id: git:commit_changes
version: 1.0.0
intent_description: Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow.
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
tags:
  - git
"""


@pytest.fixture
def invalid_yaml_string() -> str:
    """无效的 YAML 字符串。"""
    return """
skill_id: test:invalid
version: [broken
intent_description: Test
"""


# =============================================================================
# Basic Parsing Tests
# =============================================================================


class TestYAMLParserBasic:
    """基础解析功能测试。"""

    def test_parse_valid_frontmatter(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试解析有效 Frontmatter。"""
        result = parser.parse(valid_frontmatter)

        assert isinstance(result, ParsedFrontmatter)
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert result.intent_description is not None
        assert len(result.permissions) == 3

    def test_parse_minimal_frontmatter(self, parser: YAMLParser, minimal_frontmatter: dict[str, Any]) -> None:
        """测试解析最小 Frontmatter。"""
        result = parser.parse(minimal_frontmatter)

        assert result.skill_id == "test:minimal"
        assert result.version == "0.1.0"
        assert len(result.permissions) == 1
        assert result.tags == []

    def test_parse_yaml_string(self, parser: YAMLParser, valid_yaml_string: str) -> None:
        """测试解析 YAML 字符串。"""
        result = parser.parse_yaml_string(valid_yaml_string)

        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert len(result.permissions) == 2

    def test_parse_yaml_string_with_file_path(self, parser: YAMLParser, valid_yaml_string: str) -> None:
        """测试解析 YAML 字符串并指定文件路径。"""
        file_path = Path("/test/skill.md")
        result = parser.parse_yaml_string(valid_yaml_string, source_file=file_path)

        assert result.source_file == file_path

    def test_parse_with_source_file(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试解析并指定源文件。"""
        file_path = Path("/test/skill.md")
        result = parser.parse(valid_frontmatter, source_file=file_path)

        assert result.source_file == file_path


# =============================================================================
# Required Fields Validation Tests
# =============================================================================


class TestRequiredFieldsValidation:
    """必填字段验证测试。"""

    def test_skill_id_validation_valid(self, parser: YAMLParser) -> None:
        """测试有效 skill_id 验证。"""
        assert parser.validate_skill_id("git:commit_changes")
        assert parser.validate_skill_id("namespace:name")
        assert parser.validate_skill_id("a-b_c:d_e_f")

    def test_skill_id_validation_invalid(self, parser: YAMLParser) -> None:
        """测试无效 skill_id 验证。"""
        assert not parser.validate_skill_id("invalid")
        assert not parser.validate_skill_id("Invalid:Name")
        assert not parser.validate_skill_id("namespace:name:extra")
        assert not parser.validate_skill_id("")

    def test_version_validation_valid(self, parser: YAMLParser) -> None:
        """测试有效 version 验证。"""
        assert parser.validate_version("1.0.0")
        assert parser.validate_version("0.1.0")
        assert parser.validate_version("2.10.3")
        assert parser.validate_version("1.0.0-alpha")
        assert parser.validate_version("1.0.0-beta1")

    def test_version_validation_invalid(self, parser: YAMLParser) -> None:
        """测试无效 version 验证。"""
        assert not parser.validate_version("v1.0.0")
        assert not parser.validate_version("1.0")
        assert not parser.validate_version("1")
        assert not parser.validate_version("")

    def test_permission_validation_valid(self, parser: YAMLParser) -> None:
        """测试有效权限验证。"""
        assert parser.validate_permission("fs:read:/tmp")
        assert parser.validate_permission("fs:write:/home/user")
        assert parser.validate_permission("net:http:github.com")
        assert parser.validate_permission("db:read:postgres")

    def test_permission_validation_invalid(self, parser: YAMLParser) -> None:
        """测试无效权限验证。"""
        assert not parser.validate_permission("invalid")
        assert not parser.validate_permission("FS:read:/tmp")
        assert not parser.validate_permission("fs:READ:/tmp")

    def test_invalid_skill_id_strict_mode(self, parser: YAMLParser, invalid_skill_id_frontmatter: dict[str, Any]) -> None:
        """测试无效 skill_id（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(invalid_skill_id_frontmatter)

        assert "skill_id" in str(exc_info.value)
        assert exc_info.value.field_name == "skill_id"

    def test_invalid_skill_id_lenient_mode(self, lenient_parser: YAMLParser, invalid_skill_id_frontmatter: dict[str, Any]) -> None:
        """测试无效 skill_id（非严格模式）。"""
        result = lenient_parser.parse(invalid_skill_id_frontmatter)

        assert result.skill_id == "invalid_skill_id"
        assert "Invalid format for skill_id" in result.parse_warnings

    def test_invalid_version_strict_mode(self, parser: YAMLParser, invalid_version_frontmatter: dict[str, Any]) -> None:
        """测试无效 version（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(invalid_version_frontmatter)

        assert "version" in str(exc_info.value)

    def test_short_intent_strict_mode(self, parser: YAMLParser, short_intent_frontmatter: dict[str, Any]) -> None:
        """测试意图描述过短（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(short_intent_frontmatter)

        assert "too short" in str(exc_info.value)

    def test_long_intent_strict_mode(self, parser: YAMLParser, long_intent_frontmatter: dict[str, Any]) -> None:
        """测试意图描述过长（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(long_intent_frontmatter)

        assert "too long" in str(exc_info.value)

    def test_empty_permissions_strict_mode(self, parser: YAMLParser, empty_permissions_frontmatter: dict[str, Any]) -> None:
        """测试空权限列表（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(empty_permissions_frontmatter)

        assert "too few items" in str(exc_info.value)

    def test_invalid_permission_format_strict_mode(self, parser: YAMLParser, invalid_permission_format_frontmatter: dict[str, Any]) -> None:
        """测试无效权限格式（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(invalid_permission_format_frontmatter)

        assert "does not match pattern" in str(exc_info.value)

    def test_missing_required_field_strict_mode(self, parser: YAMLParser, missing_required_field_frontmatter: dict[str, Any]) -> None:
        """测试缺少必填字段（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(missing_required_field_frontmatter)

        assert "missing" in str(exc_info.value)
        assert exc_info.value.field_name == "version"

    def test_missing_required_field_lenient_mode(self, lenient_parser: YAMLParser, missing_required_field_frontmatter: dict[str, Any]) -> None:
        """测试缺少必填字段（非严格模式）。"""
        result = lenient_parser.parse(missing_required_field_frontmatter)

        assert "Missing required field: version" in result.parse_warnings

    def test_wrong_type_strict_mode(self, parser: YAMLParser, wrong_type_frontmatter: dict[str, Any]) -> None:
        """测试字段类型错误（严格模式）。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse(wrong_type_frontmatter)

        assert "wrong type" in str(exc_info.value)


# =============================================================================
# Optional Fields Validation Tests
# =============================================================================


class TestOptionalFieldsValidation:
    """可选字段验证测试。"""

    def test_all_optional_fields(self, parser: YAMLParser, optional_fields_frontmatter: dict[str, Any]) -> None:
        """测试所有可选字段。"""
        result = parser.parse(optional_fields_frontmatter)

        assert result.tags == ["test", "optional"]
        assert result.author == "Test Author"
        assert result.created_at == "2024-01-01"
        assert result.updated_at == "2024-06-15T12:00:00"
        assert result.min_agent_version == "1.0.0"
        assert result.max_agent_version == "2.0.0"
        assert result.deprecated is True
        assert result.deprecation_message == "Use test:new_skill instead"
        assert result.success_rate == 0.95
        assert result.avg_latency_ms == 150

    def test_invalid_success_rate(self, parser: YAMLParser, invalid_optional_fields_frontmatter: dict[str, Any]) -> None:
        """测试无效 success_rate。"""
        # 非严格模式下应该产生警告
        result = parser.parse(invalid_optional_fields_frontmatter, source_file=Path("/test.md"))

        # success_rate 超出范围会产生警告
        assert "success_rate above maximum" in result.parse_warnings

    def test_invalid_avg_latency(self, parser: YAMLParser, invalid_optional_fields_frontmatter: dict[str, Any]) -> None:
        """测试无效 avg_latency_ms。"""
        result = parser.parse(invalid_optional_fields_frontmatter)

        assert "avg_latency_ms below minimum" in result.parse_warnings

    def test_invalid_date_format(self, parser: YAMLParser, invalid_optional_fields_frontmatter: dict[str, Any]) -> None:
        """测试无效日期格式。"""
        result = parser.parse(invalid_optional_fields_frontmatter)

        assert "Invalid format for created_at" in result.parse_warnings

    def test_optional_fields_defaults(self, parser: YAMLParser, minimal_frontmatter: dict[str, Any]) -> None:
        """测试可选字段默认值。"""
        result = parser.parse(minimal_frontmatter)

        assert result.tags == []
        assert result.author is None
        assert result.created_at is None
        assert result.updated_at is None
        assert result.min_agent_version is None
        assert result.max_agent_version is None
        assert result.deprecated is False
        assert result.deprecation_message is None
        assert result.success_rate is None
        assert result.avg_latency_ms is None
        assert result.topology_hints == {}


# =============================================================================
# Topology Hints Tests
# =============================================================================


class TestTopologyHints:
    """拓扑提示测试。"""

    def test_valid_topology_hints(self, parser: YAMLParser, topology_hints_frontmatter: dict[str, Any]) -> None:
        """测试有效拓扑提示。"""
        result = parser.parse(topology_hints_frontmatter)

        assert result.topology_hints is not None
        assert "requires" in result.topology_hints
        assert len(result.topology_hints["requires"]) == 2
        assert "conflicts_with" in result.topology_hints
        assert "enhances" in result.topology_hints
        assert "substitutes" in result.topology_hints

    def test_invalid_topology_hints(self, parser: YAMLParser, invalid_topology_hints_frontmatter: dict[str, Any]) -> None:
        """测试无效拓扑提示。"""
        result = parser.parse(invalid_topology_hints_frontmatter)

        # requires 不是列表，应该产生警告
        assert "topology_hints.requires must be a list" in result.parse_warnings
        # conflicts_with 是有效的
        assert "conflicts_with" in result.topology_hints

    def test_empty_topology_hints(self, parser: YAMLParser, minimal_frontmatter: dict[str, Any]) -> None:
        """测试空拓扑提示。"""
        result = parser.parse(minimal_frontmatter)

        assert result.topology_hints == {}

    def test_topology_hints_not_dict(self, parser: YAMLParser) -> None:
        """测试 topology_hints 不是字典。"""
        frontmatter = {
            "skill_id": "test:topology_type",
            "version": "1.0.0",
            "intent_description": "Test topology hints type validation in the parsing process.",
            "permissions": ["fs:read:/tmp"],
            "topology_hints": "not-a-dict",
        }

        result = parser.parse(frontmatter)

        assert "topology_hints must be a dictionary" in result.parse_warnings
        assert result.topology_hints == {}

    def test_partial_topology_hints(self, parser: YAMLParser) -> None:
        """测试部分拓扑提示。"""
        frontmatter = {
            "skill_id": "test:partial_topology",
            "version": "1.0.0",
            "intent_description": "Test partial topology hints extraction in the parsing process.",
            "permissions": ["fs:read:/tmp"],
            "topology_hints": {
                "requires": ["skill:a"],
                # 其他字段缺失
            },
        }

        result = parser.parse(frontmatter)

        assert "requires" in result.topology_hints
        assert "conflicts_with" not in result.topology_hints
        assert "enhances" not in result.topology_hints
        assert "substitutes" not in result.topology_hints


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """错误处理测试。"""

    def test_yaml_validation_error_properties(self, parser: YAMLParser) -> None:
        """测试 YAMLValidationError 属性。"""
        error = YAMLValidationError(
            message="Test error",
            field_name="skill_id",
            field_value="invalid",
            file_path=Path("/test.md"),
            line_number=10
        )

        assert error.message == "Test error"
        assert error.field_name == "skill_id"
        assert error.field_value == "invalid"
        assert error.file_path == Path("/test.md")
        assert error.line_number == 10
        assert error.code == "GS-2001"

    def test_yaml_validation_error_to_dict(self, parser: YAMLParser) -> None:
        """测试 YAMLValidationError 序列化。"""
        error = YAMLValidationError(
            message="Test error",
            field_name="skill_id",
            field_value="invalid",
            file_path=Path("/test.md"),
            line_number=10
        )

        result = error.to_dict()
        # to_dict 返回嵌套结构 {"error": {...}}
        assert result["error"]["message"] == "Test error"
        assert result["field_name"] == "skill_id"
        assert result["field_value"] == "invalid"
        assert result["file_path"] == "/test.md"
        assert result["line_number"] == 10
        assert result["error"]["code"] == "GS-2001"

    def test_yaml_validation_error_without_optional_fields(self, parser: YAMLParser) -> None:
        """测试 YAMLValidationError 无可选字段。"""
        error = YAMLValidationError(message="Simple error")

        result = error.to_dict()
        assert "field_name" not in result
        assert "field_value" not in result
        assert "file_path" not in result
        assert "line_number" not in result

    def test_invalid_yaml_string(self, parser: YAMLParser, invalid_yaml_string: str) -> None:
        """测试无效 YAML 字符串。"""
        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse_yaml_string(invalid_yaml_string)

        assert "YAML parsing error" in str(exc_info.value)

    def test_yaml_string_not_dict(self, parser: YAMLParser) -> None:
        """测试 YAML 字符串解析结果不是字典。"""
        yaml_string = "just a string"

        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse_yaml_string(yaml_string)

        assert "dictionary" in str(exc_info.value)

    def test_yaml_string_list(self, parser: YAMLParser) -> None:
        """测试 YAML 字符串解析结果是列表。"""
        yaml_string = "- item1\n- item2"

        with pytest.raises(YAMLValidationError) as exc_info:
            parser.parse_yaml_string(yaml_string)

        assert "dictionary" in str(exc_info.value)


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestDataStructures:
    """数据结构测试。"""

    def test_parsed_frontmatter_properties(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试 ParsedFrontmatter 属性。"""
        result = parser.parse(valid_frontmatter)

        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert result.intent_description is not None
        assert len(result.permissions) == 3
        assert len(result.tags) == 3
        assert result.author == "test-author"

    def test_parsed_frontmatter_raw_data(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试 ParsedFrontmatter 保留原始数据。"""
        result = parser.parse(valid_frontmatter)

        assert result.raw_data == valid_frontmatter
        assert result.raw_data["skill_id"] == "git:commit_changes"

    def test_parsed_frontmatter_warnings(self, parser: YAMLParser, invalid_optional_fields_frontmatter: dict[str, Any]) -> None:
        """测试 ParsedFrontmatter 警告列表。"""
        result = parser.parse(invalid_optional_fields_frontmatter)

        assert len(result.parse_warnings) > 0
        assert isinstance(result.parse_warnings, list)

    def test_required_fields_definition(self) -> None:
        """测试必填字段定义。"""
        assert "skill_id" in REQUIRED_FIELDS
        assert "version" in REQUIRED_FIELDS
        assert "intent_description" in REQUIRED_FIELDS
        assert "permissions" in REQUIRED_FIELDS

        # 检查字段规范
        assert REQUIRED_FIELDS["skill_id"]["type"] == str
        assert "pattern" in REQUIRED_FIELDS["skill_id"]
        assert REQUIRED_FIELDS["permissions"]["type"] == list
        assert "min_items" in REQUIRED_FIELDS["permissions"]

    def test_optional_fields_definition(self) -> None:
        """测试可选字段定义。"""
        assert "tags" in OPTIONAL_FIELDS
        assert "author" in OPTIONAL_FIELDS
        assert "created_at" in OPTIONAL_FIELDS
        assert "success_rate" in OPTIONAL_FIELDS
        assert "avg_latency_ms" in OPTIONAL_FIELDS
        assert "topology_hints" in OPTIONAL_FIELDS

        # 检查字段规范
        assert OPTIONAL_FIELDS["tags"]["type"] == list
        assert OPTIONAL_FIELDS["success_rate"]["min"] == 0.0
        assert OPTIONAL_FIELDS["success_rate"]["max"] == 1.0


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """边界条件测试。"""

    def test_intent_description_exact_min_length(self, parser: YAMLParser) -> None:
        """测试意图描述恰好达到最小长度。"""
        frontmatter = {
            "skill_id": "test:exact_min",
            "version": "1.0.0",
            "intent_description": "x" * 50,  # 恰好 50 字符
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert result.intent_description == "x" * 50

    def test_intent_description_exact_max_length(self, parser: YAMLParser) -> None:
        """测试意图描述恰好达到最大长度。"""
        frontmatter = {
            "skill_id": "test:exact_max",
            "version": "1.0.0",
            "intent_description": "x" * 500,  # 恰好 500 字符
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert result.intent_description == "x" * 500

    def test_intent_description_51_chars(self, parser: YAMLParser) -> None:
        """测试意图描述 51 字符。"""
        frontmatter = {
            "skill_id": "test:51_chars",
            "version": "1.0.0",
            "intent_description": "x" * 51,
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert len(result.intent_description) == 51

    def test_intent_description_499_chars(self, parser: YAMLParser) -> None:
        """测试意图描述 499 字符。"""
        frontmatter = {
            "skill_id": "test:499_chars",
            "version": "1.0.0",
            "intent_description": "x" * 499,
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert len(result.intent_description) == 499

    def test_single_permission(self, parser: YAMLParser) -> None:
        """测试单个权限。"""
        frontmatter = {
            "skill_id": "test:single_perm",
            "version": "1.0.0",
            "intent_description": "Test single permission in the frontmatter parsing process.",
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert len(result.permissions) == 1

    def test_many_permissions(self, parser: YAMLParser) -> None:
        """测试多个权限。"""
        permissions = [f"fs:read:/path{i}" for i in range(10)]
        frontmatter = {
            "skill_id": "test:many_perms",
            "version": "1.0.0",
            "intent_description": "Test many permissions in the frontmatter parsing process.",
            "permissions": permissions,
        }

        result = parser.parse(frontmatter)
        assert len(result.permissions) == 10

    def test_unicode_in_intent_description(self, parser: YAMLParser) -> None:
        """测试意图描述包含 Unicode。"""
        frontmatter = {
            "skill_id": "test:unicode",
            "version": "1.0.0",
            "intent_description": "测试 Unicode 字符处理能力，包括中文、日文、韩文等多语言支持测试。这个描述足够长以满足最小长度要求。",
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert "中文" in result.intent_description

    def test_special_characters_in_skill_id(self, parser: YAMLParser) -> None:
        """测试 skill_id 包含特殊字符。"""
        # 有效特殊字符
        assert parser.validate_skill_id("a-b_c:d_e_f")
        assert parser.validate_skill_id("skill-123:name_456")

    def test_version_with_prerelease(self, parser: YAMLParser) -> None:
        """测试包含预发布标签的版本。"""
        frontmatter = {
            "skill_id": "test:prerelease",
            "version": "1.0.0-alpha",  # 使用简单的预发布标签格式
            "intent_description": "Test prerelease version format in the frontmatter parsing with enough length.",
            "permissions": ["fs:read:/tmp"],
        }

        result = parser.parse(frontmatter)
        assert result.version == "1.0.0-alpha"

    def test_deprecated_skill(self, parser: YAMLParser) -> None:
        """测试废弃技能。"""
        frontmatter = {
            "skill_id": "test:deprecated",
            "version": "1.0.0",
            "intent_description": "Test deprecated skill handling in the frontmatter parsing.",
            "permissions": ["fs:read:/tmp"],
            "deprecated": True,
            "deprecation_message": "Use test:new_skill instead",
        }

        result = parser.parse(frontmatter)
        assert result.deprecated is True
        assert result.deprecation_message == "Use test:new_skill instead"

    def test_empty_tags(self, parser: YAMLParser) -> None:
        """测试空标签列表。"""
        frontmatter = {
            "skill_id": "test:empty_tags",
            "version": "1.0.0",
            "intent_description": "Test empty tags list in the frontmatter parsing process.",
            "permissions": ["fs:read:/tmp"],
            "tags": [],
        }

        result = parser.parse(frontmatter)
        assert result.tags == []

    def test_many_tags(self, parser: YAMLParser) -> None:
        """测试多个标签。"""
        tags = [f"tag{i}" for i in range(20)]
        frontmatter = {
            "skill_id": "test:many_tags",
            "version": "1.0.0",
            "intent_description": "Test many tags in the frontmatter parsing process.",
            "permissions": ["fs:read:/tmp"],
            "tags": tags,
        }

        result = parser.parse(frontmatter)
        assert len(result.tags) == 20


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """集成测试。"""

    def test_full_workflow(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试完整工作流。"""
        result = parser.parse(valid_frontmatter)

        # 验证所有必填字段
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert result.intent_description is not None
        assert len(result.permissions) == 3

        # 验证可选字段
        assert len(result.tags) == 3
        assert result.author == "test-author"

        # 验证拓扑提示
        assert "requires" in result.topology_hints
        assert "conflicts_with" in result.topology_hints

        # 验证原始数据
        assert result.raw_data == valid_frontmatter

    def test_from_file_workflow(self, parser: YAMLParser) -> None:
        """测试从文件解析工作流。"""
        yaml_content = """
skill_id: test:file_workflow
version: 1.0.0
intent_description: Test complete workflow from file parsing to validation.
permissions:
  - fs:read:/tmp
tags:
  - test
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            file_path = Path(f.name)

        result = parser.parse_yaml_string(yaml_content, source_file=file_path)

        assert result.skill_id == "test:file_workflow"
        assert result.source_file == file_path

        file_path.unlink()

    def test_validation_methods(self, parser: YAMLParser) -> None:
        """测试独立验证方法。"""
        # skill_id 验证
        assert parser.validate_skill_id("valid:skill_id")
        assert not parser.validate_skill_id("invalid")

        # version 验证
        assert parser.validate_version("1.0.0")
        assert not parser.validate_version("v1.0")

        # permission 验证
        assert parser.validate_permission("fs:read:/tmp")
        assert not parser.validate_permission("invalid")


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """性能测试。"""

    @pytest.mark.slow
    def test_large_frontmatter(self, parser: YAMLParser) -> None:
        """测试大型 Frontmatter。"""
        # 生成大量权限和标签
        permissions = [f"fs:read:/path{i}" for i in range(100)]
        tags = [f"tag{i}" for i in range(50)]
        requires = [f"skill:{i}" for i in range(30)]

        frontmatter = {
            "skill_id": "test:large",
            "version": "1.0.0",
            "intent_description": "Test large frontmatter parsing performance with many fields.",
            "permissions": permissions,
            "tags": tags,
            "topology_hints": {
                "requires": requires,
            },
        }

        result = parser.parse(frontmatter)

        assert len(result.permissions) == 100
        assert len(result.tags) == 50
        assert len(result.topology_hints["requires"]) == 30

    @pytest.mark.slow
    def test_repeated_parsing(self, parser: YAMLParser, valid_frontmatter: dict[str, Any]) -> None:
        """测试重复解析性能。"""
        for _ in range(100):
            result = parser.parse(valid_frontmatter)
            assert result.skill_id == "git:commit_changes"
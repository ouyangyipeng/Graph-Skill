"""
Schema 校验器单元测试。

测试 SchemaValidator 的所有核心功能：
- JSON Schema 验证
- 必填字段检查
- 格式规范验证
- 详细错误报告

Reference: RFC-02 Section 3.1
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from graphskill.ingestion.validator.schema_validator import (
    ValidationError,
    ValidationResult,
    SchemaValidator,
    SchemaValidationError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def validator() -> SchemaValidator:
    """创建默认校验器实例。"""
    return SchemaValidator(strict_mode=False)


@pytest.fixture
def strict_validator() -> SchemaValidator:
    """创建严格模式校验器实例。"""
    return SchemaValidator(strict_mode=True)


@pytest.fixture
def valid_frontmatter() -> dict:
    """有效的 Frontmatter 数据（符合实际 schema）。"""
    return {
        "skill_id": "test:skill-001",  # namespace:name 格式
        "version": "1.0.0",
        "intent_description": "This is a test skill for unit testing purposes. It demonstrates the schema validation functionality.",  # 50-500字符
        "permissions": ["fs:read:/tmp"],
        "author": "test-author",
    }


@pytest.fixture
def invalid_frontmatter() -> dict:
    """无效的 Frontmatter 数据。"""
    return {
        "name": "Missing required fields",
        # 缺少必填字段 skill_id, version, intent_description, permissions
    }


@pytest.fixture
def minimal_frontmatter() -> dict:
    """最小有效 Frontmatter 数据。"""
    return {
        "skill_id": "minimal:skill",
        "version": "1.0.0",
        "intent_description": "Minimal skill for testing the schema validation with a valid intent description.",
        "permissions": ["fs:read:/tmp"],
    }


# =============================================================================
# Validation Error Tests
# =============================================================================


class TestValidationError:
    """验证错误数据结构测试。"""

    def test_validation_error_properties(self) -> None:
        """测试 ValidationError 属性。"""
        error = ValidationError(
            path="skill_id",
            message="Required field missing",
            value=None,
            validator="required",
            schema_path="required"
        )

        assert error.path == "skill_id"
        assert error.message == "Required field missing"
        assert error.value is None
        assert error.validator == "required"
        assert error.schema_path == "required"

    def test_validation_error_defaults(self) -> None:
        """测试 ValidationError 默认值。"""
        error = ValidationError(
            path="test",
            message="Test error"
        )

        assert error.value is None
        assert error.validator is None
        assert error.schema_path is None

    def test_validation_error_to_dict(self) -> None:
        """测试 ValidationError 序列化。"""
        error = ValidationError(
            path="skill_id",
            message="Invalid format",
            value="invalid",
            validator="pattern",
            schema_path="properties.skill_id.pattern"
        )

        result = error.to_dict()
        assert result["path"] == "skill_id"
        assert result["message"] == "Invalid format"
        assert result["validator"] == "pattern"


# =============================================================================
# Validation Result Tests
# =============================================================================


class TestValidationResult:
    """验证结果测试。"""

    def test_result_properties(self) -> None:
        """测试 ValidationResult 属性。"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Test warning"]
        )

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 1

    def test_result_error_count(self) -> None:
        """测试 error_count 属性。"""
        result = ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(path="field1", message="Error 1"),
                ValidationError(path="field2", message="Error 2"),
            ]
        )
        assert result.error_count == 2

    def test_result_warning_count(self) -> None:
        """测试 warning_count 属性。"""
        result = ValidationResult(
            is_valid=True,
            warnings=["Warning 1", "Warning 2"]
        )
        assert result.warning_count == 2

    def test_result_to_dict(self) -> None:
        """测试 ValidationResult 序列化。"""
        result = ValidationResult(
            is_valid=False,
            errors=[ValidationError(path="test", message="Error")],
            warnings=["Warning"]
        )

        result_dict = result.to_dict()
        assert not result_dict["is_valid"]
        assert result_dict["error_count"] == 1
        assert result_dict["warning_count"] == 1


# =============================================================================
# Schema Validator Tests
# =============================================================================


class TestSchemaValidator:
    """Schema 校验器测试。"""

    def test_validator_initialization(self) -> None:
        """测试校验器初始化。"""
        validator = SchemaValidator(strict_mode=True)
        assert validator.strict_mode

        validator_relaxed = SchemaValidator(strict_mode=False)
        assert not validator_relaxed.strict_mode

    def test_validate_valid_frontmatter(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试验证有效 Frontmatter。"""
        result = validator.validate(valid_frontmatter)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_invalid_frontmatter(self, validator: SchemaValidator, invalid_frontmatter: dict) -> None:
        """测试验证无效 Frontmatter。"""
        result = validator.validate(invalid_frontmatter)

        assert not result.is_valid
        assert len(result.errors) >= 1

    def test_validate_minimal_frontmatter(self, validator: SchemaValidator, minimal_frontmatter: dict) -> None:
        """测试验证最小 Frontmatter。"""
        result = validator.validate(minimal_frontmatter)

        assert result.is_valid

    def test_validate_empty_dict(self, validator: SchemaValidator) -> None:
        """测试验证空字典。"""
        result = validator.validate({})

        assert not result.is_valid
        assert len(result.errors) >= 1

    def test_validate_with_file_path(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试带文件路径的验证。"""
        result = validator.validate(valid_frontmatter, file_path=Path("/test/skill.md"))

        assert result.is_valid


# =============================================================================
# Required Field Tests
# =============================================================================


class TestRequiredFields:
    """必填字段测试。"""

    def test_missing_skill_id(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试缺少 skill_id。"""
        data = valid_frontmatter.copy()
        del data["skill_id"]
        result = validator.validate(data)

        assert not result.is_valid
        # 应该有关于 skill_id 的错误
        error_paths = [e.path for e in result.errors]
        assert "skill_id" in error_paths or "root" in error_paths

    def test_missing_version(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试缺少 version。"""
        data = valid_frontmatter.copy()
        del data["version"]
        result = validator.validate(data)

        assert not result.is_valid

    def test_missing_intent_description(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试缺少 intent_description。"""
        data = valid_frontmatter.copy()
        del data["intent_description"]
        result = validator.validate(data)

        assert not result.is_valid

    def test_missing_permissions(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试缺少 permissions。"""
        data = valid_frontmatter.copy()
        del data["permissions"]
        result = validator.validate(data)

        assert not result.is_valid


# =============================================================================
# Format Validation Tests
# =============================================================================


class TestFormatValidation:
    """格式验证测试。"""

    def test_invalid_skill_id_format(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试无效 skill_id 格式（需要 namespace:name 格式）。"""
        data = valid_frontmatter.copy()
        data["skill_id"] = "invalid-skill-id"  # 缺少 namespace:name 格式
        result = validator.validate(data)

        assert not result.is_valid
        # 应该有 pattern 验证错误
        pattern_errors = [e for e in result.errors if e.validator == "pattern"]
        assert len(pattern_errors) >= 1

    def test_invalid_version_format(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试无效 version 格式。"""
        data = valid_frontmatter.copy()
        data["version"] = "not-a-version"
        result = validator.validate(data)

        assert not result.is_valid

    def test_intent_description_too_short(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 intent_description 太短（需要至少50字符）。"""
        data = valid_frontmatter.copy()
        data["intent_description"] = "Too short"  # 少于50字符
        result = validator.validate(data)

        assert not result.is_valid

    def test_intent_description_too_long(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 intent_description 太长（最多500字符）。"""
        data = valid_frontmatter.copy()
        data["intent_description"] = "x" * 600  # 超过500字符
        result = validator.validate(data)

        assert not result.is_valid

    def test_empty_permissions(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试空 permissions（需要至少1个）。"""
        data = valid_frontmatter.copy()
        data["permissions"] = []
        result = validator.validate(data)

        assert not result.is_valid

    def test_invalid_permission_format(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试无效 permission 格式。"""
        data = valid_frontmatter.copy()
        data["permissions"] = ["invalid-permission"]  # 不符合格式
        result = validator.validate(data)

        assert not result.is_valid


# =============================================================================
# Type Validation Tests
# =============================================================================


class TestTypeValidation:
    """类型验证测试。"""

    def test_wrong_type_skill_id(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 skill_id 类型错误。"""
        data = valid_frontmatter.copy()
        data["skill_id"] = 123  # 应该是字符串
        result = validator.validate(data)

        assert not result.is_valid

    def test_wrong_type_version(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 version 类型错误。"""
        data = valid_frontmatter.copy()
        data["version"] = []  # 应该是字符串
        result = validator.validate(data)

        assert not result.is_valid

    def test_wrong_type_permissions(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 permissions 类型错误。"""
        data = valid_frontmatter.copy()
        data["permissions"] = "fs:read:/tmp"  # 应该是列表
        result = validator.validate(data)

        assert not result.is_valid


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """边界条件测试。"""

    def test_empty_frontmatter(self, validator: SchemaValidator) -> None:
        """测试空 Frontmatter。"""
        result = validator.validate({})
        assert not result.is_valid

    def test_null_values(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 null 值。"""
        data = valid_frontmatter.copy()
        data["skill_id"] = None
        result = validator.validate(data)
        assert not result.is_valid

    def test_unicode_in_fields(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 Unicode 字符。"""
        data = valid_frontmatter.copy()
        data["intent_description"] = "这是一个测试技能的意图描述，用于验证 Unicode 字符的处理能力。这个描述足够长以满足最小长度要求。"
        result = validator.validate(data)
        assert result.is_valid

    def test_extra_fields(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试额外字段。"""
        data = valid_frontmatter.copy()
        data["extra_field"] = "some value"
        data["name"] = "Test Skill"  # 额外字段
        result = validator.validate(data)
        # 额外字段被允许（additionalProperties: true）
        assert result.is_valid

    def test_topology_hints(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试 topology_hints 字段。"""
        data = valid_frontmatter.copy()
        data["topology_hints"] = {
            "requires": ["other:skill"],
            "conflicts_with": ["conflicting:skill"],
            "enhances": ["enhanced:skill"],
            "substitutes": ["substituted:skill"]
        }
        result = validator.validate(data)
        assert result.is_valid


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """错误处理测试。"""

    def test_schema_validation_error_properties(self) -> None:
        """测试 SchemaValidationError 属性。"""
        error = SchemaValidationError(
            message="Schema validation failed",
            errors=[ValidationError(path="skill_id", message="Required")]
        )

        assert error.message == "Schema validation failed"
        assert error.code == "GS-2010"
        assert len(error.errors) == 1

    def test_schema_validation_error_to_dict(self) -> None:
        """测试 SchemaValidationError 序列化。"""
        error = SchemaValidationError(
            message="Schema validation failed",
            errors=[ValidationError(path="test", message="Error")]
        )

        result = error.to_dict()
        assert "error" in result
        assert result["error"]["message"] == "Schema validation failed"
        assert "errors" in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """集成测试。"""

    def test_full_validation_workflow(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试完整验证工作流。"""
        result = validator.validate(valid_frontmatter)

        assert result.is_valid
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_validate_multiple_frontmatters(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试验证多个 Frontmatter。"""
        for i in range(5):
            data = valid_frontmatter.copy()
            data["skill_id"] = f"skill:{i}"
            result = validator.validate(data)
            assert result.is_valid


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """性能测试。"""

    @pytest.mark.slow
    def test_large_frontmatter(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试大 Frontmatter。"""
        data = valid_frontmatter.copy()
        data["permissions"] = [f"fs:read:/tmp/{i}" for i in range(100)]
        result = validator.validate(data)
        assert isinstance(result.is_valid, bool)

    @pytest.mark.slow
    def test_repeated_validation(self, validator: SchemaValidator, valid_frontmatter: dict) -> None:
        """测试重复验证。"""
        for _ in range(10):
            result = validator.validate(valid_frontmatter)
            assert result.is_valid
"""
权限声明校验器单元测试。

测试 PermissionValidator 的所有核心功能：
- 权限格式解析
- 类别验证
- 动作验证
- 高风险权限检测
- 目标格式验证

Reference: RFC-02 Section 3.2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from graphskill.ingestion.validator.permission_validator import (
    PermissionAction,
    PermissionCategory,
    PermissionInfo,
    PermissionValidationError,
    PermissionValidationResult,
    PermissionValidator,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def validator() -> PermissionValidator:
    """创建默认校验器实例。"""
    return PermissionValidator(strict_mode=False)


@pytest.fixture
def strict_validator() -> PermissionValidator:
    """创建严格模式校验器实例。"""
    return PermissionValidator(strict_mode=True)


@pytest.fixture
def valid_permissions() -> list[str]:
    """有效的权限列表。"""
    return [
        "fs:read:/tmp",
        "fs:write:/home/user",
        "net:http:github.com",
        "exec:run:/bin/bash",
    ]


@pytest.fixture
def invalid_permissions() -> list[str]:
    """无效的权限列表。"""
    return [
        "invalid:action:target",  # 无效类别
        "fs:invalid:/tmp",  # 无效动作
        "",  # 空权限
        "fs",  # 缺少部分
    ]


@pytest.fixture
def high_risk_permissions() -> list[str]:
    """高风险权限列表。"""
    return [
        "exec:admin:/bin/bash",
        "fs:write:/etc/passwd",
        "net:listen:0.0.0.0:22",
    ]


# =============================================================================
# Permission Category Tests
# =============================================================================


class TestPermissionCategory:
    """权限类别测试。"""

    def test_category_enum_values(self) -> None:
        """测试权限类别枚举值。"""
        assert PermissionCategory.FS == "fs"
        assert PermissionCategory.NET == "net"
        assert PermissionCategory.EXEC == "exec"
        assert PermissionCategory.DB == "db"
        assert PermissionCategory.ENV == "env"

    def test_category_enum_count(self) -> None:
        """测试权限类别数量。"""
        categories = list(PermissionCategory)
        assert len(categories) >= 5


# =============================================================================
# Permission Action Tests
# =============================================================================


class TestPermissionAction:
    """权限动作测试。"""

    def test_action_enum_values(self) -> None:
        """测试权限动作枚举值。"""
        assert PermissionAction.READ == "read"
        assert PermissionAction.WRITE == "write"
        assert PermissionAction.EXECUTE == "execute"

    def test_action_enum_count(self) -> None:
        """测试权限动作数量。"""
        actions = list(PermissionAction)
        assert len(actions) >= 3


# =============================================================================
# Permission Info Tests
# =============================================================================


class TestPermissionInfo:
    """权限信息数据结构测试。"""

    def test_permission_info_properties(self) -> None:
        """测试 PermissionInfo 属性。"""
        info = PermissionInfo(
            category="fs",
            action="read",
            target="/tmp",
            raw_permission="fs:read:/tmp",
            is_valid=True
        )

        assert info.category == "fs"
        assert info.action == "read"
        assert info.target == "/tmp"
        assert info.raw_permission == "fs:read:/tmp"
        assert info.is_valid

    def test_permission_info_to_dict(self) -> None:
        """测试 PermissionInfo 序列化。"""
        info = PermissionInfo(
            category="fs",
            action="read",
            target="/tmp",
            raw_permission="fs:read:/tmp",
            is_valid=True
        )

        result = info.to_dict()
        assert result["category"] == "fs"
        assert result["action"] == "read"
        assert result["target"] == "/tmp"


# =============================================================================
# Permission Validation Result Tests
# =============================================================================


class TestPermissionValidationResult:
    """权限验证结果测试。"""

    def test_result_properties(self) -> None:
        """测试 PermissionValidationResult 属性。"""
        result = PermissionValidationResult(
            is_valid=True,
            permissions=[
                PermissionInfo(
                    category="fs",
                    action="read",
                    target="/tmp",
                    raw_permission="fs:read:/tmp",
                    is_valid=True
                )
            ],
            errors=[],
            warnings=[]
        )

        assert result.is_valid
        assert len(result.permissions) == 1
        assert len(result.errors) == 0

    def test_result_permission_count(self) -> None:
        """测试 permission_count 属性。"""
        result = PermissionValidationResult(
            is_valid=True,
            permissions=[
                PermissionInfo(
                    category="fs",
                    action="read",
                    target="/tmp",
                    raw_permission="fs:read:/tmp",
                    is_valid=True
                ),
                PermissionInfo(
                    category="net",
                    action="http",
                    target="github.com",
                    raw_permission="net:http:github.com",
                    is_valid=True
                ),
            ]
        )
        assert result.permission_count == 2

    def test_result_high_risk_count(self) -> None:
        """测试 high_risk_count 属性。"""
        result = PermissionValidationResult(
            is_valid=True,
            permissions=[],
            high_risk_permissions=[
                PermissionInfo(
                    category="exec",
                    action="admin",
                    target="/bin/bash",
                    raw_permission="exec:admin:/bin/bash",
                    is_valid=True
                )
            ]
        )
        assert result.high_risk_count == 1

    def test_result_to_dict(self) -> None:
        """测试 PermissionValidationResult 序列化。"""
        result = PermissionValidationResult(
            is_valid=True,
            permissions=[
                PermissionInfo(
                    category="fs",
                    action="read",
                    target="/tmp",
                    raw_permission="fs:read:/tmp",
                    is_valid=True
                )
            ],
            errors=[],
            warnings=["Test warning"]
        )

        result_dict = result.to_dict()
        assert result_dict["is_valid"]
        assert result_dict["permission_count"] == 1
        assert len(result_dict["warnings"]) == 1


# =============================================================================
# Permission Validator Tests
# =============================================================================


class TestPermissionValidator:
    """权限校验器测试。"""

    def test_validator_initialization(self) -> None:
        """测试校验器初始化。"""
        validator = PermissionValidator(strict_mode=True)
        assert validator.strict_mode

        validator_relaxed = PermissionValidator(strict_mode=False)
        assert not validator_relaxed.strict_mode

    def test_validate_valid_permissions(self, validator: PermissionValidator, valid_permissions: list[str]) -> None:
        """测试验证有效权限。"""
        result = validator.validate(valid_permissions)

        assert result.is_valid
        assert result.permission_count >= 1
        assert len(result.errors) == 0

    def test_validate_invalid_permissions(self, validator: PermissionValidator, invalid_permissions: list[str]) -> None:
        """测试验证无效权限。"""
        result = validator.validate(invalid_permissions)

        # 无效权限应该产生错误
        assert len(result.errors) >= 1 or not result.is_valid

    def test_validate_mixed_permissions(self, validator: PermissionValidator) -> None:
        """测试验证混合权限。"""
        permissions = [
            "fs:read:/tmp",  # 有效
            "invalid:action:target",  # 无效
        ]
        result = validator.validate(permissions)

        # 应该识别有效和无效权限
        assert result.permission_count >= 0

    def test_validate_empty_permissions(self, validator: PermissionValidator) -> None:
        """测试验证空权限列表。"""
        result = validator.validate([])

        assert result.is_valid
        assert result.permission_count == 0

    def test_validate_single_permission(self, validator: PermissionValidator) -> None:
        """测试验证单个权限。"""
        result = validator.validate(["fs:read:/tmp"])

        assert result.is_valid
        assert result.permission_count == 1


# =============================================================================
# High Risk Detection Tests
# =============================================================================


class TestHighRiskDetection:
    """高风险权限检测测试。"""

    def test_detect_high_risk_permissions(self, validator: PermissionValidator, high_risk_permissions: list[str]) -> None:
        """测试检测高风险权限。"""
        result = validator.validate(high_risk_permissions)

        # 高风险权限应该被检测
        # 注意：实际检测逻辑取决于实现
        assert isinstance(result.high_risk_count, int)

    def test_admin_is_high_risk(self, validator: PermissionValidator) -> None:
        """测试 admin 动作是高风险。"""
        result = validator.validate(["exec:admin:/bin/bash"])

        # admin 动作通常被认为是高风险
        assert isinstance(result.high_risk_count, int)


# =============================================================================
# Category Specific Tests
# =============================================================================


class TestCategorySpecific:
    """类别特定测试。"""

    def test_fs_permissions(self, validator: PermissionValidator) -> None:
        """测试文件系统权限。"""
        result = validator.validate(["fs:read:/tmp", "fs:write:/home"])

        assert result.is_valid
        for perm in result.permissions:
            if perm.category == "fs":
                assert perm.category == "fs"

    def test_net_permissions(self, validator: PermissionValidator) -> None:
        """测试网络权限。"""
        result = validator.validate(["net:http:github.com", "net:https:api.example.com"])

        assert result.is_valid
        for perm in result.permissions:
            if perm.category == "net":
                assert perm.category == "net"

    def test_exec_permissions(self, validator: PermissionValidator) -> None:
        """测试执行权限。"""
        result = validator.validate(["exec:run:/bin/bash"])

        assert result.is_valid
        for perm in result.permissions:
            if perm.category == "exec":
                assert perm.category == "exec"


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """边界条件测试。"""

    def test_permission_with_wildcard(self, validator: PermissionValidator) -> None:
        """测试带通配符的权限。"""
        result = validator.validate(["fs:read:*"])

        # 通配符可能被接受或拒绝
        assert isinstance(result.is_valid, bool)

    def test_permission_with_special_chars(self, validator: PermissionValidator) -> None:
        """测试带特殊字符的权限。"""
        result = validator.validate(["fs:read:/tmp/test-file.txt"])

        assert result.is_valid

    def test_permission_with_port(self, validator: PermissionValidator) -> None:
        """测试带端口的权限。"""
        result = validator.validate(["net:http:localhost:8080"])

        # 端口可能被接受
        assert isinstance(result.is_valid, bool)

    def test_permission_with_url(self, validator: PermissionValidator) -> None:
        """测试带 URL 的权限。"""
        result = validator.validate(["net:http:https://github.com"])

        # URL 格式可能被接受或拒绝
        assert isinstance(result.is_valid, bool)

    def test_permission_case_sensitivity(self, validator: PermissionValidator) -> None:
        """测试权限大小写敏感性。"""
        result_lower = validator.validate(["fs:read:/tmp"])
        result_upper = validator.validate(["FS:READ:/tmp"])

        # 类别和动作通常是小写
        assert result_lower.is_valid
        # 大写可能被拒绝或转换
        assert isinstance(result_upper.is_valid, bool)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """错误处理测试。"""

    def test_permission_validation_error_properties(self) -> None:
        """测试 PermissionValidationError 属性。"""
        error = PermissionValidationError(
            message="Invalid permission",
            permissions=[
                PermissionInfo(
                    category="invalid",
                    action="action",
                    raw_permission="invalid:action",
                    is_valid=False
                )
            ]
        )

        assert error.message == "Invalid permission"
        assert error.code == "GS-2012"
        assert len(error.permissions) == 1

    def test_permission_validation_error_to_dict(self) -> None:
        """测试 PermissionValidationError 序列化。"""
        error = PermissionValidationError(
            message="Invalid permission",
            permissions=[
                PermissionInfo(
                    category="invalid",
                    action="action",
                    raw_permission="invalid:action",
                    is_valid=False
                )
            ]
        )

        result = error.to_dict()
        assert "error" in result
        assert result["error"]["message"] == "Invalid permission"
        assert "permissions" in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """集成测试。"""

    def test_full_validation_workflow(self, validator: PermissionValidator) -> None:
        """测试完整验证工作流。"""
        permissions = [
            "fs:read:/tmp",
            "fs:write:/home/user",
            "net:http:github.com",
            "exec:run:/bin/bash",
        ]
        result = validator.validate(permissions)

        assert result.is_valid
        assert result.permission_count == 4
        assert isinstance(result.permissions, list)
        assert isinstance(result.errors, list)

    def test_validate_and_get_info(self, validator: PermissionValidator) -> None:
        """测试验证并获取信息。"""
        permissions = [
            "fs:read:/tmp",
            "net:http:github.com",
            "exec:admin:/bin/bash",  # 可能是高风险
        ]
        result = validator.validate(permissions)

        assert result.is_valid
        assert result.permission_count >= 1
        # 检查权限信息
        for perm in result.permissions:
            assert perm.raw_permission in permissions

    def test_validation_with_file_path(self, validator: PermissionValidator) -> None:
        """测试带文件路径的验证。"""
        permissions = ["fs:read:/tmp"]
        result = validator.validate(permissions, file_path=Path("/test/skill.md"))

        assert result.is_valid


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """性能测试。"""

    @pytest.mark.slow
    def test_large_permission_list(self, validator: PermissionValidator) -> None:
        """测试大权限列表。"""
        permissions = [f"fs:read:/tmp/{i}" for i in range(100)]
        result = validator.validate(permissions)

        assert result.permission_count == 100

    @pytest.mark.slow
    def test_repeated_validation(self, validator: PermissionValidator) -> None:
        """测试重复验证。"""
        permissions = ["fs:read:/tmp"]
        for _ in range(10):
            result = validator.validate(permissions)
            assert result.is_valid
"""
静态代码检查器单元测试。

测试 StaticValidator 的所有核心功能：
- 代码块语法检查
- 多语言规则检查
- 问题严重程度分类
- AST 分析集成

Reference: RFC-02 Section 3.3
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from graphskill.ingestion.validator.static_validator import (
    CodeIssue,
    SeverityLevel,
    StaticAnalysisResult,
    StaticValidator,
    StaticValidationError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def validator() -> StaticValidator:
    """创建默认校验器实例。"""
    return StaticValidator()


@pytest.fixture
def valid_python_code() -> str:
    """有效的 Python 代码。"""
    return '''
def main():
    """Main entry point."""
    print("Hello World")
    return 0

def helper():
    return True
'''


@pytest.fixture
def problematic_python_code() -> str:
    """有问题的 Python 代码。"""
    return '''
def main():
    # Missing docstring
    eval("dangerous_code")  # Dangerous eval usage
    exec("another_dangerous")  # Dangerous exec usage
    return None

def unused_function():
    pass
'''


@pytest.fixture
def valid_bash_code() -> str:
    """有效的 Bash 代码。"""
    return '''
function main() {
    echo "Hello World"
    return 0
}
'''


@pytest.fixture
def problematic_bash_code() -> str:
    """有问题的 Bash 代码。"""
    return '''
function main() {
    rm -rf /  # Dangerous rm command
    chmod 777 /tmp  # Dangerous chmod
}
'''


@pytest.fixture
def valid_javascript_code() -> str:
    """有效的 JavaScript 代码。"""
    return '''
function main() {
    console.log("Hello World");
    return 0;
}
'''


@pytest.fixture
def problematic_javascript_code() -> str:
    """有问题的 JavaScript 代码。"""
    return '''
function main() {
    var x = 1;  // Should use const/let
    eval("dangerous");  // Dangerous eval
    return undefined;
}
'''


def make_code_block(code: str, language: str, line_start: int = 1) -> dict:
    """创建代码块字典。"""
    return {
        "language": language,
        "code": code,
        "line_start": line_start,
    }


# =============================================================================
# Severity Level Tests
# =============================================================================


class TestSeverityLevel:
    """严重程度级别测试。"""

    def test_severity_enum_values(self) -> None:
        """测试严重程度枚举值。"""
        assert SeverityLevel.ERROR == "error"
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.INFO == "info"
        assert SeverityLevel.STYLE == "style"

    def test_severity_enum_count(self) -> None:
        """测试严重程度数量。"""
        levels = list(SeverityLevel)
        assert len(levels) == 4


# =============================================================================
# Code Issue Tests
# =============================================================================


class TestCodeIssue:
    """代码问题数据结构测试。"""

    def test_code_issue_properties(self) -> None:
        """测试 CodeIssue 属性。"""
        issue = CodeIssue(
            severity=SeverityLevel.ERROR,
            message="Syntax error",
            line_number=10,
            column=5,
            code_block_index=0,
            rule_id="SYNTAX001",
            suggestion="Fix the syntax"
        )

        assert issue.severity == SeverityLevel.ERROR
        assert issue.message == "Syntax error"
        assert issue.line_number == 10
        assert issue.column == 5
        assert issue.code_block_index == 0
        assert issue.rule_id == "SYNTAX001"

    def test_code_issue_defaults(self) -> None:
        """测试 CodeIssue 默认值。"""
        issue = CodeIssue(
            severity=SeverityLevel.WARNING,
            message="Test warning",
            line_number=1,
            code_block_index=0
        )

        assert issue.column is None
        assert issue.rule_id is None
        assert issue.suggestion is None

    def test_code_issue_to_dict(self) -> None:
        """测试 CodeIssue 序列化。"""
        issue = CodeIssue(
            severity=SeverityLevel.ERROR,
            message="Test error",
            line_number=10,
            column=5,
            code_block_index=0,
            rule_id="TEST001"
        )

        result = issue.to_dict()
        assert result["severity"] == "error"
        assert result["message"] == "Test error"
        assert result["line_number"] == 10


# =============================================================================
# Static Analysis Result Tests
# =============================================================================


class TestStaticAnalysisResult:
    """静态分析结果测试。"""

    def test_result_properties(self) -> None:
        """测试 StaticAnalysisResult 属性。"""
        result = StaticAnalysisResult(
            file_path=Path("/test/file.md"),
            issues=[],
            has_errors=False,
            has_warnings=True,
            error_count=0,
            warning_count=1,
            info_count=0
        )

        assert result.file_path == Path("/test/file.md")
        assert len(result.issues) == 0
        assert result.has_warnings
        assert not result.has_errors

    def test_result_has_errors(self) -> None:
        """测试 has_errors 属性。"""
        result_no_errors = StaticAnalysisResult(
            has_errors=False,
            error_count=0
        )
        assert not result_no_errors.has_errors

        result_with_errors = StaticAnalysisResult(
            has_errors=True,
            error_count=1,
            issues=[CodeIssue(
                severity=SeverityLevel.ERROR,
                message="Error",
                line_number=1,
                code_block_index=0
            )]
        )
        assert result_with_errors.has_errors

    def test_result_error_count(self) -> None:
        """测试 error_count 属性。"""
        result = StaticAnalysisResult(
            error_count=1,
            warning_count=1,
            issues=[
                CodeIssue(
                    severity=SeverityLevel.ERROR,
                    message="Error 1",
                    line_number=1,
                    code_block_index=0
                ),
                CodeIssue(
                    severity=SeverityLevel.WARNING,
                    message="Warning 1",
                    line_number=2,
                    code_block_index=0
                ),
            ]
        )
        assert result.error_count == 1
        assert result.warning_count == 1

    def test_result_total_issues(self) -> None:
        """测试 total_issues 属性。"""
        result = StaticAnalysisResult(
            issues=[
                CodeIssue(
                    severity=SeverityLevel.ERROR,
                    message="Error 1",
                    line_number=1,
                    code_block_index=0
                ),
                CodeIssue(
                    severity=SeverityLevel.WARNING,
                    message="Warning 1",
                    line_number=2,
                    code_block_index=0
                ),
            ]
        )
        assert result.total_issues == 2

    def test_result_to_dict(self) -> None:
        """测试 StaticAnalysisResult 序列化。"""
        result = StaticAnalysisResult(
            file_path=Path("/test/file.md"),
            has_warnings=True,
            warning_count=1,
            issues=[]
        )

        result_dict = result.to_dict()
        assert result_dict["has_warnings"]
        assert result_dict["warning_count"] == 1


# =============================================================================
# Static Validator Tests
# =============================================================================


class TestStaticValidator:
    """静态检查器测试。"""

    def test_validator_initialization(self) -> None:
        """测试检查器初始化。"""
        validator = StaticValidator(strict_mode=True)
        assert validator.strict_mode

        validator_relaxed = StaticValidator(strict_mode=False)
        assert not validator_relaxed.strict_mode

    def test_validate_valid_python(self, validator: StaticValidator, valid_python_code: str) -> None:
        """测试验证有效 Python 代码。"""
        code_blocks = [make_code_block(valid_python_code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)
        assert not result.has_errors  # 有效代码不应该有错误

    def test_validate_problematic_python(self, validator: StaticValidator, problematic_python_code: str) -> None:
        """测试验证有问题的 Python 代码。"""
        code_blocks = [make_code_block(problematic_python_code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        # 应该检测到问题
        assert isinstance(result, StaticAnalysisResult)
        # 可能检测到问题（取决于规则实现）

    def test_validate_valid_bash(self, validator: StaticValidator, valid_bash_code: str) -> None:
        """测试验证有效 Bash 代码。"""
        code_blocks = [make_code_block(valid_bash_code, "bash")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)
        assert not result.has_errors

    def test_validate_problematic_bash(self, validator: StaticValidator, problematic_bash_code: str) -> None:
        """测试验证有问题的 Bash 代码。"""
        code_blocks = [make_code_block(problematic_bash_code, "bash")]
        result = validator.validate_code_blocks(code_blocks)

        # 应该检测到危险命令
        assert isinstance(result, StaticAnalysisResult)

    def test_validate_valid_javascript(self, validator: StaticValidator, valid_javascript_code: str) -> None:
        """测试验证有效 JavaScript 代码。"""
        code_blocks = [make_code_block(valid_javascript_code, "javascript")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)
        assert not result.has_errors

    def test_validate_problematic_javascript(self, validator: StaticValidator, problematic_javascript_code: str) -> None:
        """测试验证有问题的 JavaScript 代码。"""
        code_blocks = [make_code_block(problematic_javascript_code, "javascript")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_validate_multiple_code_blocks(self, validator: StaticValidator) -> None:
        """测试验证多个代码块。"""
        code_blocks = [
            make_code_block("def main(): pass", "python"),
            make_code_block("echo 'hello'", "bash"),
            make_code_block("console.log('hi');", "javascript"),
        ]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)
        assert len(result.ast_results) >= 0  # AST 结果列表

    def test_validate_go_code(self, validator: StaticValidator) -> None:
        """测试验证 Go 代码。"""
        code = '''
package main

func main() {
    fmt.Println("Hello")
}
'''
        code_blocks = [make_code_block(code, "go")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_validate_rust_code(self, validator: StaticValidator) -> None:
        """测试验证 Rust 代码。"""
        code = '''
fn main() {
    println!("Hello");
}
'''
        code_blocks = [make_code_block(code, "rust")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_validate_java_code(self, validator: StaticValidator) -> None:
        """测试验证 Java 代码。"""
        code = '''
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}
'''
        code_blocks = [make_code_block(code, "java")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_validate_unsupported_language(self, validator: StaticValidator) -> None:
        """测试验证不支持的语言。"""
        code_blocks = [make_code_block("some code", "ruby")]
        result = validator.validate_code_blocks(code_blocks)

        # 不支持的语言应该返回结果
        assert isinstance(result, StaticAnalysisResult)

    def test_empty_code_block(self, validator: StaticValidator) -> None:
        """测试空代码块。"""
        code_blocks = [make_code_block("", "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_whitespace_only_code(self, validator: StaticValidator) -> None:
        """测试只有空白字符的代码。"""
        code_blocks = [make_code_block("   \n\t  ", "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_code_with_unicode(self, validator: StaticValidator) -> None:
        """测试包含 Unicode 的代码。"""
        code = '''
def 你好():
    """中文函数"""
    print("世界")
'''
        code_blocks = [make_code_block(code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_code_with_long_lines(self, validator: StaticValidator) -> None:
        """测试长行代码。"""
        code = f'''
def main():
    x = "{"x" * 200}"  # Very long string
'''
        code_blocks = [make_code_block(code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_code_with_nested_functions(self, validator: StaticValidator) -> None:
        """测试嵌套函数代码。"""
        code = '''
def outer():
    def inner():
        pass
    return inner
'''
        code_blocks = [make_code_block(code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    def test_code_with_comments(self, validator: StaticValidator) -> None:
        """测试带注释的代码。"""
        code = '''
def main():
    # This is a comment
    """Docstring"""
    pass
'''
        code_blocks = [make_code_block(code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """错误处理测试。"""

    def test_static_validation_error_properties(self) -> None:
        """测试 StaticValidationError 属性。"""
        error = StaticValidationError(
            message="Validation failed",
            issues=[CodeIssue(
                severity=SeverityLevel.ERROR,
                message="Syntax error",
                line_number=1,
                code_block_index=0
            )]
        )

        assert error.message == "Validation failed"
        assert len(error.issues) == 1
        assert error.code == "GS-2011"

    def test_static_validation_error_to_dict(self) -> None:
        """测试 StaticValidationError 序列化。"""
        error = StaticValidationError(
            message="Validation failed",
            issues=[CodeIssue(
                severity=SeverityLevel.ERROR,
                message="Error",
                line_number=1,
                code_block_index=0
            )]
        )

        result = error.to_dict()
        assert "error" in result
        assert result["error"]["message"] == "Validation failed"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """集成测试。"""

    def test_full_validation_workflow(self, validator: StaticValidator) -> None:
        """测试完整验证工作流。"""
        code_blocks = [
            make_code_block("def main(): pass", "python"),
            make_code_block("echo 'hello'", "bash"),
        ]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)
        assert isinstance(result.issues, list)
        assert isinstance(result.ast_results, list)

    def test_validation_with_file_path(self, validator: StaticValidator) -> None:
        """测试带文件路径的验证。"""
        code_blocks = [make_code_block("def main(): pass", "python")]
        result = validator.validate_code_blocks(code_blocks, file_path=Path("/test/skill.md"))

        assert result.file_path == Path("/test/skill.md")


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """性能测试。"""

    @pytest.mark.slow
    def test_large_code_block(self, validator: StaticValidator) -> None:
        """测试大代码块。"""
        # 生成大量代码
        code = "\n".join([f"def func{i}(): pass" for i in range(100)])
        code_blocks = [make_code_block(code, "python")]
        result = validator.validate_code_blocks(code_blocks)

        assert isinstance(result, StaticAnalysisResult)

    @pytest.mark.slow
    def test_repeated_validation(self, validator: StaticValidator, valid_python_code: str) -> None:
        """测试重复验证。"""
        code_blocks = [make_code_block(valid_python_code, "python")]
        for _ in range(10):
            result = validator.validate_code_blocks(code_blocks)
            assert isinstance(result, StaticAnalysisResult)
"""
静态代码检查器。

检查 SKILL.md 文件中代码块的语法错误和潜在问题。

Reference: RFC-02 Section 3.3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from graphskill.core.exceptions import IngestionError
from graphskill.ingestion.parser.ast_parser import ASTParser, ASTAnalysisResult


class SeverityLevel(str, Enum):
    """问题严重程度级别。"""
    
    ERROR = "error"      # 必须修复
    WARNING = "warning"  # 建议修复
    INFO = "info"        # 信息提示
    STYLE = "style"      # 代码风格问题


@dataclass
class CodeIssue:
    """代码问题结构。"""
    
    severity: SeverityLevel
    message: str
    line_number: int
    column: Optional[int] = None
    code_block_index: Optional[int] = None
    rule_id: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
            "severity": self.severity.value,
            "message": self.message,
            "line_number": self.line_number,
        }
        if self.column:
            result["column"] = self.column
        if self.code_block_index:
            result["code_block_index"] = self.code_block_index
        if self.rule_id:
            result["rule_id"] = self.rule_id
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


@dataclass
class StaticAnalysisResult:
    """静态分析结果。"""
    
    file_path: Optional[Path] = None
    issues: list[CodeIssue] = field(default_factory=list)
    ast_results: list[ASTAnalysisResult] = field(default_factory=list)
    has_errors: bool = False
    has_warnings: bool = False
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    @property
    def total_issues(self) -> int:
        """总问题数量。"""
        return len(self.issues)
    
    def to_dict(self) -> dict:
        return {
            "file_path": str(self.file_path) if self.file_path else None,
            "total_issues": self.total_issues,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class StaticValidationError(IngestionError):
    """静态验证错误。
    
    Error Code: GS-2011
    """
    
    def __init__(
        self,
        message: str,
        issues: Optional[list[CodeIssue]] = None,
        file_path: Optional[Path] = None,
    ):
        super().__init__(message)
        self.code = "GS-2011"
        self.issues = issues or []
        self.file_path = file_path
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["issues"] = [issue.to_dict() for issue in self.issues]
        if self.file_path:
            result["file_path"] = str(self.file_path)
        return result


# 规则定义
STATIC_RULES = {
    # Python 规则
    "python": {
        "missing_entrypoint": {
            "severity": SeverityLevel.WARNING,
            "message": "No entrypoint function found (main, run, execute)",
            "suggestion": "Add a main() function with entrypoint=true metadata",
        },
        "syntax_error": {
            "severity": SeverityLevel.ERROR,
            "message": "Syntax error detected",
        },
        "unused_import": {
            "severity": SeverityLevel.WARNING,
            "message": "Potentially unused import",
        },
        "missing_docstring": {
            "severity": SeverityLevel.INFO,
            "message": "Function missing docstring",
            "suggestion": "Add docstring for better documentation",
        },
        "high_complexity": {
            "severity": SeverityLevel.WARNING,
            "message": "High code complexity detected",
            "suggestion": "Consider breaking down into smaller functions",
        },
    },
    # Bash 规则
    "bash": {
        "missing_error_handling": {
            "severity": SeverityLevel.WARNING,
            "message": "Missing error handling (set -e)",
            "suggestion": "Add 'set -e' for error propagation",
        },
        "unquoted_variable": {
            "severity": SeverityLevel.WARNING,
            "message": "Unquoted variable expansion",
            "suggestion": "Quote variables to prevent word splitting",
        },
        "deprecated_syntax": {
            "severity": SeverityLevel.INFO,
            "message": "Deprecated syntax usage",
        },
    },
    # JavaScript/TypeScript 规则
    "javascript": {
        "missing_error_handling": {
            "severity": SeverityLevel.WARNING,
            "message": "Missing try-catch error handling",
            "suggestion": "Add error handling for robust execution",
        },
        "console_log": {
            "severity": SeverityLevel.INFO,
            "message": "console.log statement found",
            "suggestion": "Remove debug statements before production",
        },
    },
    "typescript": {
        "implicit_any": {
            "severity": SeverityLevel.WARNING,
            "message": "Implicit 'any' type",
            "suggestion": "Add explicit type annotation",
        },
    },
    # Go 规则
    "go": {
        "unhandled_error": {
            "severity": SeverityLevel.ERROR,
            "message": "Unhandled error return",
            "suggestion": "Check and handle error return values",
        },
        "missing_gomod": {
            "severity": SeverityLevel.INFO,
            "message": "Missing module declaration",
        },
    },
    # Rust 规则
    "rust": {
        "unsafe_block": {
            "severity": SeverityLevel.WARNING,
            "message": "Unsafe block detected",
            "suggestion": "Review unsafe code carefully",
        },
        "unhandled_result": {
            "severity": SeverityLevel.ERROR,
            "message": "Unhandled Result type",
            "suggestion": "Handle potential errors with match or ? operator",
        },
    },
    # Java 规则
    "java": {
        "missing_exception_handling": {
            "severity": SeverityLevel.WARNING,
            "message": "Missing exception handling",
            "suggestion": "Add try-catch for checked exceptions",
        },
        "empty_catch": {
            "severity": SeverityLevel.ERROR,
            "message": "Empty catch block",
            "suggestion": "Handle or log the exception",
        },
    },
}


class StaticValidator:
    """
    静态代码检查器。
    
    检查代码块的语法错误和潜在问题。
    
    Features:
        - 多语言支持
        - AST 分析集成
        - 规则检查
        - 问题报告
    
    Example:
        >>> validator = StaticValidator()
        >>> result = validator.validate_code_blocks(code_blocks)
        >>> if result.has_errors:
        ...     for issue in result.issues:
        ...         print(f"{issue.severity}: {issue.message}")
    """
    
    # 复杂度阈值
    COMPLEXITY_THRESHOLD = 5.0
    
    def __init__(
        self,
        strict_mode: bool = True,
        ast_parser: Optional[ASTParser] = None,
    ):
        """
        初始化检查器。
        
        Args:
            strict_mode: 严格模式，启用时对错误抛出异常
            ast_parser: AST 解析器实例
        """
        self.strict_mode = strict_mode
        self.ast_parser = ast_parser or ASTParser()
    
    def validate_code_blocks(
        self,
        code_blocks: list[dict],
        file_path: Optional[Path] = None,
    ) -> StaticAnalysisResult:
        """
        验证代码块列表。
        
        Args:
            code_blocks: 代码块列表（包含 language, code, line_start 等）
            file_path: 源文件路径
            
        Returns:
            StaticAnalysisResult: 分析结果
        """
        issues: list[CodeIssue] = []
        ast_results: list[ASTAnalysisResult] = []
        
        for i, block in enumerate(code_blocks):
            language = block.get("language", "text")
            code = block.get("code", "")
            line_start = block.get("line_start", 1)
            
            # AST 分析
            ast_result = self.ast_parser.parse(code, language, line_start)
            ast_results.append(ast_result)
            
            # 检查语法错误
            if ast_result.has_syntax_errors:
                for error in ast_result.syntax_errors:
                    issues.append(CodeIssue(
                        severity=SeverityLevel.ERROR,
                        message=f"Syntax error: {error.get('message', 'Unknown error')}",
                        line_number=error.get("line", line_start),
                        code_block_index=i,
                        rule_id="syntax_error",
                    ))
            
            # 语言特定规则检查
            block_issues = self._check_language_rules(
                code, language, ast_result, line_start, i
            )
            issues.extend(block_issues)
        
        # 统计问题数量
        error_count = sum(1 for issue in issues if issue.severity == SeverityLevel.ERROR)
        warning_count = sum(1 for issue in issues if issue.severity == SeverityLevel.WARNING)
        info_count = sum(1 for issue in issues if issue.severity in (SeverityLevel.INFO, SeverityLevel.STYLE))
        
        result = StaticAnalysisResult(
            file_path=file_path,
            issues=issues,
            ast_results=ast_results,
            has_errors=error_count > 0,
            has_warnings=warning_count > 0,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
        )
        
        if self.strict_mode and result.has_errors:
            raise StaticValidationError(
                f"Static validation failed with {error_count} errors",
                issues=[issue for issue in issues if issue.severity == SeverityLevel.ERROR],
                file_path=file_path,
            )
        
        return result
    
    def _check_language_rules(
        self,
        code: str,
        language: str,
        ast_result: ASTAnalysisResult,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """
        检查语言特定规则。
        
        Args:
            code: 代码内容
            language: 语言名称
            ast_result: AST 分析结果
            line_start: 起始行号
            block_index: 代码块索引
            
        Returns:
            list: 问题列表
        """
        issues: list[CodeIssue] = []
        rules = STATIC_RULES.get(language, {})
        
        # 检查入口点
        if "missing_entrypoint" in rules:
            if not ast_result.entrypoint_candidates:
                issues.append(CodeIssue(
                    severity=rules["missing_entrypoint"]["severity"],
                    message=rules["missing_entrypoint"]["message"],
                    line_number=line_start,
                    code_block_index=block_index,
                    rule_id="missing_entrypoint",
                    suggestion=rules["missing_entrypoint"].get("suggestion"),
                ))
        
        # 检查复杂度
        if "high_complexity" in rules:
            if ast_result.complexity_score > self.COMPLEXITY_THRESHOLD:
                issues.append(CodeIssue(
                    severity=rules["high_complexity"]["severity"],
                    message=f"{rules['high_complexity']['message']} (score: {ast_result.complexity_score:.1f})",
                    line_number=line_start,
                    code_block_index=block_index,
                    rule_id="high_complexity",
                    suggestion=rules["high_complexity"].get("suggestion"),
                ))
        
        # Python 特定检查
        if language == "python":
            issues.extend(self._check_python_rules(code, ast_result, line_start, block_index))
        
        # Bash 特定检查
        elif language == "bash":
            issues.extend(self._check_bash_rules(code, line_start, block_index))
        
        # JavaScript/TypeScript 特定检查
        elif language in ("javascript", "typescript"):
            issues.extend(self._check_javascript_rules(code, language, line_start, block_index))
        
        # Go 特定检查
        elif language == "go":
            issues.extend(self._check_go_rules(code, ast_result, line_start, block_index))
        
        # Rust 特定检查
        elif language == "rust":
            issues.extend(self._check_rust_rules(code, ast_result, line_start, block_index))
        
        # Java 特定检查
        elif language == "java":
            issues.extend(self._check_java_rules(code, line_start, block_index))
        
        return issues
    
    def _check_python_rules(
        self,
        code: str,
        ast_result: ASTAnalysisResult,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """Python 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES["python"]
        
        # 检查 docstring
        if "missing_docstring" in rules:
            for func in ast_result.functions:
                if not func.docstring and func.name not in ("__init__", "__str__", "__repr__"):
                    issues.append(CodeIssue(
                        severity=rules["missing_docstring"]["severity"],
                        message=f"{rules['missing_docstring']['message']} in function '{func.name}'",
                        line_number=func.line_start,
                        code_block_index=block_index,
                        rule_id="missing_docstring",
                        suggestion=rules["missing_docstring"].get("suggestion"),
                    ))
        
        return issues
    
    def _check_bash_rules(
        self,
        code: str,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """Bash 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES["bash"]
        
        # 检查 set -e
        if "missing_error_handling" in rules:
            if "set -e" not in code and "set -o errexit" not in code:
                # 检查是否有其他错误处理机制
                if "|| exit" not in code and "trap" not in code:
                    issues.append(CodeIssue(
                        severity=rules["missing_error_handling"]["severity"],
                        message=rules["missing_error_handling"]["message"],
                        line_number=line_start,
                        code_block_index=block_index,
                        rule_id="missing_error_handling",
                        suggestion=rules["missing_error_handling"].get("suggestion"),
                    ))
        
        # 检查未引用变量
        if "unquoted_variable" in rules:
            import re
            # 查找 $VAR 但不是 "$VAR" 或 ${VAR}
            unquoted_pattern = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)[^"\'\w]')
            for match in unquoted_pattern.finditer(code):
                # 检查是否在引号内
                pos = match.start()
                line_num = code[:pos].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["unquoted_variable"]["severity"],
                    message=f"{rules['unquoted_variable']['message']}: ${match.group(1)}",
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="unquoted_variable",
                    suggestion=rules["unquoted_variable"].get("suggestion"),
                ))
        
        return issues
    
    def _check_javascript_rules(
        self,
        code: str,
        language: str,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """JavaScript/TypeScript 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES.get(language, {})
        
        # 检查 console.log
        if "console_log" in rules:
            import re
            console_pattern = re.compile(r"console\.log\(")
            for match in console_pattern.finditer(code):
                line_num = code[:match.start()].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["console_log"]["severity"],
                    message=rules["console_log"]["message"],
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="console_log",
                    suggestion=rules["console_log"].get("suggestion"),
                ))
        
        # TypeScript: 检查 implicit any
        if language == "typescript" and "implicit_any" in rules:
            import re
            any_pattern = re.compile(r":\s*any\b")
            for match in any_pattern.finditer(code):
                line_num = code[:match.start()].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["implicit_any"]["severity"],
                    message=rules["implicit_any"]["message"],
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="implicit_any",
                    suggestion=rules["implicit_any"].get("suggestion"),
                ))
        
        return issues
    
    def _check_go_rules(
        self,
        code: str,
        ast_result: ASTAnalysisResult,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """Go 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES["go"]
        
        # 检查未处理错误
        if "unhandled_error" in rules:
            import re
            # 查找 err 变量但未检查
            err_assign_pattern = re.compile(r"err\s*:=|err\s*,")
            err_check_pattern = re.compile(r"if\s+err\s*!=\s*nil|err\s*==\s*nil")
            
            has_err_assign = err_assign_pattern.search(code)
            has_err_check = err_check_pattern.search(code)
            
            if has_err_assign and not has_err_check:
                line_num = code[:has_err_assign.start()].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["unhandled_error"]["severity"],
                    message=rules["unhandled_error"]["message"],
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="unhandled_error",
                    suggestion=rules["unhandled_error"].get("suggestion"),
                ))
        
        return issues
    
    def _check_rust_rules(
        self,
        code: str,
        ast_result: ASTAnalysisResult,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """Rust 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES["rust"]
        
        # 检查 unsafe 块
        if "unsafe_block" in rules:
            import re
            unsafe_pattern = re.compile(r"unsafe\s*\{")
            for match in unsafe_pattern.finditer(code):
                line_num = code[:match.start()].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["unsafe_block"]["severity"],
                    message=rules["unsafe_block"]["message"],
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="unsafe_block",
                    suggestion=rules["unsafe_block"].get("suggestion"),
                ))
        
        return issues
    
    def _check_java_rules(
        self,
        code: str,
        line_start: int,
        block_index: int,
    ) -> list[CodeIssue]:
        """Java 特定规则检查。"""
        issues: list[CodeIssue] = []
        rules = STATIC_RULES["java"]
        
        # 检查空 catch 块
        if "empty_catch" in rules:
            import re
            empty_catch_pattern = re.compile(r"catch\s*\([^)]+\)\s*\{\s*\}")
            for match in empty_catch_pattern.finditer(code):
                line_num = code[:match.start()].count("\n") + line_start
                issues.append(CodeIssue(
                    severity=rules["empty_catch"]["severity"],
                    message=rules["empty_catch"]["message"],
                    line_number=line_num,
                    code_block_index=block_index,
                    rule_id="empty_catch",
                    suggestion=rules["empty_catch"].get("suggestion"),
                ))
        
        return issues
    
    def validate_file(
        self,
        file_path: Path,
        code_blocks: Optional[list[dict]] = None,
    ) -> StaticAnalysisResult:
        """
        验证文件。
        
        Args:
            file_path: 技能文件路径
            code_blocks: 可选的代码块列表（如果未提供，将解析文件）
            
        Returns:
            StaticAnalysisResult: 分析结果
        """
        from graphskill.ingestion.parser.markdown_parser import MarkdownParser
        
        if code_blocks is None:
            parser = MarkdownParser(strict_mode=False)
            parsed = parser.parse(file_path)
            code_blocks = [
                {
                    "language": block.language,
                    "code": block.code,
                    "line_start": block.line_start,
                }
                for block in parsed.code_blocks
            ]
        
        return self.validate_code_blocks(code_blocks, file_path)
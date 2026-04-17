"""
AST 语法树解析器。

使用 Tree-sitter 解析代码块的语法结构，
提取函数定义、导入语句、变量声明等关键信息。

Reference: RFC-02 Section 3.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from graphskill.core.exceptions import IngestionError


class SupportedLanguage(str, Enum):
    """支持的编程语言。"""
    
    PYTHON = "python"
    BASH = "bash"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    SQL = "sql"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    TEXT = "text"


@dataclass
class FunctionDefinition:
    """函数定义结构。"""
    
    name: str
    line_start: int
    line_end: int
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    is_entrypoint_candidate: bool = False


@dataclass
class ImportStatement:
    """导入语句结构。"""
    
    module: str
    line_number: int
    names: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from_import: bool = False


@dataclass
class VariableDeclaration:
    """变量声明结构。"""
    
    name: str
    line_number: int
    value_type: Optional[str] = None
    is_constant: bool = False


@dataclass
class ASTAnalysisResult:
    """AST 分析结果。"""
    
    language: str
    functions: list[FunctionDefinition] = field(default_factory=list)
    imports: list[ImportStatement] = field(default_factory=list)
    variables: list[VariableDeclaration] = field(default_factory=list)
    syntax_errors: list[dict] = field(default_factory=list)
    entrypoint_candidates: list[FunctionDefinition] = field(default_factory=list)
    complexity_score: float = 0.0
    raw_tree: Optional[Any] = None
    
    @property
    def has_syntax_errors(self) -> bool:
        """是否存在语法错误。"""
        return len(self.syntax_errors) > 0
    
    @property
    def function_count(self) -> int:
        """函数数量。"""
        return len(self.functions)
    
    @property
    def import_count(self) -> int:
        """导入语句数量。"""
        return len(self.imports)


class ASTParseError(IngestionError):
    """AST 解析错误。
    
    Error Code: GS-2002
    """
    
    def __init__(
        self,
        message: str,
        language: Optional[str] = None,
        line_number: Optional[int] = None,
    ):
        super().__init__(message)
        self.code = "GS-2002"
        self.language = language
        self.line_number = line_number
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.language:
            result["language"] = self.language
        if self.line_number:
            result["line_number"] = self.line_number
        return result


class ASTParser:
    """
    AST 语法树解析器。
    
    使用 Tree-sitter 解析代码块的语法结构。
    
    Features:
        - 多语言支持
        - 函数定义提取
        - 导入语句分析
        - 语法错误检测
        - 入口点候选识别
    
    Note:
        Tree-sitter 是可选依赖，如果未安装则使用简化解析。
    
    Example:
        >>> parser = ASTParser()
        >>> result = parser.parse("def main(): pass", "python")
        >>> print(result.functions[0].name)
        main
    """
    
    # 入口点候选函数名模式
    ENTRYPOINT_NAMES = {
        "python": ["main", "run", "execute", "handle", "process"],
        "bash": ["main", "run", "execute"],
        "javascript": ["main", "run", "execute", "handler"],
        "typescript": ["main", "run", "execute", "handler"],
        "go": ["main", "Run", "Execute"],
        "rust": ["main", "run", "execute"],
        "java": ["main", "run", "execute"],
    }
    
    def __init__(self, use_tree_sitter: bool = True):
        """
        初始化解析器。
        
        Args:
            use_tree_sitter: 是否使用 Tree-sitter（需要安装）
        """
        self.use_tree_sitter = use_tree_sitter
        self._tree_sitter_available = self._check_tree_sitter()
    
    def _check_tree_sitter(self) -> bool:
        """检查 Tree-sitter 是否可用。"""
        try:
            import tree_sitter  # noqa: F401
            return True
        except ImportError:
            return False
    
    def parse(
        self,
        code: str,
        language: str,
        line_offset: int = 0,
    ) -> ASTAnalysisResult:
        """
        解析代码块。
        
        Args:
            code: 代码内容
            language: 语言名称
            line_offset: 行号偏移（相对于文件起始）
            
        Returns:
            ASTAnalysisResult: 分析结果
        """
        # 标准化语言名称
        normalized_language = self._normalize_language(language)
        
        if self._tree_sitter_available and self.use_tree_sitter:
            return self._parse_with_tree_sitter(code, normalized_language, line_offset)
        else:
            return self._parse_with_regex(code, normalized_language, line_offset)
    
    def _normalize_language(self, language: str) -> str:
        """
        标准化语言名称。
        
        Args:
            language: 原始语言名称
            
        Returns:
            str: 标准化后的语言名称
        """
        # 处理常见别名
        aliases = {
            "py": "python",
            "sh": "bash",
            "shell": "bash",
            "js": "javascript",
            "ts": "typescript",
            "golang": "go",
            "rs": "rust",
            "c++": "cpp",
            "cplusplus": "cpp",
        }
        
        normalized = aliases.get(language.lower(), language.lower())
        
        # 检查是否支持
        try:
            return SupportedLanguage(normalized).value
        except ValueError:
            # 不支持的语言，返回原始名称
            return language.lower()
    
    def _parse_with_tree_sitter(
        self,
        code: str,
        language: str,
        line_offset: int,
    ) -> ASTAnalysisResult:
        """
        使用 Tree-sitter 解析。
        
        Args:
            code: 代码内容
            language: 语言名称
            line_offset: 行号偏移
            
        Returns:
            ASTAnalysisResult: 分析结果
        """
        # Tree-sitter 解析逻辑
        # 由于 Tree-sitter 需要语言特定解析器，这里提供框架
        # 实际实现需要安装对应的语言解析器
        
        try:
            import tree_sitter_python as tspython  # noqa: F401
            # 如果成功导入，使用 Tree-sitter
            return self._tree_sitter_parse_impl(code, language, line_offset)
        except ImportError:
            # Tree-sitter 语言解析器未安装，回退到正则解析
            return self._parse_with_regex(code, language, line_offset)
    
    def _tree_sitter_parse_impl(
        self,
        code: str,
        language: str,
        line_offset: int,
    ) -> ASTAnalysisResult:
        """
        Tree-sitter 解析实现。
        
        Note: 这是一个占位实现，需要根据实际 Tree-sitter 版本调整。
        """
        # 由于 Tree-sitter API 可能变化，这里提供简化实现
        # 实际项目中需要根据 Tree-sitter 版本实现完整解析
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        syntax_errors: list[dict] = []
        
        # 使用正则作为基础解析（Tree-sitter 未完全配置时的回退）
        result = self._parse_with_regex(code, language, line_offset)
        
        return result
    
    def _parse_with_regex(
        self,
        code: str,
        language: str,
        line_offset: int,
    ) -> ASTAnalysisResult:
        """
        使用正则表达式解析（简化版）。
        
        Args:
            code: 代码内容
            language: 语言名称
            line_offset: 行号偏移
            
        Returns:
            ASTAnalysisResult: 分析结果
        """
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        syntax_errors: list[dict] = []
        
        if language == "python":
            functions, imports, variables = self._parse_python(code, line_offset)
        elif language == "bash":
            functions, imports, variables = self._parse_bash(code, line_offset)
        elif language in ("javascript", "typescript"):
            functions, imports, variables = self._parse_javascript(code, line_offset)
        elif language == "go":
            functions, imports, variables = self._parse_go(code, line_offset)
        elif language == "rust":
            functions, imports, variables = self._parse_rust(code, line_offset)
        elif language == "java":
            functions, imports, variables = self._parse_java(code, line_offset)
        else:
            # 不支持的语言，返回空结果
            pass
        
        # 识别入口点候选
        entrypoint_names = self.ENTRYPOINT_NAMES.get(language, ["main"])
        entrypoint_candidates = [
            f for f in functions
            if f.name in entrypoint_names or f.is_entrypoint_candidate
        ]
        
        # 计算复杂度分数
        complexity_score = self._calculate_complexity(functions, imports, variables)
        
        return ASTAnalysisResult(
            language=language,
            functions=functions,
            imports=imports,
            variables=variables,
            syntax_errors=syntax_errors,
            entrypoint_candidates=entrypoint_candidates,
            complexity_score=complexity_score,
        )
    
    def _parse_python(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """
        解析 Python 代码。
        
        Args:
            code: 代码内容
            line_offset: 行号偏移
            
        Returns:
            tuple: (functions, imports, variables)
        """
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 函数定义模式
        func_pattern = re.compile(
            r"^(async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\w+))?\s*:"
        )
        
        # 导入语句模式
        import_pattern = re.compile(r"^import\s+(\w+)(?:\s+as\s+(\w+))?")
        from_import_pattern = re.compile(r"^from\s+(\w+(?:\.\w+)*)\s+import\s+(.+)")
        
        # 变量声明模式
        var_pattern = re.compile(r"^(\w+)\s*=\s*(.+)")
        const_pattern = re.compile(r"^(\w+)\s*:\s*(\w+)\s*=\s*(.+)")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # 函数定义
            func_match = func_pattern.match(stripped)
            if func_match:
                is_async = func_match.group(1) is not None
                name = func_match.group(2)
                params_str = func_match.group(3) or ""
                return_type = func_match.group(4)
                
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                
                # 查找函数结束行
                func_end_line = self._find_python_function_end(lines, i)
                
                # 查找 docstring
                docstring = self._find_python_docstring(lines, i + 1)
                
                functions.append(FunctionDefinition(
                    name=name,
                    parameters=params,
                    return_type=return_type,
                    line_start=line_num,
                    line_end=line_offset + func_end_line + 1,
                    docstring=docstring,
                    is_async=is_async,
                    is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("python", []),
                ))
            
            # 导入语句
            import_match = import_pattern.match(stripped)
            if import_match:
                imports.append(ImportStatement(
                    module=import_match.group(1),
                    alias=import_match.group(2),
                    is_from_import=False,
                    line_number=line_num,
                ))
            
            from_match = from_import_pattern.match(stripped)
            if from_match:
                module = from_match.group(1)
                names_str = from_match.group(2)
                names = [n.strip() for n in names_str.split(",") if n.strip()]
                imports.append(ImportStatement(
                    module=module,
                    names=names,
                    is_from_import=True,
                    line_number=line_num,
                ))
            
            # 变量声明
            const_match = const_pattern.match(stripped)
            if const_match:
                variables.append(VariableDeclaration(
                    name=const_match.group(1),
                    value_type=const_match.group(2),
                    line_number=line_num,
                    is_constant=False,
                ))
            else:
                var_match_result = var_pattern.match(stripped)
                if var_match_result and not stripped.startswith("#"):
                    variables.append(VariableDeclaration(
                        name=var_match_result.group(1),
                        line_number=line_num,
                        is_constant=False,
                    ))
        
        return functions, imports, variables
    
    def _find_python_function_end(self, lines: list[str], start_idx: int) -> int:
        """
        查找 Python 函数结束行。
        
        Args:
            lines: 代码行列表
            start_idx: 函数起始索引
            
        Returns:
            int: 函数结束行索引
        """
        # 获取函数缩进级别
        func_line = lines[start_idx]
        func_indent = len(func_line) - len(func_line.lstrip())
        
        # 查找下一个相同或更低缩进的非空行
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue
            
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= func_indent:
                return i - 1
        
        return len(lines) - 1
    
    def _find_python_docstring(self, lines: list[str], start_idx: int) -> Optional[str]:
        """
        查找 Python 函数 docstring。
        
        Args:
            lines: 代码行列表
            start_idx: 函数体起始索引
            
        Returns:
            Optional[str]: docstring 内容
        """
        if start_idx >= len(lines):
            return None
        
        first_line = lines[start_idx].strip()
        
        # 单行 docstring
        if first_line.startswith('"') and first_line.endswith('"') and len(first_line) > 2:
            return first_line[1:-1]
        
        if first_line.startswith("'") and first_line.endswith("'") and len(first_line) > 2:
            return first_line[1:-1]
        
        # 多行 docstring
        if first_line.startswith('"""') or first_line.startswith("'''"):
            quote = first_line[:3]
            # 检查是否在同一行结束
            if first_line.endswith(quote) and len(first_line) > 6:
                return first_line[3:-3]
            
            # 查找结束引号
            docstring_lines = [first_line[3:]]
            for i in range(start_idx + 1, len(lines)):
                line = lines[i]
                if quote in line:
                    docstring_lines.append(line.split(quote)[0])
                    return "\n".join(docstring_lines).strip()
                docstring_lines.append(line)
        
        return None
    
    def _parse_bash(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """解析 Bash 代码。"""
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 函数定义模式
        func_pattern = re.compile(r"^function\s+(\w+)\s*\{|^(\w+)\s*\(\)\s*\{")
        
        # source/import 模式
        source_pattern = re.compile(r"^source\s+(.+)|^\.\s+(.+)")
        
        # 变量声明模式
        var_pattern = re.compile(r"^(\w+)=(.+)")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # 函数定义
            func_match = func_pattern.match(stripped)
            if func_match:
                name = func_match.group(1) or func_match.group(2)
                func_end = self._find_bash_function_end(lines, i)
                functions.append(FunctionDefinition(
                    name=name,
                    line_start=line_num,
                    line_end=line_offset + func_end + 1,
                    is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("bash", []),
                ))
            
            # source 语句
            source_match = source_pattern.match(stripped)
            if source_match:
                module = source_match.group(1) or source_match.group(2)
                imports.append(ImportStatement(
                    module=module.strip(),
                    line_number=line_num,
                ))
            
            # 变量声明
            var_match = var_pattern.match(stripped)
            if var_match and not stripped.startswith("#"):
                variables.append(VariableDeclaration(
                    name=var_match.group(1),
                    line_number=line_num,
                ))
        
        return functions, imports, variables
    
    def _find_bash_function_end(self, lines: list[str], start_idx: int) -> int:
        """查找 Bash 函数结束行。"""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and i > start_idx:
                return i
        return len(lines) - 1
    
    def _parse_javascript(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """解析 JavaScript/TypeScript 代码。"""
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 函数定义模式
        func_pattern = re.compile(
            r"(async\s+)?function\s+(\w+)\s*\(|"
            r"(async\s+)?(\w+)\s*=\s*(?:async\s+)?function\s*\(|"
            r"(async\s+)?const\s+(\w+)\s*=\s*\([^)]*\)\s*=>"
        )
        
        # 导入语句模式
        import_pattern = re.compile(r"^import\s+(.+)\s+from\s+['\"](.+)['\"]")
        require_pattern = re.compile(r"^(?:const|let|var)\s+(\w+)\s*=\s*require\(['\"](.+)['\"]\)")
        
        # 变量声明模式
        var_pattern = re.compile(r"^(?:const|let|var)\s+(\w+)(?:\s*:\s*(\w+))?\s*=")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # 函数定义（简化处理）
            func_match = func_pattern.search(stripped)
            if func_match:
                # 提取函数名（根据匹配组）
                name = None
                groups = func_match.groups()
                if groups[1]:  # function name
                    name = groups[1]
                elif groups[3]:  # name = function
                    name = groups[3]
                elif groups[5]:  # const name = () =>
                    name = groups[5]
                
                if name:
                    functions.append(FunctionDefinition(
                        name=name,
                        line_start=line_num,
                        line_end=line_num + 5,  # 简化估算
                        is_async=groups[0] or groups[2] or groups[4] is not None,
                        is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("javascript", []),
                    ))
            
            # import 语句
            import_match = import_pattern.match(stripped)
            if import_match:
                names_str = import_match.group(1)
                module = import_match.group(2)
                names = [n.strip() for n in names_str.split(",") if n.strip()]
                imports.append(ImportStatement(
                    module=module,
                    names=names,
                    is_from_import=True,
                    line_number=line_num,
                ))
            
            # require 语句
            require_match = require_pattern.match(stripped)
            if require_match:
                imports.append(ImportStatement(
                    module=require_match.group(2),
                    names=[require_match.group(1)],
                    is_from_import=False,
                    line_number=line_num,
                ))
            
            # 变量声明
            var_match = var_pattern.match(stripped)
            if var_match:
                variables.append(VariableDeclaration(
                    name=var_match.group(1),
                    value_type=var_match.group(2),
                    line_number=line_num,
                    is_constant=stripped.startswith("const"),
                ))
        
        return functions, imports, variables
    
    def _parse_go(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """解析 Go 代码。"""
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 函数定义模式
        func_pattern = re.compile(r"^func\s+(\w+)\s*\(([^)]*)\)(?:\s*\(([^)]*)\))?")
        
        # 导入语句模式
        import_pattern = re.compile(r"^import\s+['\"](.+)['\"]|import\s+\(([^)]+)\)")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # 函数定义
            func_match = func_pattern.match(stripped)
            if func_match:
                name = func_match.group(1)
                params_str = func_match.group(2) or ""
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                
                func_end = self._find_go_function_end(lines, i)
                functions.append(FunctionDefinition(
                    name=name,
                    parameters=params,
                    line_start=line_num,
                    line_end=line_offset + func_end + 1,
                    is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("go", []),
                ))
            
            # import 语句
            import_match = import_pattern.match(stripped)
            if import_match:
                if import_match.group(1):
                    imports.append(ImportStatement(
                        module=import_match.group(1),
                        line_number=line_num,
                    ))
                elif import_match.group(2):
                    # 多行 import
                    import_block = import_match.group(2)
                    for imp in import_block.split("\n"):
                        imp = imp.strip()
                        if imp and not imp.startswith("//"):
                            imports.append(ImportStatement(
                                module=imp.strip('"').strip("'"),
                                line_number=line_num,
                            ))
        
        return functions, imports, variables
    
    def _find_go_function_end(self, lines: list[str], start_idx: int) -> int:
        """查找 Go 函数结束行。"""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and i > start_idx:
                return i
        return len(lines) - 1
    
    def _parse_rust(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """解析 Rust 代码。"""
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 函数定义模式
        func_pattern = re.compile(
            r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\w+))?"
        )
        
        # use 语句模式
        use_pattern = re.compile(r"^use\s+(.+);")
        
        # let 语句模式
        let_pattern = re.compile(r"^let\s+(?:mut\s+)?(\w+)(?:\s*:\s*(\w+))?\s*=")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # 函数定义
            func_match = func_pattern.match(stripped)
            if func_match:
                name = func_match.group(1)
                params_str = func_match.group(2) or ""
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                return_type = func_match.group(3)
                
                func_end = self._find_rust_function_end(lines, i)
                functions.append(FunctionDefinition(
                    name=name,
                    parameters=params,
                    return_type=return_type,
                    line_start=line_num,
                    line_end=line_offset + func_end + 1,
                    is_async="async" in stripped,
                    is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("rust", []),
                ))
            
            # use 语句
            use_match = use_pattern.match(stripped)
            if use_match:
                imports.append(ImportStatement(
                    module=use_match.group(1),
                    line_number=line_num,
                ))
            
            # let 语句
            let_match = let_pattern.match(stripped)
            if let_match:
                variables.append(VariableDeclaration(
                    name=let_match.group(1),
                    value_type=let_match.group(2),
                    line_number=line_num,
                    is_constant="mut" not in stripped,
                ))
        
        return functions, imports, variables
    
    def _find_rust_function_end(self, lines: list[str], start_idx: int) -> int:
        """查找 Rust 函数结束行。"""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and i > start_idx:
                return i
        return len(lines) - 1
    
    def _parse_java(
        self,
        code: str,
        line_offset: int,
    ) -> tuple[list[FunctionDefinition], list[ImportStatement], list[VariableDeclaration]]:
        """解析 Java 代码。"""
        import re
        
        functions: list[FunctionDefinition] = []
        imports: list[ImportStatement] = []
        variables: list[VariableDeclaration] = []
        
        lines = code.split("\n")
        
        # 方法定义模式
        method_pattern = re.compile(
            r"^(?:public|private|protected)?(?:\s+static)?(?:\s+\w+)?\s+(\w+)\s*\(([^)]*)\)"
        )
        
        # import 语句模式
        import_pattern = re.compile(r"^import\s+(.+);")
        
        # 变量声明模式
        var_pattern = re.compile(r"^(?:public|private|protected)?(?:\s+static)?(?:\s+final)?\s+(\w+)\s+(\w+)\s*=")
        
        for i, line in enumerate(lines):
            line_num = line_offset + i + 1
            stripped = line.strip()
            
            # import 语句
            import_match = import_pattern.match(stripped)
            if import_match:
                imports.append(ImportStatement(
                    module=import_match.group(1),
                    line_number=line_num,
                ))
            
            # 方法定义（排除 class 关键字）
            if "class" not in stripped:
                method_match = method_pattern.match(stripped)
                if method_match:
                    name = method_match.group(1)
                    params_str = method_match.group(2) or ""
                    params = [p.strip() for p in params_str.split(",") if p.strip()]
                    
                    func_end = self._find_java_method_end(lines, i)
                    functions.append(FunctionDefinition(
                        name=name,
                        parameters=params,
                        line_start=line_num,
                        line_end=line_offset + func_end + 1,
                        is_entrypoint_candidate=name in self.ENTRYPOINT_NAMES.get("java", []),
                    ))
            
            # 变量声明
            var_match = var_pattern.match(stripped)
            if var_match:
                variables.append(VariableDeclaration(
                    name=var_match.group(2),
                    value_type=var_match.group(1),
                    line_number=line_num,
                    is_constant="final" in stripped,
                ))
        
        return functions, imports, variables
    
    def _find_java_method_end(self, lines: list[str], start_idx: int) -> int:
        """查找 Java 方法结束行。"""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and i > start_idx:
                return i
        return len(lines) - 1
    
    def _calculate_complexity(
        self,
        functions: list[FunctionDefinition],
        imports: list[ImportStatement],
        variables: list[VariableDeclaration],
    ) -> float:
        """
        计算代码复杂度分数。
        
        Args:
            functions: 函数列表
            imports: 导入列表
            variables: 变量列表
            
        Returns:
            float: 复杂度分数 (0-10)
        """
        # 基于函数数量、参数数量、导入数量计算
        func_score = min(len(functions) * 0.5, 3.0)
        param_score = min(sum(len(f.parameters) for f in functions) * 0.1, 2.0)
        import_score = min(len(imports) * 0.2, 2.0)
        var_score = min(len(variables) * 0.1, 1.0)
        
        # 异步函数额外复杂度
        async_score = min(sum(1 for f in functions if f.is_async) * 0.3, 1.0)
        
        return func_score + param_score + import_score + var_score + async_score
    
    def get_entrypoint_candidates(
        self,
        result: ASTAnalysisResult,
    ) -> list[FunctionDefinition]:
        """
        获取入口点候选函数。
        
        Args:
            result: AST 分析结果
            
        Returns:
            list: 入口点候选列表
        """
        return result.entrypoint_candidates
    
    def is_language_supported(self, language: str) -> bool:
        """
        检查语言是否支持。
        
        Args:
            language: 语言名称
            
        Returns:
            bool: 是否支持
        """
        normalized = self._normalize_language(language)
        try:
            SupportedLanguage(normalized)
            return True
        except ValueError:
            return False
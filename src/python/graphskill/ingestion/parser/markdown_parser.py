"""
Markdown 技能文件解析器。

解析 SKILL.md 文件，提取 YAML Frontmatter 和 Markdown 正文。
支持代码块提取和行号定位。

Reference: RFC-02 Section 3.2
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from graphskill.core.exceptions import IngestionError


@dataclass
class ParsedSkillFile:
    """解析后的技能文件结构。"""
    
    file_path: Path
    frontmatter: dict
    content: str
    code_blocks: list[CodeBlock] = field(default_factory=list)
    raw_content: str = ""
    frontmatter_line_start: int = 1
    frontmatter_line_end: int = 0
    
    @property
    def skill_id(self) -> Optional[str]:
        """获取技能 ID。"""
        return self.frontmatter.get("skill_id")
    
    @property
    def version(self) -> Optional[str]:
        """获取版本号。"""
        return self.frontmatter.get("version")


@dataclass
class CodeBlock:
    """代码块结构。"""
    
    language: str
    code: str
    line_start: int
    line_end: int
    metadata: Optional[dict] = None
    is_entrypoint: bool = False
    
    @property
    def line_count(self) -> int:
        """代码块行数。"""
        return self.line_end - self.line_start + 1


class ParseError(IngestionError):
    """解析错误异常。
    
    Error Code: GS-2000 系列
    """
    
    def __init__(self, message: str, file_path: Optional[Path] = None, line_number: Optional[int] = None):
        super().__init__(message)
        self.code = "GS-2000"
        self.file_path = file_path
        self.line_number = line_number
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.file_path:
            result["file_path"] = str(self.file_path)
        if self.line_number:
            result["line_number"] = self.line_number
        return result


class MarkdownParser:
    """
    Markdown 技能文件解析器。
    
    支持解析包含 YAML Frontmatter 的 Markdown 文件，
    提取元数据和代码块。
    
    Features:
        - YAML Frontmatter 提取
        - 代码块语法识别
        - 行号精确定位
        - 代码块元数据解析
    
    Example:
        >>> parser = MarkdownParser()
        >>> result = parser.parse(Path("skills/git/commit_changes/SKILL.md"))
        >>> print(result.frontmatter["skill_id"])
        git:commit_changes
        >>> print(len(result.code_blocks))
        3
    """
    
    # YAML Frontmatter 模式：--- 包围的 YAML 块
    FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n",
        re.DOTALL
    )
    
    # 代码块模式：```language {metadata} 格式
    CODE_BLOCK_PATTERN = re.compile(
        r"```(\w+)?(?:\s+\{([^}]*)\})?\s*\n(.*?)\n```",
        re.DOTALL
    )
    
    # Entrypoint 标记模式
    ENTRYPOINT_PATTERN = re.compile(
        r"```(\w+)?\s*\{.*?entrypoint.*?\}",
        re.DOTALL
    )
    
    def __init__(self, strict_mode: bool = True):
        """
        初始化解析器。
        
        Args:
            strict_mode: 严格模式，启用时对格式错误抛出异常
        """
        self.strict_mode = strict_mode
    
    def parse(self, file_path: Path) -> ParsedSkillFile:
        """
        解析技能文件。
        
        Args:
            file_path: 技能文件路径
            
        Returns:
            ParsedSkillFile: 解析结果
            
        Raises:
            ParseError: 文件格式错误
        """
        if not file_path.exists():
            raise ParseError(
                f"File not found: {file_path}",
                file_path=file_path
            )
        
        if not file_path.is_file():
            raise ParseError(
                f"Path is not a file: {file_path}",
                file_path=file_path
            )
        
        try:
            raw_content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ParseError(
                f"File encoding error (expected UTF-8): {e}",
                file_path=file_path
            )
        
        # 提取 Frontmatter
        frontmatter, content, fm_line_end = self._extract_frontmatter(raw_content, file_path)
        
        # 提取代码块
        code_blocks = self._extract_code_blocks(content)
        
        return ParsedSkillFile(
            file_path=file_path,
            frontmatter=frontmatter,
            content=content,
            code_blocks=code_blocks,
            raw_content=raw_content,
            frontmatter_line_start=1,
            frontmatter_line_end=fm_line_end,
        )
    
    def parse_string(self, content: str, file_path: Optional[Path] = None) -> ParsedSkillFile:
        """
        解析字符串内容。
        
        Args:
            content: 文件内容字符串
            file_path: 可选的文件路径（用于错误报告）
            
        Returns:
            ParsedSkillFile: 解析结果
            
        Raises:
            ParseError: 内容格式错误
        """
        # 提取 Frontmatter
        frontmatter, remaining_content, fm_line_end = self._extract_frontmatter(content, file_path)
        
        # 提取代码块
        code_blocks = self._extract_code_blocks(remaining_content)
        
        return ParsedSkillFile(
            file_path=file_path or Path("unknown"),
            frontmatter=frontmatter,
            content=remaining_content,
            code_blocks=code_blocks,
            raw_content=content,
            frontmatter_line_start=1,
            frontmatter_line_end=fm_line_end,
        )
    
    def _extract_frontmatter(
        self,
        raw_content: str,
        file_path: Optional[Path] = None
    ) -> tuple[dict, str, int]:
        """
        提取 YAML Frontmatter。
        
        Args:
            raw_content: 原始文件内容
            file_path: 文件路径（用于错误报告）
            
        Returns:
            tuple: (frontmatter_dict, remaining_content, frontmatter_end_line)
            
        Raises:
            ParseError: Frontmatter 格式错误
        """
        match = self.FRONTMATTER_PATTERN.match(raw_content)
        
        if not match:
            if self.strict_mode:
                raise ParseError(
                    "No valid YAML frontmatter found. "
                    "File must start with '---' markers.",
                    file_path=file_path,
                    line_number=1
                )
            # 非严格模式：返回空 frontmatter
            return {}, raw_content, 0
        
        yaml_content = match.group(1)
        remaining_content = raw_content[match.end():]
        
        # 计算 frontmatter 结束行号
        fm_lines = yaml_content.count("\n") + 3  # --- + content + ---
        fm_line_end = fm_lines
        
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ParseError(
                f"YAML parsing error: {e}",
                file_path=file_path,
                line_number=self._find_yaml_error_line(str(e))
            )
        
        if not isinstance(frontmatter, dict):
            raise ParseError(
                "Frontmatter must be a YAML dictionary/mapping",
                file_path=file_path,
                line_number=2
            )
        
        return frontmatter, remaining_content, fm_line_end
    
    def _extract_code_blocks(self, content: str) -> list[CodeBlock]:
        """
        提取代码块。
        
        Args:
            content: Markdown 正文
            
        Returns:
            list: 代码块列表
        """
        code_blocks: list[CodeBlock] = []
        
        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            language = match.group(1) or "text"
            metadata_str = match.group(2) or ""
            code = match.group(3)
            
            # 解析 metadata (如果有)
            metadata: Optional[dict] = None
            if metadata_str:
                try:
                    # 支持 {key=value, key2="value2"} 格式
                    metadata = self._parse_block_metadata(metadata_str)
                except Exception:
                    metadata = {"raw": metadata_str}
            
            # 检查是否为 entrypoint
            is_entrypoint = False
            if metadata and metadata.get("entrypoint"):
                is_entrypoint = True
            
            # 计算行号（相对于 content 开始位置）
            line_start = content[:match.start()].count("\n") + 1
            line_end = line_start + code.count("\n") + 2  # 包含 ``` 行
            
            code_blocks.append(CodeBlock(
                language=language,
                code=code.strip(),
                line_start=line_start,
                line_end=line_end,
                metadata=metadata,
                is_entrypoint=is_entrypoint,
            ))
        
        return code_blocks
    
    def _parse_block_metadata(self, metadata_str: str) -> dict:
        """
        解析代码块元数据。
        
        支持格式：
        - {entrypoint=true}
        - {timeout=30, retry=3}
        - {name="main", type="function"}
        
        Args:
            metadata_str: 元数据字符串
            
        Returns:
            dict: 解析后的元数据
        """
        result: dict = {}
        
        # 移除花括号
        metadata_str = metadata_str.strip()
        if metadata_str.startswith("{") and metadata_str.endswith("}"):
            metadata_str = metadata_str[1:-1]
        
        # 分割键值对
        pairs = metadata_str.split(",")
        for pair in pairs:
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip()
                
                # 解析值类型
                if value.lower() == "true":
                    result[key] = True
                elif value.lower() == "false":
                    result[key] = False
                elif value.startswith('"') and value.endswith('"'):
                    result[key] = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    result[key] = value[1:-1]
                else:
                    # 尝试解析为数字
                    try:
                        if "." in value:
                            result[key] = float(value)
                        else:
                            result[key] = int(value)
                    except ValueError:
                        result[key] = value
        
        return result
    
    def _find_yaml_error_line(self, error_message: str) -> int:
        """
        从 YAML 错误消息中提取行号。
        
        Args:
            error_message: YAML 错误消息
            
        Returns:
            int: 错误行号（默认返回 2）
        """
        # YAML 错误通常包含 "line X" 或类似信息
        line_match = re.search(r"line\s+(\d+)", error_message)
        if line_match:
            return int(line_match.group(1))
        return 2
    
    def get_entrypoint_block(self, parsed: ParsedSkillFile) -> Optional[CodeBlock]:
        """
        获取入口代码块。
        
        Args:
            parsed: 解析结果
            
        Returns:
            CodeBlock: 入口代码块（如果存在）
        """
        for block in parsed.code_blocks:
            if block.is_entrypoint:
                return block
        return None
    
    def get_blocks_by_language(self, parsed: ParsedSkillFile, language: str) -> list[CodeBlock]:
        """
        按语言筛选代码块。
        
        Args:
            parsed: 解析结果
            language: 语言名称
            
        Returns:
            list: 匹配的代码块列表
        """
        return [block for block in parsed.code_blocks if block.language == language]
"""
Markdown 解析器单元测试。

测试 MarkdownParser 的所有核心功能：
- YAML Frontmatter 提取
- 代码块解析
- 行号定位
- 错误处理
- 边界条件

Reference: RFC-02 Section 3.2
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from graphskill.ingestion.parser.markdown_parser import (
    CodeBlock,
    MarkdownParser,
    ParseError,
    ParsedSkillFile,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def parser() -> MarkdownParser:
    """创建默认解析器实例。"""
    return MarkdownParser(strict_mode=True)


@pytest.fixture
def lenient_parser() -> MarkdownParser:
    """创建非严格模式解析器实例。"""
    return MarkdownParser(strict_mode=False)


@pytest.fixture
def valid_skill_content() -> str:
    """有效的技能文件内容。"""
    return '''---
skill_id: git:commit_changes
version: 1.0.0
intent_description: Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
  - net:http:github.com
tags:
  - git
  - version-control
  - commit
topology_hints:
  requires:
    - git:init_repo
  conflicts_with:
    - git:reset_hard
---

# Git Commit Changes

This skill performs a Git commit operation.

## Usage

```python {entrypoint=true}
def main():
    import subprocess
    result = subprocess.run(['git', 'commit', '-m', 'message'])
    return result.returncode
```

## Helper Function

```python
def check_staged_files():
    """Check if there are staged files."""
    import subprocess
    result = subprocess.run(['git', 'diff', '--staged', '--name-only'])
    return result.stdout.strip() != ''
```

## Bash Alternative

```bash
#!/bin/bash
git commit -m "$1"
```
'''


@pytest.fixture
def minimal_skill_content() -> str:
    """最小有效技能文件内容。"""
    return """---
skill_id: test:minimal
version: 0.1.0
intent_description: A minimal test skill for basic functionality verification and unit testing purposes.
permissions:
  - fs:read:/tmp
---

# Minimal Skill

```text
Hello World
```
"""


@pytest.fixture
def no_frontmatter_content() -> str:
    """缺少 Frontmatter 的内容。"""
    return """# No Frontmatter

This file has no YAML frontmatter.

```python
def main():
    pass
```
"""


@pytest.fixture
def invalid_yaml_content() -> str:
    """包含无效 YAML 的内容（真正的 YAML 语法错误）。"""
    return """---
skill_id: invalid yaml
  version: broken indentation
intent_description: Test invalid YAML parsing behavior.
---

# Invalid YAML
"""


@pytest.fixture
def empty_content() -> str:
    """空内容。"""
    return ""


@pytest.fixture
def only_frontmatter_content() -> str:
    """只有 Frontmatter 的内容。"""
    return """---
skill_id: test:only_fm
version: 1.0.0
intent_description: Only frontmatter without any markdown content or code blocks included.
permissions:
  - fs:read:/tmp
---
"""


@pytest.fixture
def multiple_code_blocks_content() -> str:
    """包含多个代码块的内容。"""
    return """---
skill_id: test:multi_block
version: 1.0.0
intent_description: Test multiple code blocks extraction with different languages and metadata configurations.
permissions:
  - fs:read:/tmp
---

# Multiple Code Blocks

```python {entrypoint=true, timeout=30}
def main():
    pass
```

```javascript
function helper() {
    return true;
}
```

```bash {retry=3}
#!/bin/bash
echo "test"
```

```go
package main

func main() {
    println("hello")
}
```

```rust
fn main() {
    println!("hello");
}
```

```java
public class Main {
    public static void main(String[] args) {}
}
```

```text
Plain text block
```
"""


@pytest.fixture
def nested_code_content() -> str:
    """包含嵌套代码块的内容（边界测试）。"""
    return """---
skill_id: test:nested
version: 1.0.0
intent_description: Test nested code block handling and edge cases with backticks inside code.
permissions:
  - fs:read:/tmp
---

# Nested Code

```python
def print_markdown():
    # This contains backticks in string
    code = "```bash\\necho hello\\n```"
    print(code)
```
"""


@pytest.fixture
def unicode_content() -> str:
    """包含 Unicode 字符的内容。"""
    return """---
skill_id: test:unicode
version: 1.0.0
intent_description: 测试 Unicode 字符处理能力，包括中文、日文、韩文等多语言支持。
permissions:
  - fs:read:/tmp
---

# Unicode Test 🎉

```python
# 中文注释
def 你好():
    print("Hello 世界！")
```
"""


@pytest.fixture
def long_content() -> str:
    """长内容（性能测试）。"""
    intent_desc = "A comprehensive skill for testing parser performance with large file content. " * 10
    code_lines = "\n".join([f"    # Line {i}" for i in range(100)])
    return f"""---
skill_id: test:long
version: 1.0.0
intent_description: {intent_desc}
permissions:
  - fs:read:/tmp
---

# Long Content Test

```python
def main():
{code_lines}
    pass
```
"""


# =============================================================================
# Basic Parsing Tests
# =============================================================================


class TestMarkdownParserBasic:
    """基础解析功能测试。"""

    def test_parse_valid_file(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试解析有效文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(valid_skill_content)
            f.flush()
            file_path = Path(f.name)

        result = parser.parse(file_path)

        assert isinstance(result, ParsedSkillFile)
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert result.file_path == file_path
        assert len(result.code_blocks) == 3

        # 清理
        file_path.unlink()

    def test_parse_string(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试解析字符串内容。"""
        result = parser.parse_string(valid_skill_content)

        assert isinstance(result, ParsedSkillFile)
        assert result.skill_id == "git:commit_changes"
        assert result.frontmatter["version"] == "1.0.0"
        assert len(result.code_blocks) == 3

    def test_parse_minimal_file(self, parser: MarkdownParser, minimal_skill_content: str) -> None:
        """测试解析最小有效文件。"""
        result = parser.parse_string(minimal_skill_content)

        assert result.skill_id == "test:minimal"
        assert result.version == "0.1.0"
        assert len(result.code_blocks) == 1
        assert result.code_blocks[0].language == "text"

    def test_parse_file_not_found(self, parser: MarkdownParser) -> None:
        """测试文件不存在时的错误处理。"""
        with pytest.raises(ParseError) as exc_info:
            parser.parse(Path("/nonexistent/file.md"))

        assert "File not found" in str(exc_info.value)
        assert exc_info.value.file_path == Path("/nonexistent/file.md")

    def test_parse_directory_path(self, parser: MarkdownParser) -> None:
        """测试传入目录路径时的错误处理。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ParseError) as exc_info:
                parser.parse(Path(tmpdir))

            assert "not a file" in str(exc_info.value)


# =============================================================================
# Frontmatter Extraction Tests
# =============================================================================


class TestFrontmatterExtraction:
    """Frontmatter 提取测试。"""

    def test_extract_valid_frontmatter(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试提取有效 Frontmatter。"""
        result = parser.parse_string(valid_skill_content)

        assert result.frontmatter is not None
        assert result.frontmatter["skill_id"] == "git:commit_changes"
        assert result.frontmatter["version"] == "1.0.0"
        assert result.frontmatter["intent_description"] is not None
        assert len(result.frontmatter["permissions"]) == 3
        assert "git" in result.frontmatter["tags"]

    def test_frontmatter_line_numbers(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试 Frontmatter 行号定位。"""
        result = parser.parse_string(valid_skill_content)

        assert result.frontmatter_line_start == 1
        assert result.frontmatter_line_end > 1

    def test_missing_frontmatter_strict_mode(self, parser: MarkdownParser, no_frontmatter_content: str) -> None:
        """测试严格模式下缺少 Frontmatter。"""
        with pytest.raises(ParseError) as exc_info:
            parser.parse_string(no_frontmatter_content)

        assert "No valid YAML frontmatter" in str(exc_info.value)

    def test_missing_frontmatter_lenient_mode(self, lenient_parser: MarkdownParser, no_frontmatter_content: str) -> None:
        """测试非严格模式下缺少 Frontmatter。"""
        result = lenient_parser.parse_string(no_frontmatter_content)

        assert result.frontmatter == {}
        assert result.content == no_frontmatter_content

    def test_invalid_yaml_frontmatter(self, parser: MarkdownParser, invalid_yaml_content: str) -> None:
        """测试无效 YAML Frontmatter。"""
        # 严格模式下，无效 YAML 会抛出 ParseError
        with pytest.raises(ParseError) as exc_info:
            parser.parse_string(invalid_yaml_content)

        assert "YAML parsing error" in str(exc_info.value)

    def test_only_frontmatter(self, parser: MarkdownParser, only_frontmatter_content: str) -> None:
        """测试只有 Frontmatter 的文件。"""
        result = parser.parse_string(only_frontmatter_content)

        assert result.skill_id == "test:only_fm"
        assert len(result.code_blocks) == 0
        assert result.content.strip() == ""

    def test_frontmatter_dict_type(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试 Frontmatter 返回字典类型。"""
        result = parser.parse_string(valid_skill_content)

        assert isinstance(result.frontmatter, dict)


# =============================================================================
# Code Block Extraction Tests
# =============================================================================


class TestCodeBlockExtraction:
    """代码块提取测试。"""

    def test_extract_single_code_block(self, parser: MarkdownParser, minimal_skill_content: str) -> None:
        """测试提取单个代码块。"""
        result = parser.parse_string(minimal_skill_content)

        assert len(result.code_blocks) == 1
        block = result.code_blocks[0]

        assert block.language == "text"
        assert block.code == "Hello World"
        assert block.line_start > 0
        assert block.line_end > block.line_start

    def test_extract_multiple_code_blocks(self, parser: MarkdownParser, multiple_code_blocks_content: str) -> None:
        """测试提取多个代码块。"""
        result = parser.parse_string(multiple_code_blocks_content)

        assert len(result.code_blocks) == 7

        # 检查各语言
        languages = [block.language for block in result.code_blocks]
        assert "python" in languages
        assert "javascript" in languages
        assert "bash" in languages
        assert "go" in languages
        assert "rust" in languages
        assert "java" in languages
        assert "text" in languages

    def test_code_block_line_numbers(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试代码块行号定位。"""
        result = parser.parse_string(valid_skill_content)

        for block in result.code_blocks:
            assert block.line_start > 0
            assert block.line_end >= block.line_start
            assert block.line_count >= 1

    def test_entrypoint_detection(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试入口点检测。"""
        result = parser.parse_string(valid_skill_content)

        entrypoint = parser.get_entrypoint_block(result)
        assert entrypoint is not None
        assert entrypoint.is_entrypoint
        assert entrypoint.language == "python"

    def test_no_entrypoint(self, parser: MarkdownParser, minimal_skill_content: str) -> None:
        """测试无入口点的情况。"""
        result = parser.parse_string(minimal_skill_content)

        entrypoint = parser.get_entrypoint_block(result)
        assert entrypoint is None

    def test_code_block_metadata(self, parser: MarkdownParser, multiple_code_blocks_content: str) -> None:
        """测试代码块元数据解析。"""
        result = parser.parse_string(multiple_code_blocks_content)

        # 找到 Python 块（有 entrypoint 和 timeout）
        python_block = next(b for b in result.code_blocks if b.language == "python")
        assert python_block.metadata is not None
        assert python_block.metadata.get("entrypoint") is True
        assert python_block.metadata.get("timeout") == 30

        # 找到 Bash 块（有 retry）
        bash_block = next(b for b in result.code_blocks if b.language == "bash")
        assert bash_block.metadata is not None
        assert bash_block.metadata.get("retry") == 3

    def test_code_block_content(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试代码块内容提取。"""
        result = parser.parse_string(valid_skill_content)

        python_block = next(b for b in result.code_blocks if b.language == "python" and b.is_entrypoint)
        assert "def main()" in python_block.code
        assert "subprocess" in python_block.code

    def test_get_blocks_by_language(self, parser: MarkdownParser, multiple_code_blocks_content: str) -> None:
        """测试按语言筛选代码块。"""
        result = parser.parse_string(multiple_code_blocks_content)

        python_blocks = parser.get_blocks_by_language(result, "python")
        assert len(python_blocks) == 1
        assert python_blocks[0].language == "python"

        # 不存在的语言
        ruby_blocks = parser.get_blocks_by_language(result, "ruby")
        assert len(ruby_blocks) == 0

    def test_code_block_without_language(self, parser: MarkdownParser) -> None:
        """测试无语言标记的代码块。"""
        content = """---
skill_id: test:no_lang
version: 1.0.0
intent_description: Test code block without explicit language specification in the markdown.
permissions:
  - fs:read:/tmp
---

```
plain code
```
"""
        result = parser.parse_string(content)

        assert len(result.code_blocks) == 1
        # 无语言标记默认为 text
        assert result.code_blocks[0].language == "text"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """错误处理测试。"""

    def test_parse_error_properties(self, parser: MarkdownParser) -> None:
        """测试 ParseError 属性。"""
        error = ParseError(
            message="Test error",
            file_path=Path("/test/path.md"),
            line_number=10
        )

        assert error.message == "Test error"
        assert error.file_path == Path("/test/path.md")
        assert error.line_number == 10
        assert error.code == "GS-2000"

    def test_parse_error_to_dict(self, parser: MarkdownParser) -> None:
        """测试 ParseError 序列化。"""
        error = ParseError(
            message="Test error",
            file_path=Path("/test/path.md"),
            line_number=10
        )

        result = error.to_dict()
        # to_dict 返回嵌套结构 {"error": {...}}
        assert result["error"]["message"] == "Test error"
        assert result["file_path"] == "/test/path.md"
        assert result["line_number"] == 10
        assert result["error"]["code"] == "GS-2000"

    def test_parse_error_without_optional_fields(self, parser: MarkdownParser) -> None:
        """测试 ParseError 无可选字段。"""
        error = ParseError(message="Simple error")

        result = error.to_dict()
        assert "file_path" not in result
        assert "line_number" not in result

    def test_unicode_decode_error(self, parser: MarkdownParser) -> None:
        """测试 Unicode 解码错误。"""
        # 创建一个包含非 UTF-8 字符的文件
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".md", delete=False) as f:
            f.write(b"\xff\xfe Invalid UTF-8")
            f.flush()
            file_path = Path(f.name)

        with pytest.raises(ParseError) as exc_info:
            parser.parse(file_path)

        assert "encoding error" in str(exc_info.value).lower()

        file_path.unlink()

    def test_empty_file_strict_mode(self, parser: MarkdownParser, empty_content: str) -> None:
        """测试空文件（严格模式）。"""
        with pytest.raises(ParseError) as exc_info:
            parser.parse_string(empty_content)

        assert "No valid YAML frontmatter" in str(exc_info.value)

    def test_empty_file_lenient_mode(self, lenient_parser: MarkdownParser, empty_content: str) -> None:
        """测试空文件（非严格模式）。"""
        result = lenient_parser.parse_string(empty_content)

        assert result.frontmatter == {}
        assert result.content == ""
        assert len(result.code_blocks) == 0


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """边界条件测试。"""

    def test_nested_backticks(self, parser: MarkdownParser, nested_code_content: str) -> None:
        """测试嵌套反引号。"""
        result = parser.parse_string(nested_code_content)

        # 应该只提取一个代码块（外层的）
        assert len(result.code_blocks) == 1
        assert "```bash" in result.code_blocks[0].code

    def test_unicode_content(self, parser: MarkdownParser, unicode_content: str) -> None:
        """测试 Unicode 内容。"""
        result = parser.parse_string(unicode_content)

        assert result.skill_id == "test:unicode"
        assert "中文" in result.frontmatter["intent_description"]
        assert len(result.code_blocks) == 1
        assert "你好" in result.code_blocks[0].code

    def test_long_content(self, parser: MarkdownParser, long_content: str) -> None:
        """测试长内容（性能）。"""
        result = parser.parse_string(long_content)

        assert result.skill_id == "test:long"
        assert len(result.code_blocks) == 1
        # 验证代码块包含所有行
        assert "Line 99" in result.code_blocks[0].code

    def test_frontmatter_with_special_characters(self, parser: MarkdownParser) -> None:
        """测试 Frontmatter 包含特殊字符。"""
        content = """---
skill_id: test:special
version: 1.0.0
intent_description: "Test with special chars: :colon, :dash, _underscore"
permissions:
  - fs:read:/tmp/special-path_123
---
"""
        result = parser.parse_string(content)

        assert result.skill_id == "test:special"
        assert "special chars" in result.frontmatter["intent_description"]

    def test_multiline_intent_description(self, parser: MarkdownParser) -> None:
        """测试多行意图描述。"""
        content = """---
skill_id: test:multiline
version: 1.0.0
intent_description: |
  This is a multiline description.
  It spans multiple lines.
  Each line provides additional context.
permissions:
  - fs:read:/tmp
---
"""
        result = parser.parse_string(content)

        assert result.skill_id == "test:multiline"
        assert "multiline" in result.frontmatter["intent_description"]
        assert "additional context" in result.frontmatter["intent_description"]

    def test_consecutive_code_blocks(self, parser: MarkdownParser) -> None:
        """测试连续代码块。"""
        content = """---
skill_id: test:consecutive
version: 1.0.0
intent_description: Test consecutive code blocks without any intervening text or content.
permissions:
  - fs:read:/tmp
---
```python
def a():
    pass
```
```python
def b():
    pass
```
"""
        result = parser.parse_string(content)

        assert len(result.code_blocks) == 2
        assert result.code_blocks[0].name != result.code_blocks[1].name if hasattr(result.code_blocks[0], 'name') else True

    def test_code_block_with_empty_lines(self, parser: MarkdownParser) -> None:
        """测试包含空行的代码块。"""
        content = """---
skill_id: test:empty_lines
version: 1.0.0
intent_description: Test code block with empty lines inside the code content block.
permissions:
  - fs:read:/tmp
---

```python
def main():

    # Empty line above


    pass
```
"""
        result = parser.parse_string(content)

        assert len(result.code_blocks) == 1
        assert "\n\n" in result.code_blocks[0].code


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestDataStructures:
    """数据结构测试。"""

    def test_parsed_skill_file_properties(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试 ParsedSkillFile 属性。"""
        result = parser.parse_string(valid_skill_content)

        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert result.raw_content == valid_skill_content

    def test_code_block_properties(self, parser: MarkdownParser) -> None:
        """测试 CodeBlock 属性。"""
        block = CodeBlock(
            language="python",
            code="def main(): pass",
            line_start=10,
            line_end=12,
            metadata={"timeout": 30},
            is_entrypoint=True
        )

        assert block.language == "python"
        assert block.line_count == 3  # 12 - 10 + 1
        assert block.is_entrypoint
        assert block.metadata["timeout"] == 30

    def test_code_block_default_values(self, parser: MarkdownParser) -> None:
        """测试 CodeBlock 默认值。"""
        block = CodeBlock(
            language="text",
            code="hello",
            line_start=1,
            line_end=2
        )

        assert block.metadata is None
        assert block.is_entrypoint is False

    def test_parsed_skill_file_default_values(self, parser: MarkdownParser) -> None:
        """测试 ParsedSkillFile 默认值。"""
        result = ParsedSkillFile(
            file_path=Path("/test.md"),
            frontmatter={"skill_id": "test:default"},
            content="test"
        )

        assert result.code_blocks == []
        assert result.raw_content == ""
        assert result.frontmatter_line_start == 1
        assert result.frontmatter_line_end == 0


# =============================================================================
# Metadata Parsing Tests
# =============================================================================


class TestMetadataParsing:
    """元数据解析测试。"""

    def test_boolean_metadata(self, parser: MarkdownParser) -> None:
        """测试布尔元数据。"""
        content = """---
skill_id: test:bool_meta
version: 1.0.0
intent_description: Test boolean metadata parsing in code block configuration.
permissions:
  - fs:read:/tmp
---

```python {entrypoint=true, debug=false}
def main():
    pass
```
"""
        result = parser.parse_string(content)

        assert result.code_blocks[0].metadata["entrypoint"] is True
        assert result.code_blocks[0].metadata["debug"] is False

    def test_numeric_metadata(self, parser: MarkdownParser) -> None:
        """测试数值元数据。"""
        content = """---
skill_id: test:num_meta
version: 1.0.0
intent_description: Test numeric metadata parsing with integer and float values.
permissions:
  - fs:read:/tmp
---

```python {timeout=30, ratio=0.5}
def main():
    pass
```
"""
        result = parser.parse_string(content)

        assert result.code_blocks[0].metadata["timeout"] == 30
        assert result.code_blocks[0].metadata["ratio"] == 0.5

    def test_string_metadata(self, parser: MarkdownParser) -> None:
        """测试字符串元数据。"""
        content = """---
skill_id: test:str_meta
version: 1.0.0
intent_description: Test string metadata parsing with quoted and unquoted values.
permissions:
  - fs:read:/tmp
---

```python {name="main", type='function'}
def main():
    pass
```
"""
        result = parser.parse_string(content)

        assert result.code_blocks[0].metadata["name"] == "main"
        assert result.code_blocks[0].metadata["type"] == "function"

    def test_complex_metadata(self, parser: MarkdownParser) -> None:
        """测试复杂元数据。"""
        content = """---
skill_id: test:complex_meta
version: 1.0.0
intent_description: Test complex metadata with multiple key-value pairs of different types.
permissions:
  - fs:read:/tmp
---

```python {entrypoint=true, timeout=60, retry=3, name="handler", debug=false}
def main():
    pass
```
"""
        result = parser.parse_string(content)

        meta = result.code_blocks[0].metadata
        assert meta["entrypoint"] is True
        assert meta["timeout"] == 60
        assert meta["retry"] == 3
        assert meta["name"] == "handler"
        assert meta["debug"] is False


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """性能测试。"""

    @pytest.mark.slow
    def test_large_file_parsing(self, parser: MarkdownParser) -> None:
        """测试大文件解析性能。"""
        # 生成大文件内容
        intent_desc = "Large file test. " * 100
        code_blocks = []
        for i in range(50):
            code_blocks.append(f"""
```python
def function_{i}():
    # Function {i}
    pass
```
""")
        
        content = f"""---
skill_id: test:large
version: 1.0.0
intent_description: {intent_desc}
permissions:
  - fs:read:/tmp
---

# Large File

{''.join(code_blocks)}
"""

        result = parser.parse_string(content)

        assert result.skill_id == "test:large"
        assert len(result.code_blocks) == 50

    @pytest.mark.slow
    def test_repeated_parsing(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试重复解析性能。"""
        for _ in range(100):
            result = parser.parse_string(valid_skill_content)
            assert result.skill_id == "git:commit_changes"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """集成测试。"""

    def test_full_workflow(self, parser: MarkdownParser, valid_skill_content: str) -> None:
        """测试完整工作流。"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(valid_skill_content)
            f.flush()
            file_path = Path(f.name)

        # 解析
        result = parser.parse(file_path)

        # 验证所有属性
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert len(result.code_blocks) == 3

        # 获取入口点
        entrypoint = parser.get_entrypoint_block(result)
        assert entrypoint is not None

        # 按语言筛选
        python_blocks = parser.get_blocks_by_language(result, "python")
        assert len(python_blocks) == 2

        # 清理
        file_path.unlink()

    def test_skill_id_property_none(self, parser: MarkdownParser) -> None:
        """测试 skill_id 属性为 None。"""
        result = ParsedSkillFile(
            file_path=Path("/test.md"),
            frontmatter={},  # 无 skill_id
            content="test"
        )

        assert result.skill_id is None

    def test_version_property_none(self, parser: MarkdownParser) -> None:
        """测试 version 属性为 None。"""
        result = ParsedSkillFile(
            file_path=Path("/test.md"),
            frontmatter={"skill_id": "test:no_version"},
            content="test"
        )

        assert result.version is None
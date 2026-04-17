"""
性能基准测试：解析器模块。

测试解析器的性能指标：
- 单文件解析时间
- 批量解析吞吐量
- 内存占用

Reference: plans/phase_03_e2e_plan.md
"""

from __future__ import annotations

import os
import pytest
import time
import tempfile
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from graphskill.ingestion.parser.markdown_parser import MarkdownParser
from graphskill.ingestion.parser.yaml_parser import YAMLParser
from graphskill.ingestion.parser.ast_parser import ASTParser


# ============================================================================
# Benchmark Helpers
# ============================================================================

@dataclass
class BenchmarkResult:
    """基准测试结果."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    throughput: float  # ops per second
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "throughput": self.throughput,
        }


def benchmark(func, iterations: int = 100) -> BenchmarkResult:
    """
    执行基准测试.
    
    Args:
        func: 要测试的函数
        iterations: 迭代次数
    
    Returns:
        BenchmarkResult: 测试结果
    """
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    total_time = sum(times)
    avg_time = total_time / iterations
    min_time = min(times)
    max_time = max(times)
    throughput = iterations / (total_time / 1000)  # ops per second
    
    return BenchmarkResult(
        name=func.__name__ if hasattr(func, '__name__') else "benchmark",
        iterations=iterations,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        min_time_ms=min_time,
        max_time_ms=max_time,
        throughput=throughput,
    )


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Markdown 解析器."""
    return MarkdownParser(strict_mode=True)


@pytest.fixture
def yaml_parser() -> YAMLParser:
    """YAML 解析器."""
    return YAMLParser(strict_mode=True)


@pytest.fixture
def ast_parser() -> ASTParser:
    """AST 解析器."""
    return ASTParser(use_tree_sitter=False)


@pytest.fixture
def sample_skill_content() -> str:
    """示例技能内容."""
    return """---
skill_id: "test:benchmark"
version: "1.0.0"
intent_description: "A benchmark test skill for performance measurement"
permissions:
  - "fs:read:./**"
  - "exec:test:run"
topology_hints:
  requires:
    - "fs:exists"
  provides:
    - "test:result"
tags:
  - "benchmark"
  - "test"
author: "Benchmark Team"
---

# Benchmark Test Skill

## Description

This is a test skill for benchmarking parser performance.

## Code Implementation

```python
def benchmark_function():
    '''A simple benchmark function.'''
    return "benchmark_result"

def another_function(data: list):
    '''Process data for benchmarking.'''
    results = []
    for item in data:
        results.append(process_item(item))
    return results
```

```bash
#!/bin/bash
echo "Running benchmark"
```
"""


@pytest.fixture
def sample_yaml_dict() -> dict[str, Any]:
    """示例 YAML 字典."""
    return {
        "skill_id": "test:benchmark",
        "version": "1.0.0",
        "intent_description": "A benchmark test skill for performance measurement with detailed intent description for testing purposes",
        "permissions": ["fs:read:./repo", "exec:test:run"],
        "topology_hints": {
            "requires": ["fs:exists"],
            "provides": ["test:result"],
        },
        "tags": ["benchmark", "test"],
        "author": "Benchmark Team",
    }


@pytest.fixture
def sample_python_code() -> str:
    """示例 Python 代码."""
    return '''
def main():
    """Main entry point."""
    data = load_data()
    results = process_data(data)
    save_results(results)
    return results

def load_data():
    """Load data from file."""
    with open("data.json", "r") as f:
        return json.load(f)

def process_data(data: list) -> list:
    """Process the data."""
    return [transform(item) for item in data]

def transform(item: dict) -> dict:
    """Transform a single item."""
    return {
        "id": item.get("id"),
        "value": item.get("value") * 2,
    }

def save_results(results: list):
    """Save results to file."""
    with open("results.json", "w") as f:
        json.dump(results, f)

if __name__ == "__main__":
    main()
'''


@pytest.fixture
def temp_skill_file(sample_skill_content: str) -> Path:
    """临时技能文件."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".SKILL.md",
        delete=False
    ) as f:
        f.write(sample_skill_content)
        path = Path(f.name)
    
    yield path
    
    # Cleanup
    if path.exists():
        path.unlink()


# ============================================================================
# Benchmark Tests
# ============================================================================

class TestMarkdownParserBenchmark:
    """Markdown 解析器基准测试."""
    
    @pytest.mark.benchmark
    def test_parse_single_file_benchmark(
        self,
        markdown_parser: MarkdownParser,
        temp_skill_file: Path,
    ) -> None:
        """单文件解析基准测试."""
        result = benchmark(
            lambda: markdown_parser.parse(temp_skill_file),
            iterations=100,
        )
        
        print(f"\nMarkdown Parser Single File Benchmark:")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Min time: {result.min_time_ms:.2f} ms")
        print(f"  Max time: {result.max_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} ops/sec")
        
        # Performance assertions
        assert result.avg_time_ms < 50, "Single file parse should be < 50ms"
        assert result.throughput > 20, "Should parse > 20 files per second"
    
    @pytest.mark.benchmark
    def test_parse_string_benchmark(
        self,
        markdown_parser: MarkdownParser,
        sample_skill_content: str,
    ) -> None:
        """字符串解析基准测试."""
        result = benchmark(
            lambda: markdown_parser.parse_string(sample_skill_content),
            iterations=200,
        )
        
        print(f"\nMarkdown Parser String Benchmark:")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} ops/sec")
        
        assert result.avg_time_ms < 30, "String parse should be < 30ms"
    
    @pytest.mark.benchmark
    def test_extract_code_blocks_benchmark(
        self,
        markdown_parser: MarkdownParser,
        sample_skill_content: str,
    ) -> None:
        """代码块提取基准测试."""
        parsed = markdown_parser.parse_string(sample_skill_content)
        
        result = benchmark(
            lambda: parsed.code_blocks,
            iterations=1000,
        )
        
        print(f"\nCode Block Extraction Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.4f} ms")
        
        assert result.avg_time_ms < 1, "Code block access should be < 1ms"


class TestYAMLParserBenchmark:
    """YAML 解析器基准测试."""
    
    @pytest.mark.benchmark
    def test_parse_dict_benchmark(
        self,
        yaml_parser: YAMLParser,
        sample_yaml_dict: dict[str, Any],
    ) -> None:
        """字典解析基准测试."""
        result = benchmark(
            lambda: yaml_parser.parse(sample_yaml_dict),
            iterations=500,
        )
        
        print(f"\nYAML Parser Dict Benchmark:")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} ops/sec")
        
        assert result.avg_time_ms < 10, "Dict parse should be < 10ms"
        assert result.throughput > 100, "Should parse > 100 dicts per second"
    
    @pytest.mark.benchmark
    def test_validate_fields_benchmark(
        self,
        yaml_parser: YAMLParser,
        sample_yaml_dict: dict[str, Any],
    ) -> None:
        """字段验证基准测试."""
        result = benchmark(
            lambda: yaml_parser.parse(sample_yaml_dict),
            iterations=500,
        )
        
        print(f"\nYAML Field Validation Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        
        assert result.avg_time_ms < 10, "Validation should be < 10ms"


class TestASTParserBenchmark:
    """AST 解析器基准测试."""
    
    @pytest.mark.benchmark
    def test_parse_python_benchmark(
        self,
        ast_parser: ASTParser,
        sample_python_code: str,
    ) -> None:
        """Python 代码解析基准测试."""
        result = benchmark(
            lambda: ast_parser.parse(sample_python_code, language="python"),
            iterations=100,
        )
        
        print(f"\nAST Parser Python Benchmark:")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} ops/sec")
        
        assert result.avg_time_ms < 100, "Python parse should be < 100ms"
    
    @pytest.mark.benchmark
    def test_parse_bash_benchmark(
        self,
        ast_parser: ASTParser,
    ) -> None:
        """Bash 代码解析基准测试."""
        bash_code = '''
#!/bin/bash

function main() {
    echo "Starting process"
    process_data
    echo "Process complete"
}

function process_data() {
    for file in *.txt; do
        cat "$file" | grep "pattern"
    done
}

main
'''
        
        result = benchmark(
            lambda: ast_parser.parse(bash_code, language="bash"),
            iterations=100,
        )
        
        print(f"\nAST Parser Bash Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        
        assert result.avg_time_ms < 100, "Bash parse should be < 100ms"


class TestBatchParsingBenchmark:
    """批量解析基准测试."""
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_batch_file_parsing_benchmark(
        self,
        markdown_parser: MarkdownParser,
        sample_skill_content: str,
    ) -> None:
        """批量文件解析基准测试."""
        # Create multiple temp files
        temp_files = []
        for i in range(50):
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".SKILL.md",
                delete=False
            ) as f:
                f.write(sample_skill_content)
                temp_files.append(Path(f.name))
        
        def parse_all():
            results = []
            for file_path in temp_files:
                results.append(markdown_parser.parse(file_path))
            return results
        
        result = benchmark(parse_all, iterations=10)
        
        print(f"\nBatch File Parsing Benchmark (50 files):")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} batches/sec")
        print(f"  Per-file time: {result.avg_time_ms / 50:.2f} ms")
        
        # Cleanup
        for path in temp_files:
            if path.exists():
                path.unlink()
        
        assert result.avg_time_ms < 2000, "Batch parse should be < 2s"
    
    @pytest.mark.benchmark
    def test_batch_dict_parsing_benchmark(
        self,
        yaml_parser: YAMLParser,
        sample_yaml_dict: dict[str, Any],
    ) -> None:
        """批量字典解析基准测试."""
        dicts = [sample_yaml_dict.copy() for _ in range(100)]
        
        def parse_all():
            results = []
            for d in dicts:
                results.append(yaml_parser.parse(d))
            return results
        
        result = benchmark(parse_all, iterations=20)
        
        print(f"\nBatch Dict Parsing Benchmark (100 dicts):")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Per-dict time: {result.avg_time_ms / 100:.2f} ms")
        
        assert result.avg_time_ms < 500, "Batch dict parse should be < 500ms"


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
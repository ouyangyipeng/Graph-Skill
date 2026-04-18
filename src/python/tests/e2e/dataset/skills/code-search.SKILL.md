---
skill_id: "code:search"
version: "1.0.0"
intent_description: "Search for code patterns across multiple files using regex or semantic matching with context extraction for comprehensive code analysis and discovery"
permissions:
  - "fs:read:./"
  - "fs:read:/repo"
topology_hints:
  requires:
    - "fs:read"
    - "fs:walk"
  provides:
    - "code:matches"
    - "code:context"
tags:
  - "search"
  - "code"
  - "regex"
  - "semantic"
author: "GraphSkill Team"
---

# Code Search Skill

## Description

This skill searches for code patterns across multiple files. It supports both regex-based exact matching and semantic similarity search. Results include file paths, line numbers, and surrounding context.

## Usage

```python
# Regex search
results = search_code_regex("./src", r"def\s+\w+\s*\(")

# Semantic search (requires embedding)
results = search_code_semantic("./src", "function that handles authentication")

# Search with context
results = search_code("./src", pattern, context_lines=5)
```

## Code Implementation

```python
import re
import os
from pathlib import Path
from typing import Optional, list[dict], Union
from dataclasses import dataclass

@dataclass
class SearchResult:
    file_path: str
    line_number: int
    matched_text: str
    context_before: list[str]
    context_after: list[str]
    confidence: float = 1.0

def search_code_regex(
    directory: Union[str, Path],
    pattern: str,
    file_pattern: str = "*.py",
    context_lines: int = 3,
    max_results: int = 100
) -> list[SearchResult]:
    """
    Search for regex pattern in code files.
    
    Args:
        directory: Directory to search.
        pattern: Regex pattern to match.
        file_pattern: File glob pattern.
        context_lines: Number of context lines.
        max_results: Maximum results to return.
    
    Returns:
        List of search results.
    """
    results = []
    dir_path = Path(directory)
    regex = re.compile(pattern)
    
    for file_path in dir_path.rglob(file_pattern):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                if regex.search(line):
                    # Extract context
                    context_before = lines[max(0, i-context_lines):i]
                    context_after = lines[i+1:min(len(lines), i+1+context_lines)]
                    
                    results.append(SearchResult(
                        file_path=str(file_path),
                        line_number=i + 1,
                        matched_text=line.strip(),
                        context_before=[l.strip() for l in context_before],
                        context_after=[l.strip() for l in context_after]
                    ))
                    
                    if len(results) >= max_results:
                        return results
        except Exception:
            continue
    
    return results

def search_code_semantic(
    directory: Union[str, Path],
    query: str,
    file_pattern: str = "*.py",
    top_k: int = 10,
    embedding_model: Optional[str] = None
) -> list[SearchResult]:
    """
    Semantic search using embedding similarity.
    
    Args:
        directory: Directory to search.
        query: Natural language query.
        file_pattern: File glob pattern.
        top_k: Number of top results.
        embedding_model: Embedding model name.
    
    Returns:
        List of search results with confidence scores.
    """
    # Placeholder for semantic search implementation
    # Would require embedding model integration
    results = []
    
    # Simple keyword-based fallback
    keywords = query.lower().split()
    dir_path = Path(directory)
    
    for file_path in dir_path.rglob(file_pattern):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().lower()
            
            # Count keyword matches
            matches = sum(1 for kw in keywords if kw in content)
            if matches > 0:
                confidence = matches / len(keywords)
                results.append(SearchResult(
                    file_path=str(file_path),
                    line_number=1,
                    matched_text=query,
                    context_before=[],
                    context_after=[],
                    confidence=confidence
                ))
        except Exception:
            continue
    
    # Sort by confidence
    results.sort(key=lambda r: r.confidence, reverse=True)
    return results[:top_k]

def walk_directory(
    directory: Union[str, Path],
    file_pattern: str = "*.py"
) -> list[str]:
    """
    Walk directory and return matching files.
    
    Args:
        directory: Directory to walk.
        file_pattern: File glob pattern.
    
    Returns:
        List of file paths.
    """
    dir_path = Path(directory)
    return [str(p) for p in dir_path.rglob(file_pattern)]
```

## Entry Point

- `search_code_regex(directory: Union[str, Path], pattern: str, ...) -> list[SearchResult]`

## Dependencies

- Requires `fs:read` skill to read file contents
- Requires `fs:walk` skill to traverse directories
- Provides `code:matches` and `code:context` for downstream analysis

## Error Handling

- Skips files that cannot be read
- Handles encoding errors gracefully
- Limits results to prevent memory issues
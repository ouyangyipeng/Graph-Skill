---
skill_id: "fs:read"
version: "1.0.0"
intent_description: "Read file contents from the filesystem with support for various encoding formats and partial reading capabilities for efficient data access and processing"
permissions:
  - "fs:read:/tmp"
  - "fs:read:./"
topology_hints:
  provides:
    - "fs:content"
  requires:
    - "fs:exists"
tags:
  - "filesystem"
  - "read"
  - "io"
author: "GraphSkill Team"
---

# File Read Skill

## Description

This skill reads file contents from the filesystem. It supports various encoding formats, partial reading (lines or bytes), and handles large files efficiently.

## Usage

```python
# Read entire file
content = read_file("/path/to/file.txt")

# Read specific lines
lines = read_file_lines("/path/to/file.txt", start=0, end=100)

# Read with specific encoding
content = read_file("/path/to/file.txt", encoding="utf-8")
```

## Code Implementation

```python
import os
from pathlib import Path
from typing import Optional, Union

def read_file(
    file_path: Union[str, Path],
    encoding: str = "utf-8",
    max_size: Optional[int] = None
) -> str:
    """
    Read entire file contents.
    
    Args:
        file_path: Path to the file.
        encoding: File encoding (default: utf-8).
        max_size: Maximum bytes to read (optional).
    
    Returns:
        File contents as string.
    
    Raises:
        FileNotFoundError: If file doesn't exist.
        PermissionError: If no read permission.
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    # Check file size
    file_size = path.stat().st_size
    if max_size and file_size > max_size:
        raise ValueError(f"File too large: {file_size} > {max_size}")
    
    with open(path, "r", encoding=encoding) as f:
        return f.read()

def read_file_lines(
    file_path: Union[str, Path],
    start: int = 0,
    end: Optional[int] = None,
    encoding: str = "utf-8"
) -> list[str]:
    """
    Read specific lines from a file.
    
    Args:
        file_path: Path to the file.
        start: Starting line index (0-based).
        end: Ending line index (exclusive, optional).
        encoding: File encoding.
    
    Returns:
        List of lines.
    """
    path = Path(file_path)
    
    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()
    
    if end is None:
        return lines[start:]
    return lines[start:end]

def read_file_bytes(
    file_path: Union[str, Path],
    offset: int = 0,
    length: Optional[int] = None
) -> bytes:
    """
    Read file as bytes.
    
    Args:
        file_path: Path to the file.
        offset: Byte offset to start reading.
        length: Number of bytes to read.
    
    Returns:
        File contents as bytes.
    """
    path = Path(file_path)
    
    with open(path, "rb") as f:
        if offset:
            f.seek(offset)
        if length:
            return f.read(length)
        return f.read()

def file_exists(file_path: Union[str, Path]) -> bool:
    """
    Check if a file exists.
    
    Args:
        file_path: Path to check.
    
    Returns:
        True if file exists, False otherwise.
    """
    return Path(file_path).is_file()
```

## Entry Point

- `read_file(file_path: Union[str, Path], encoding: str = "utf-8", max_size: Optional[int] = None) -> str`

## Dependencies

- Requires `fs:exists` skill to verify file existence before reading
- Provides `fs:content` output for downstream processing

## Error Handling

- Raises `FileNotFoundError` for missing files
- Raises `PermissionError` for access denied
- Raises `ValueError` for invalid paths or oversized files
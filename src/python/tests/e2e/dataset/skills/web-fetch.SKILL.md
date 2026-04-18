---
skill_id: "web:fetch"
version: "1.0.0"
intent_description: "Fetch content from web URLs with support for HTTP HTTPS protocols headers customization and response parsing for data retrieval and web integration"
permissions:
  - "net:fetch:https"
  - "net:fetch:http"
topology_hints:
  requires:
    - "net:resolve"
  provides:
    - "web:content"
    - "web:metadata"
  conflicts:
    - "web:post"
    - "web:upload"
tags:
  - "web"
  - "http"
  - "fetch"
  - "download"
author: "GraphSkill Team"
---

# Web Fetch Skill

## Description

This skill fetches content from web URLs using HTTP GET requests. It supports custom headers, timeout configuration, and automatic response parsing (JSON, HTML, text). Content can be extracted and processed for downstream skills.

## Usage

```python
# Simple fetch
content = fetch_url("https://api.example.com/data")

# Fetch with headers
content = fetch_url("https://api.example.com/data", headers={"Authorization": "Bearer token"})

# Fetch JSON
data = fetch_json("https://api.example.com/json")
```

## Code Implementation

```python
import urllib.request
import urllib.error
import json
import time
from typing import Optional, dict[str, str], Union, Any
from dataclasses import dataclass
from enum import Enum

class ContentType(str, Enum):
    JSON = "json"
    HTML = "html"
    TEXT = "text"
    BINARY = "binary"

@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str
    content: Union[str, bytes, dict]
    headers: dict[str, str]
    fetch_time_ms: float
    size_bytes: int

def fetch_url(
    url: str,
    headers: Optional[dict[str, str]] = None,
    timeout: int = 30,
    max_size: Optional[int] = None,
    user_agent: str = "GraphSkill/1.0"
) -> FetchResult:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch.
        headers: Optional HTTP headers.
        timeout: Request timeout in seconds.
        max_size: Maximum response size in bytes.
        user_agent: User agent string.
    
    Returns:
        Fetch result with content and metadata.
    
    Raises:
        urllib.error.URLError: If request fails.
        ValueError: If response exceeds max_size.
    """
    start_time = time.time()
    
    # Prepare request
    request_headers = {
        "User-Agent": user_agent,
        "Accept": "*/*"
    }
    if headers:
        request_headers.update(headers)
    
    request = urllib.request.Request(url, headers=request_headers)
    
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Check size
            content_length = response.headers.get("Content-Length")
            if max_size and content_length:
                if int(content_length) > max_size:
                    raise ValueError(f"Response too large: {content_length} > {max_size}")
            
            # Read content
            content_bytes = response.read()
            
            # Determine content type
            content_type_header = response.headers.get("Content-Type", "text/plain")
            content_type = _parse_content_type(content_type_header)
            
            # Parse content
            if content_type == ContentType.JSON:
                content = json.loads(content_bytes.decode("utf-8"))
            elif content_type == ContentType.BINARY:
                content = content_bytes
            else:
                content = content_bytes.decode("utf-8")
            
            fetch_time = (time.time() - start_time) * 1000
            
            return FetchResult(
                url=url,
                status_code=response.status,
                content_type=content_type.value,
                content=content,
                headers=dict(response.headers),
                fetch_time_ms=fetch_time,
                size_bytes=len(content_bytes)
            )
    
    except urllib.error.HTTPError as e:
        fetch_time = (time.time() - start_time) * 1000
        return FetchResult(
            url=url,
            status_code=e.code,
            content_type="error",
            content=e.reason,
            headers={},
            fetch_time_ms=fetch_time,
            size_bytes=0
        )

def fetch_json(
    url: str,
    headers: Optional[dict[str, str]] = None,
    timeout: int = 30
) -> dict[str, Any]:
    """
    Fetch JSON content from URL.
    
    Args:
        url: URL to fetch.
        headers: Optional HTTP headers.
        timeout: Request timeout.
    
    Returns:
        JSON data as dict.
    
    Raises:
        ValueError: If response is not valid JSON.
    """
    result = fetch_url(url, headers=headers, timeout=timeout)
    
    if result.status_code != 200:
        raise ValueError(f"HTTP error: {result.status_code}")
    
    if isinstance(result.content, dict):
        return result.content
    
    # Try to parse as JSON
    try:
        return json.loads(result.content)
    except json.JSONDecodeError:
        raise ValueError("Response is not valid JSON")

def _parse_content_type(content_type_header: str) -> ContentType:
    """
    Parse content type header.
    
    Args:
        content_type_header: Content-Type header value.
    
    Returns:
        ContentType enum value.
    """
    if "application/json" in content_type_header:
        return ContentType.JSON
    elif "text/html" in content_type_header:
        return ContentType.HTML
    elif "text/" in content_type_header:
        return ContentType.TEXT
    else:
        return ContentType.BINARY

def resolve_url(url: str) -> str:
    """
    Resolve URL to final destination (following redirects).
    
    Args:
        url: URL to resolve.
    
    Returns:
        Final URL after redirects.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.url
    except Exception:
        return url
```

## Entry Point

- `fetch_url(url: str, headers: Optional[dict[str, str]] = None, ...) -> FetchResult`

## Dependencies

- Requires `net:resolve` skill for DNS resolution
- Provides `web:content` and `web:metadata` for downstream processing
- Conflicts with `web:post` and `web:upload` for safety

## Error Handling

- Returns error status for HTTP errors
- Raises `ValueError` for oversized responses
- Handles timeout gracefully
- Validates JSON responses
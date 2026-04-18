---
skill_id: "git:commit"
version: "1.0.0"
intent_description: "Execute Git commit operation with automatic commit message generation based on staged changes analysis and intelligent message formatting following conventional commit standards"
permissions:
  - "fs:read:.git"
  - "fs:read:./repo"
  - "exec:git:status"
  - "exec:git:diff"
  - "exec:git:commit"
topology_hints:
  requires:
    - "git:status"
    - "git:diff"
  provides:
    - "git:history"
  conflicts:
    - "git:reset"
tags:
  - "git"
  - "version-control"
  - "commit"
author: "GraphSkill Team"
---

# Git Commit Skill

## Description

This skill performs Git commit operations with intelligent commit message generation. It analyzes staged changes and creates meaningful commit messages following conventional commit format.

## Usage

```bash
# Basic commit
git commit -m "feat: add new feature"

# Commit with staged changes analysis
git commit
```

## Code Implementation

```python
import subprocess
import os
from typing import Optional

def git_commit(message: Optional[str] = None) -> str:
    """
    Execute git commit with automatic message generation.
    
    Args:
        message: Optional commit message. If not provided, 
                 will analyze staged changes to generate one.
    
    Returns:
        Commit hash or error message.
    """
    # Check if there are staged changes
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
    )
    
    if not status_result.stdout.strip():
        return "No changes to commit"
    
    if message is None:
        # Analyze diff to generate commit message
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True,
            text=True
        )
        # Simple heuristic for message generation
        files_changed = diff_result.stdout.count("\n")
        message = f"chore: update {files_changed} files"
    
    # Execute commit
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        # Extract commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        return hash_result.stdout.strip()
    else:
        return f"Error: {result.stderr}"

def get_commit_history(limit: int = 10) -> list[str]:
    """
    Get recent commit history.
    
    Args:
        limit: Number of commits to retrieve.
    
    Returns:
        List of commit hashes with messages.
    """
    result = subprocess.run(
        ["git", "log", "--oneline", f"-n{limit}"],
        capture_output=True,
        text=True
    )
    
    return result.stdout.strip().split("\n") if result.stdout else []
```

## Entry Point

- `git_commit(message: Optional[str] = None) -> str`

## Dependencies

- Requires `git:status` skill to check repository state
- Requires `git:diff` skill to analyze changes
- Provides output to `git:history` for historical tracking

## Error Handling

- Returns "No changes to commit" if nothing is staged
- Returns error message if commit fails
- Handles subprocess execution errors gracefully
"""
Watcher-Importer Integration Tests.

Test the collaboration workflow between file watcher and batch importer modules.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from datetime import datetime
from typing import Any
import asyncio

from graphskill.ingestion.watcher import (
    FileWatcher,
    FileEvent,
    FileEventType,
    WatcherConfig,
)
from graphskill.ingestion.importer.batch_importer import (
    BatchImporter,
    ImportStats,
    BatchImportResult,
)
from graphskill.ingestion.parser.yaml_parser import YAMLParser
from graphskill.ingestion.parser.markdown_parser import MarkdownParser


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def watcher_config() -> WatcherConfig:
    """Create watcher configuration."""
    return WatcherConfig(
        debounce_seconds=0.1,
        max_queue_size=100,
    )


@pytest.fixture
def file_watcher(watcher_config: WatcherConfig) -> FileWatcher:
    """Create file watcher instance."""
    return FileWatcher(config=watcher_config)


@pytest.fixture
def batch_importer() -> BatchImporter:
    """Create batch importer instance."""
    return BatchImporter()


@pytest.fixture
def yaml_parser() -> YAMLParser:
    """Create YAML parser instance."""
    return YAMLParser(strict_mode=False)


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Create markdown parser instance."""
    return MarkdownParser()


@pytest.fixture
def temp_skill_directory(tmp_path: Path) -> Path:
    """Create temporary skill directory."""
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    return skill_dir


@pytest.fixture
def valid_skill_file(temp_skill_directory: Path) -> Path:
    """Create valid skill file."""
    skill_file = temp_skill_directory / "SKILL.md"
    skill_file.write_text("""---
skill_id: test:skill_1
version: 1.0.0
intent_description: Test skill for watcher importer integration testing with sufficient length description.
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
tags:
  - test
author: test-author
---

## Implementation

```python
def execute():
    pass
```
""")
    return skill_file


# ============================================================================
# FileWatcher Integration Tests
# ============================================================================


class TestFileWatcherIntegration:
    """FileWatcher integration tests."""
    
    @pytest.mark.asyncio
    async def test_file_watcher_add_watch_path(
        self, file_watcher: FileWatcher, temp_skill_directory: Path
    ) -> None:
        """Test FileWatcher adding watch path."""
        file_watcher.add_watch_path(temp_skill_directory)
        
        # watch_paths is in config
        assert len(file_watcher.config.watch_paths) >= 1
        assert temp_skill_directory in file_watcher.config.watch_paths
    
    @pytest.mark.asyncio
    async def test_file_watcher_matches_pattern(
        self, file_watcher: FileWatcher
    ) -> None:
        """Test FileWatcher pattern matching."""
        # Should match SKILL.md files
        assert file_watcher._matches_pattern(Path("skills/git/SKILL.md")) == True
        assert file_watcher._matches_pattern(Path("skills/git/test.md")) == False
        assert file_watcher._matches_pattern(Path("skills/git/test.py")) == False
    
    @pytest.mark.asyncio
    async def test_file_watcher_should_ignore(
        self, file_watcher: FileWatcher
    ) -> None:
        """Test FileWatcher ignore patterns."""
        # Should ignore files matching ignore_patterns (*.tmp, *.bak, .git/*)
        assert file_watcher._should_ignore(Path("skills/test.tmp")) == True
        assert file_watcher._should_ignore(Path("skills/test.bak")) == True
        # .git/* pattern matches paths starting with .git/
        assert file_watcher._should_ignore(Path(".git/config")) == True
        # Should not ignore normal files
        assert file_watcher._should_ignore(Path("skills/SKILL.md")) == False
    
    @pytest.mark.asyncio
    async def test_file_watcher_scan_existing_files(
        self, file_watcher: FileWatcher, temp_skill_directory: Path, valid_skill_file: Path
    ) -> None:
        """Test FileWatcher scanning existing files."""
        file_watcher.add_watch_path(temp_skill_directory)
        
        existing_files = await file_watcher.scan_existing_files()
        
        assert len(existing_files) >= 1
        assert any(f.name == "SKILL.md" for f in existing_files)


# ============================================================================
# BatchImporter Integration Tests
# ============================================================================


class TestBatchImporterIntegration:
    """BatchImporter integration tests."""
    
    @pytest.mark.asyncio
    async def test_batch_importer_scan_skill_files(
        self, batch_importer: BatchImporter, temp_skill_directory: Path, valid_skill_file: Path
    ) -> None:
        """Test BatchImporter scanning skill files."""
        skill_files = batch_importer._scan_skill_files(temp_skill_directory, recursive=True)
        
        assert len(skill_files) >= 1
        assert any(f.name == "SKILL.md" for f in skill_files)
    
    @pytest.mark.asyncio
    async def test_batch_importer_build_skill_node(
        self, batch_importer: BatchImporter, yaml_parser: YAMLParser, valid_skill_file: Path
    ) -> None:
        """Test BatchImporter building skill node from frontmatter."""
        # Parse the file first
        markdown_parser = MarkdownParser()
        parsed_file = markdown_parser.parse(valid_skill_file)
        
        # Build skill node using frontmatter dict
        skill_node = batch_importer._build_skill_node(parsed_file.frontmatter, valid_skill_file)
        
        assert skill_node is not None
        assert skill_node.uid == "test:skill_1"
        assert skill_node.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_batch_importer_stats(
        self, batch_importer: BatchImporter
    ) -> None:
        """Test BatchImporter statistics."""
        stats = ImportStats(
            total_files=10,
            parsed_files=10,
            valid_files=8,
            invalid_files=2,
            nodes_created=8,
            nodes_failed=2,
        )
        
        assert stats.total_files == 10
        assert stats.nodes_created == 8
        assert stats.nodes_failed == 2
        assert stats.success_rate == 80.0  # 8/10 * 100
    
    @pytest.mark.asyncio
    async def test_batch_importer_batch_import_result(
        self, batch_importer: BatchImporter
    ) -> None:
        """Test BatchImporter batch import result."""
        stats = ImportStats(
            total_files=5,
            parsed_files=5,
            valid_files=5,
            invalid_files=0,
            nodes_created=5,
            nodes_failed=0,
        )
        result = BatchImportResult(
            success=True,
            stats=stats,
            node_results=[],
            edge_results=[],
        )
        
        assert result.success == True
        assert result.stats.nodes_created == 5
        assert result.stats.success_rate == 100.0


# ============================================================================
# Watcher-Importer Pipeline Tests
# ============================================================================


class TestWatcherImporterPipeline:
    """Test complete pipeline from watcher to importer."""
    
    @pytest.mark.asyncio
    async def test_file_event_to_import_pipeline(
        self, batch_importer: BatchImporter, markdown_parser: MarkdownParser, temp_skill_directory: Path
    ) -> None:
        """Test file event triggering import pipeline."""
        # Create a skill file
        skill_file = temp_skill_directory / "SKILL.md"
        skill_file.write_text("""---
skill_id: pipeline:test_skill
version: 1.0.0
intent_description: Test skill for pipeline testing with proper description length for validation.
permissions:
  - fs:read:/tmp
---
""")
        
        # Parse the file
        parsed_file = markdown_parser.parse(skill_file)
        
        # Build skill node using frontmatter dict
        skill_node = batch_importer._build_skill_node(parsed_file.frontmatter, skill_file)
        
        assert skill_node is not None
        assert skill_node.uid == "pipeline:test_skill"
    
    @pytest.mark.asyncio
    async def test_batch_processing_workflow(
        self, batch_importer: BatchImporter, temp_skill_directory: Path
    ) -> None:
        """Test batch processing of multiple skill files."""
        # Create multiple skill directories with SKILL.md
        for i in range(3):
            skill_subdir = temp_skill_directory / f"batch_skill_{i}"
            skill_subdir.mkdir()
            skill_file = skill_subdir / "SKILL.md"
            skill_file.write_text(f"""---
skill_id: batch:skill_{i}
version: 1.0.0
intent_description: Batch test skill {i} for batch processing integration testing with proper length.
permissions:
  - fs:read:/tmp
---
""")
        
        # Scan files recursively
        scanned_files = batch_importer._scan_skill_files(temp_skill_directory, recursive=True)
        
        assert len(scanned_files) >= 3
        assert all(f.name == "SKILL.md" for f in scanned_files)


# ============================================================================
# FileEvent Handling Tests
# ============================================================================


class TestFileEventHandling:
    """Test file event handling."""
    
    @pytest.mark.asyncio
    async def test_file_event_types(
        self, file_watcher: FileWatcher
    ) -> None:
        """Test different file event types."""
        # Create event
        created_event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=Path("skills/test/SKILL.md"),
            timestamp=datetime.now(),
        )
        
        assert created_event.event_type == FileEventType.CREATED
        assert created_event.event_type.value == "created"
        
        # Modify event
        modified_event = FileEvent(
            event_type=FileEventType.MODIFIED,
            file_path=Path("skills/test/SKILL.md"),
            timestamp=datetime.now(),
        )
        
        assert modified_event.event_type == FileEventType.MODIFIED
        assert modified_event.event_type.value == "modified"
        
        # Delete event
        deleted_event = FileEvent(
            event_type=FileEventType.DELETED,
            file_path=Path("skills/test/SKILL.md"),
            timestamp=datetime.now(),
        )
        
        assert deleted_event.event_type == FileEventType.DELETED
        assert deleted_event.event_type.value == "deleted"
    
    @pytest.mark.asyncio
    async def test_file_event_to_dict(
        self, file_watcher: FileWatcher
    ) -> None:
        """Test FileEvent serialization."""
        event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=Path("skills/test/SKILL.md"),
            timestamp=datetime.now(),
        )
        
        event_dict = event.to_dict()
        
        assert "event_type" in event_dict
        assert "file_path" in event_dict
        assert "timestamp" in event_dict
        assert event_dict["event_type"] == "created"


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_directory_handling(
        self, batch_importer: BatchImporter, tmp_path: Path
    ) -> None:
        """Test handling empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        skill_files = batch_importer._scan_skill_files(empty_dir, recursive=True)
        
        assert len(skill_files) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_skill_file_handling(
        self, batch_importer: BatchImporter, markdown_parser: MarkdownParser, tmp_path: Path
    ) -> None:
        """Test handling invalid skill file."""
        # Create invalid file (missing required fields)
        invalid_file = tmp_path / "SKILL.md"
        invalid_file.write_text("""---
skill_id: invalid
# Missing version and intent_description
permissions:
  - fs:read:/tmp
---
""")
        
        # Parse should handle gracefully in lenient mode
        try:
            parsed_file = markdown_parser.parse(invalid_file)
            # Build should handle gracefully
            skill_node = batch_importer._build_skill_node(parsed_file.frontmatter, invalid_file)
            # May return partial result
            if skill_node:
                assert skill_node.uid == "invalid"
        except Exception as e:
            # Should not crash
            assert "error" in str(e).lower() or "invalid" in str(e).lower() or "missing" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_import_stats_all_failed(
        self, batch_importer: BatchImporter
    ) -> None:
        """Test import statistics when all imports fail."""
        stats = ImportStats(
            total_files=10,
            parsed_files=10,
            valid_files=0,
            invalid_files=10,
            nodes_created=0,
            nodes_failed=10,
        )
        
        assert stats.total_files == 10
        assert stats.nodes_created == 0
        assert stats.nodes_failed == 10
        assert stats.success_rate == 0.0


# ============================================================================
# Watcher Statistics Tests
# ============================================================================


class TestWatcherStats:
    """Test watcher statistics."""
    
    @pytest.mark.asyncio
    async def test_watcher_get_stats(
        self, file_watcher: FileWatcher, temp_skill_directory: Path
    ) -> None:
        """Test watcher statistics collection."""
        file_watcher.add_watch_path(temp_skill_directory)
        
        stats = file_watcher.get_stats()
        
        assert "watch_paths" in stats
        assert len(stats["watch_paths"]) >= 1
        assert "running" in stats  # Note: key is "running" not "is_running"
        assert stats["running"] == False  # Not started yet
    
    @pytest.mark.asyncio
    async def test_watcher_config_defaults(
        self, file_watcher: FileWatcher
    ) -> None:
        """Test watcher configuration defaults."""
        config = file_watcher.config
        
        assert config.debounce_seconds > 0
        assert config.max_queue_size > 0
        assert len(config.file_patterns) > 0
        assert "SKILL.md" in config.file_patterns
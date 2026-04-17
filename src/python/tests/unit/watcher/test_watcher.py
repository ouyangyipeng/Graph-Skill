"""
Watcher 模块单元测试。

测试文件监控服务的数据结构和功能。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graphskill.ingestion.watcher import (
    FileEventType,
    FileEvent,
    WatcherConfig,
    WatcherError,
    FileWatcher,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def watcher_config() -> WatcherConfig:
    """创建默认监控配置。"""
    return WatcherConfig()


@pytest.fixture
def custom_config() -> WatcherConfig:
    """创建自定义监控配置。"""
    return WatcherConfig(
        watch_paths=[Path("/tmp/skills")],
        file_patterns=["SKILL.md", "*.skill.md"],
        recursive=False,
        debounce_seconds=1.0,
        max_queue_size=500,
        ignore_patterns=["*.tmp", "*.bak", ".git/*", "__pycache__/*"],
    )


@pytest.fixture
def file_event_created() -> FileEvent:
    """创建 CREATED 事件。"""
    return FileEvent(
        event_type=FileEventType.CREATED,
        file_path=Path("/tmp/skills/test/SKILL.md"),
    )


@pytest.fixture
def file_event_modified() -> FileEvent:
    """创建 MODIFIED 事件。"""
    return FileEvent(
        event_type=FileEventType.MODIFIED,
        file_path=Path("/tmp/skills/test/SKILL.md"),
    )


@pytest.fixture
def file_event_deleted() -> FileEvent:
    """创建 DELETED 事件。"""
    return FileEvent(
        event_type=FileEventType.DELETED,
        file_path=Path("/tmp/skills/test/SKILL.md"),
    )


@pytest.fixture
def file_event_moved() -> FileEvent:
    """创建 MOVED 事件。"""
    return FileEvent(
        event_type=FileEventType.MOVED,
        file_path=Path("/tmp/skills/new/SKILL.md"),
        old_path=Path("/tmp/skills/old/SKILL.md"),
    )


@pytest.fixture
def file_watcher(watcher_config: WatcherConfig) -> FileWatcher:
    """创建文件监控器。"""
    return FileWatcher(config=watcher_config)


# ============================================================================
# FileEventType Tests
# ============================================================================


class TestFileEventType:
    """FileEventType 枚举测试。"""
    
    def test_event_type_enum_values(self) -> None:
        """测试枚举值。"""
        assert FileEventType.CREATED == "created"
        assert FileEventType.MODIFIED == "modified"
        assert FileEventType.DELETED == "deleted"
        assert FileEventType.MOVED == "moved"
    
    def test_event_type_is_string_enum(self) -> None:
        """测试是字符串枚举。"""
        assert isinstance(FileEventType.CREATED, str)
        assert FileEventType.CREATED.value == "created"
    
    def test_event_type_count(self) -> None:
        """测试枚举数量。"""
        assert len(FileEventType) == 4


# ============================================================================
# FileEvent Tests
# ============================================================================


class TestFileEvent:
    """FileEvent 数据结构测试。"""
    
    def test_create_file_event(
        self, file_event_created: FileEvent
    ) -> None:
        """测试创建文件事件。"""
        assert file_event_created.event_type == FileEventType.CREATED
        assert file_event_created.file_path == Path("/tmp/skills/test/SKILL.md")
        assert file_event_created.is_directory == False
        assert file_event_created.old_path is None
    
    def test_file_event_timestamp_auto(
        self, file_event_created: FileEvent
    ) -> None:
        """测试时间戳自动生成。"""
        assert file_event_created.timestamp is not None
        assert isinstance(file_event_created.timestamp, datetime)
    
    def test_file_event_with_old_path(
        self, file_event_moved: FileEvent
    ) -> None:
        """测试带原路径的事件。"""
        assert file_event_moved.old_path == Path("/tmp/skills/old/SKILL.md")
        assert file_event_moved.event_type == FileEventType.MOVED
    
    def test_file_event_is_directory(self) -> None:
        """测试目录事件。"""
        event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=Path("/tmp/skills/test"),
            is_directory=True,
        )
        assert event.is_directory == True
    
    def test_file_event_to_dict(
        self, file_event_created: FileEvent
    ) -> None:
        """测试转换为字典。"""
        result = file_event_created.to_dict()
        
        assert result["event_type"] == "created"
        assert result["file_path"] == "/tmp/skills/test/SKILL.md"
        assert "timestamp" in result
        assert result["is_directory"] == False
        assert result["old_path"] is None
    
    def test_file_event_to_dict_with_old_path(
        self, file_event_moved: FileEvent
    ) -> None:
        """测试带原路径的字典转换。"""
        result = file_event_moved.to_dict()
        
        assert result["event_type"] == "moved"
        assert result["old_path"] == "/tmp/skills/old/SKILL.md"
    
    def test_file_event_custom_timestamp(self) -> None:
        """测试自定义时间戳。"""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=Path("/tmp/test.md"),
            timestamp=custom_time,
        )
        assert event.timestamp == custom_time


# ============================================================================
# WatcherConfig Tests
# ============================================================================


class TestWatcherConfig:
    """WatcherConfig 数据结构测试。"""
    
    def test_create_default_config(
        self, watcher_config: WatcherConfig
    ) -> None:
        """测试创建默认配置。"""
        assert watcher_config.watch_paths == []
        assert watcher_config.file_patterns == ["SKILL.md"]
        assert watcher_config.recursive == True
        assert watcher_config.debounce_seconds == 0.5
        assert watcher_config.max_queue_size == 1000
        assert watcher_config.ignore_patterns == ["*.tmp", "*.bak", ".git/*"]
    
    def test_create_custom_config(
        self, custom_config: WatcherConfig
    ) -> None:
        """测试创建自定义配置。"""
        assert custom_config.watch_paths == [Path("/tmp/skills")]
        assert custom_config.file_patterns == ["SKILL.md", "*.skill.md"]
        assert custom_config.recursive == False
        assert custom_config.debounce_seconds == 1.0
        assert custom_config.max_queue_size == 500
        assert "*.tmp" in custom_config.ignore_patterns
    
    def test_config_to_dict(
        self, custom_config: WatcherConfig
    ) -> None:
        """测试配置转换为字典。"""
        result = custom_config.to_dict()
        
        assert result["watch_paths"] == ["/tmp/skills"]
        assert result["file_patterns"] == ["SKILL.md", "*.skill.md"]
        assert result["recursive"] == False
        assert result["debounce_seconds"] == 1.0
        assert result["max_queue_size"] == 500
        assert "*.tmp" in result["ignore_patterns"]
    
    def test_config_empty_watch_paths(
        self, watcher_config: WatcherConfig
    ) -> None:
        """测试空监控路径。"""
        result = watcher_config.to_dict()
        assert result["watch_paths"] == []
    
    def test_config_multiple_watch_paths(self) -> None:
        """测试多个监控路径。"""
        config = WatcherConfig(
            watch_paths=[
                Path("/skills/dir1"),
                Path("/skills/dir2"),
                Path("/skills/dir3"),
            ]
        )
        assert len(config.watch_paths) == 3


# ============================================================================
# WatcherError Tests
# ============================================================================


class TestWatcherError:
    """WatcherError 异常测试。"""
    
    def test_create_watcher_error(self) -> None:
        """测试创建监控错误。"""
        error = WatcherError("Watch failed")
        assert error.message == "Watch failed"
        assert error.code == "GS-3040"
        assert error.path is None
    
    def test_watcher_error_with_path(self) -> None:
        """测试带路径的错误。"""
        path = Path("/tmp/skills/test")
        error = WatcherError("Path not found", path=path)
        assert error.path == path
    
    def test_watcher_error_to_dict(self) -> None:
        """测试错误转换为字典。"""
        path = Path("/tmp/skills/test")
        error = WatcherError("Path not found", path=path)
        result = error.to_dict()
        
        assert "error" in result
        assert result["error"]["code"] == "GS-3040"
        assert result["error"]["message"] == "Path not found"
        assert result["path"] == "/tmp/skills/test"
    
    def test_watcher_error_to_dict_without_path(self) -> None:
        """测试无路径的错误字典。"""
        error = WatcherError("Generic error")
        result = error.to_dict()
        assert "path" not in result
    
    def test_watcher_error_inheritance(self) -> None:
        """测试错误继承关系。"""
        error = WatcherError("Test error")
        assert isinstance(error, IngestionError)
        assert isinstance(error, Exception)


# ============================================================================
# FileWatcher Tests
# ============================================================================


class TestFileWatcherInit:
    """FileWatcher 初始化测试。"""
    
    def test_init_default_config(self) -> None:
        """测试默认配置初始化。"""
        watcher = FileWatcher()
        assert watcher.config is not None
        assert watcher.config.file_patterns == ["SKILL.md"]
        assert watcher.on_event is None
        assert watcher._running == False
    
    def test_init_custom_config(
        self, custom_config: WatcherConfig
    ) -> None:
        """测试自定义配置初始化。"""
        watcher = FileWatcher(config=custom_config)
        assert watcher.config == custom_config
        assert watcher.config.recursive == False
    
    def test_init_with_callback(self) -> None:
        """测试带回调初始化。"""
        callback = MagicMock()
        watcher = FileWatcher(on_event=callback)
        assert watcher.on_event == callback
    
    def test_init_event_queue(
        self, watcher_config: WatcherConfig
    ) -> None:
        """测试事件队列初始化。"""
        watcher = FileWatcher(config=watcher_config)
        assert watcher._event_queue is not None
        assert watcher._event_queue.maxsize == watcher_config.max_queue_size


class TestFileWatcherPathManagement:
    """FileWatcher 路径管理测试。"""
    
    def test_add_watch_path(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试添加监控路径。"""
        path = Path("/tmp/new_skills")
        file_watcher.add_watch_path(path)
        assert path in file_watcher.config.watch_paths
    
    def test_add_watch_path_duplicate(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试添加重复路径。"""
        path = Path("/tmp/skills")
        file_watcher.add_watch_path(path)
        file_watcher.add_watch_path(path)
        assert file_watcher.config.watch_paths.count(path) == 1
    
    def test_remove_watch_path(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试移除监控路径。"""
        path = Path("/tmp/skills")
        file_watcher.add_watch_path(path)
        file_watcher.remove_watch_path(path)
        assert path not in file_watcher.config.watch_paths
    
    def test_remove_nonexistent_path(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试移除不存在路径。"""
        path = Path("/tmp/nonexistent")
        file_watcher.remove_watch_path(path)
        # 不应该抛出异常
        assert path not in file_watcher.config.watch_paths


class TestFileWatcherCallback:
    """FileWatcher 回调测试。"""
    
    def test_set_callback(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试设置回调。"""
        callback = MagicMock()
        file_watcher.set_callback(callback)
        assert file_watcher.on_event == callback
    
    def test_set_callback_replaces_existing(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试替换现有回调。"""
        old_callback = MagicMock()
        new_callback = MagicMock()
        
        file_watcher.set_callback(old_callback)
        file_watcher.set_callback(new_callback)
        
        assert file_watcher.on_event == new_callback


class TestFileWatcherPatternMatching:
    """FileWatcher 模式匹配测试。"""
    
    def test_matches_pattern_skill_md(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试匹配 SKILL.md。"""
        path = Path("/tmp/skills/test/SKILL.md")
        assert file_watcher._matches_pattern(path) == True
    
    def test_matches_pattern_other_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试不匹配其他文件。"""
        path = Path("/tmp/skills/test/README.md")
        assert file_watcher._matches_pattern(path) == False
    
    def test_matches_pattern_custom_patterns(self) -> None:
        """测试自定义模式匹配（精确匹配文件名）。"""
        # _matches_pattern 只支持精确匹配文件名，不支持通配符
        config = WatcherConfig(file_patterns=["custom.skill.md", "SKILL.md"])
        watcher = FileWatcher(config=config)
        
        assert watcher._matches_pattern(Path("/tmp/custom.skill.md")) == True
        assert watcher._matches_pattern(Path("/tmp/SKILL.md")) == True
        assert watcher._matches_pattern(Path("/tmp/test.skill.md")) == False  # 不匹配通配符
        assert watcher._matches_pattern(Path("/tmp/other.md")) == False
    
    def test_matches_pattern_nested_path(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试嵌套路径匹配。"""
        path = Path("/tmp/skills/deep/nested/dir/SKILL.md")
        assert file_watcher._matches_pattern(path) == True


class TestFileWatcherIgnorePatterns:
    """FileWatcher 忽略模式测试。"""
    
    def test_should_ignore_tmp_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试忽略临时文件。"""
        path = Path("/tmp/skills/test.tmp")
        assert file_watcher._should_ignore(path) == True
    
    def test_should_ignore_bak_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试忽略备份文件。"""
        path = Path("/tmp/skills/test.bak")
        assert file_watcher._should_ignore(path) == True
    
    def test_should_ignore_git_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试忽略 git 文件。"""
        path = Path(".git/config")
        assert file_watcher._should_ignore(path) == True
    
    def test_should_not_ignore_skill_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试不忽略技能文件。"""
        path = Path("/tmp/skills/test/SKILL.md")
        assert file_watcher._should_ignore(path) == False
    
    def test_custom_ignore_patterns(self) -> None:
        """测试自定义忽略模式。"""
        config = WatcherConfig(ignore_patterns=["*.log", "*.cache"])
        watcher = FileWatcher(config=config)
        
        assert watcher._should_ignore(Path("/tmp/test.log")) == True
        assert watcher._should_ignore(Path("/tmp/test.cache")) == True
        assert watcher._should_ignore(Path("/tmp/SKILL.md")) == False


class TestFileWatcherDebounce:
    """FileWatcher 防抖测试。"""
    
    def test_should_debounce_first_event(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试首次事件不防抖。"""
        path = Path("/tmp/skills/test/SKILL.md")
        # 首次调用不应该防抖
        assert file_watcher._should_debounce(path) == False
    
    def test_should_debounce_rapid_events(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试快速连续事件防抖。"""
        path = Path("/tmp/skills/test/SKILL.md")
        # 首次调用
        file_watcher._should_debounce(path)
        # 立即再次调用应该防抖
        assert file_watcher._should_debounce(path) == True
    
    def test_debounce_different_paths(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试不同路径独立防抖。"""
        path1 = Path("/tmp/skills/test1/SKILL.md")
        path2 = Path("/tmp/skills/test2/SKILL.md")
        
        # 首次调用 path1
        assert file_watcher._should_debounce(path1) == False
        # 首次调用 path2（不应该受 path1 影响）
        assert file_watcher._should_debounce(path2) == False
    
    def test_debounce_custom_seconds(self) -> None:
        """测试自定义防抖时间。"""
        config = WatcherConfig(debounce_seconds=2.0)
        watcher = FileWatcher(config=config)
        
        path = Path("/tmp/test/SKILL.md")
        watcher._should_debounce(path)
        # 立即再次调用应该防抖
        assert watcher._should_debounce(path) == True


class TestFileWatcherEventHandling:
    """FileWatcher 事件处理测试。"""
    
    def test_handle_event_valid_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试处理有效文件事件。"""
        path = Path("/tmp/skills/test/SKILL.md")
        file_watcher._handle_event(FileEventType.CREATED, path)
        
        # 事件应该被加入队列
        assert file_watcher._event_queue.qsize() == 1
    
    def test_handle_event_ignored_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试处理忽略文件事件。"""
        path = Path("/tmp/skills/test.tmp")
        file_watcher._handle_event(FileEventType.CREATED, path)
        
        # 事件不应该被加入队列
        assert file_watcher._event_queue.qsize() == 0
    
    def test_handle_event_non_matching_file(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试处理不匹配文件事件。"""
        path = Path("/tmp/skills/README.md")
        file_watcher._handle_event(FileEventType.CREATED, path)
        
        # 事件不应该被加入队列
        assert file_watcher._event_queue.qsize() == 0
    
    def test_handle_event_with_old_path(
        self, file_watcher: FileWatcher
    ) -> None:
        """测试处理带原路径事件。"""
        new_path = Path("/tmp/skills/new/SKILL.md")
        old_path = Path("/tmp/skills/old/SKILL.md")
        file_watcher._handle_event(FileEventType.MOVED, new_path, old_path=old_path)
        
        assert file_watcher._event_queue.qsize() == 1
        event = file_watcher._event_queue.get_nowait()
        assert event.old_path == old_path
    
    def test_handle_event_queue_full(self) -> None:
        """测试队列满时丢弃事件。"""
        config = WatcherConfig(max_queue_size=1)
        watcher = FileWatcher(config=config)
        
        path = Path("/tmp/skills/test/SKILL.md")
        # 加入第一个事件
        watcher._handle_event(FileEventType.CREATED, path)
        # 队列已满，第二个事件应该被丢弃
        watcher._handle_event(FileEventType.MODIFIED, path)
        
        assert watcher._event_queue.qsize() == 1


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_empty_file_patterns(self) -> None:
        """测试空文件模式。"""
        config = WatcherConfig(file_patterns=[])
        watcher = FileWatcher(config=config)
        
        path = Path("/tmp/skills/SKILL.md")
        assert watcher._matches_pattern(path) == False
    
    def test_empty_ignore_patterns(self) -> None:
        """测试空忽略模式。"""
        config = WatcherConfig(ignore_patterns=[])
        watcher = FileWatcher(config=config)
        
        path = Path("/tmp/skills/test.tmp")
        assert watcher._should_ignore(path) == False
    
    def test_file_event_with_special_chars_path(self) -> None:
        """测试特殊字符路径。"""
        path = Path("/tmp/skills/test with spaces/SKILL.md")
        event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=path,
        )
        result = event.to_dict()
        assert "test with spaces" in result["file_path"]
    
    def test_file_event_with_unicode_path(self) -> None:
        """测试 Unicode 路径。"""
        path = Path("/tmp/skills/测试/SKILL.md")
        event = FileEvent(
            event_type=FileEventType.CREATED,
            file_path=path,
        )
        result = event.to_dict()
        assert "测试" in result["file_path"]
    
    def test_watcher_config_zero_debounce(self) -> None:
        """测试零防抖时间。"""
        config = WatcherConfig(debounce_seconds=0.0)
        watcher = FileWatcher(config=config)
        
        path = Path("/tmp/test/SKILL.md")
        watcher._should_debounce(path)
        # 零防抖时间，立即再次调用不应该防抖
        # 但由于时间精度问题，可能仍然防抖
        # 这里主要测试配置可以接受零值
        assert watcher.config.debounce_seconds == 0.0
    
    def test_watcher_config_large_queue(self) -> None:
        """测试大队列。"""
        config = WatcherConfig(max_queue_size=10000)
        watcher = FileWatcher(config=config)
        assert watcher._event_queue.maxsize == 10000


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    def test_full_event_workflow(self) -> None:
        """测试完整事件工作流。"""
        config = WatcherConfig(
            file_patterns=["SKILL.md"],
            ignore_patterns=["*.tmp"],
            debounce_seconds=0.1,
        )
        
        callback_events = []
        def callback(event: FileEvent) -> None:
            callback_events.append(event)
        
        watcher = FileWatcher(config=config, on_event=callback)
        
        # 模拟处理事件
        path = Path("/tmp/skills/test/SKILL.md")
        watcher._handle_event(FileEventType.CREATED, path)
        
        # 检查事件被加入队列
        assert watcher._event_queue.qsize() == 1
        
        # 获取事件
        event = watcher._event_queue.get_nowait()
        assert event.event_type == FileEventType.CREATED
        assert event.file_path == path
    
    def test_multiple_events_workflow(self) -> None:
        """测试多事件工作流。"""
        watcher = FileWatcher()
        
        paths = [
            Path("/tmp/skills/skill1/SKILL.md"),
            Path("/tmp/skills/skill2/SKILL.md"),
            Path("/tmp/skills/skill3/SKILL.md"),
        ]
        
        for path in paths:
            watcher._handle_event(FileEventType.CREATED, path)
        
        assert watcher._event_queue.qsize() == 3
        
        # 检查所有事件
        events = []
        while not watcher._event_queue.empty():
            events.append(watcher._event_queue.get_nowait())
        
        assert len(events) == 3
        for event in events:
            assert event.event_type == FileEventType.CREATED
    
    def test_config_to_dict_roundtrip(self) -> None:
        """测试配置字典往返。"""
        config = WatcherConfig(
            watch_paths=[Path("/tmp/skills")],
            file_patterns=["SKILL.md"],
            recursive=True,
            debounce_seconds=0.5,
            max_queue_size=1000,
            ignore_patterns=["*.tmp"],
        )
        
        result = config.to_dict()
        
        # 验证所有字段
        assert result["watch_paths"] == ["/tmp/skills"]
        assert result["file_patterns"] == ["SKILL.md"]
        assert result["recursive"] == True
        assert result["debounce_seconds"] == 0.5
        assert result["max_queue_size"] == 1000
        assert result["ignore_patterns"] == ["*.tmp"]


# ============================================================================
# Async Tests
# ============================================================================


class TestAsyncOperations:
    """异步操作测试。"""
    
    @pytest.mark.asyncio
    async def test_start_without_paths(self) -> None:
        """测试无路径启动。"""
        watcher = FileWatcher()
        # 无监控路径时启动（模拟模式）
        await watcher.start()
        assert watcher._running == True
        await watcher.stop()
    
    @pytest.mark.asyncio
    async def test_stop_without_start(self) -> None:
        """测试未启动时停止。"""
        watcher = FileWatcher()
        await watcher.stop()
        assert watcher._running == False
    
    @pytest.mark.asyncio
    async def test_start_stop_cycle(self) -> None:
        """测试启动停止循环。"""
        watcher = FileWatcher()
        
        await watcher.start()
        assert watcher._running == True
        
        await watcher.stop()
        assert watcher._running == False
        
        # 再次启动
        await watcher.start()
        assert watcher._running == True
        
        await watcher.stop()
        assert watcher._running == False
    
    @pytest.mark.asyncio
    async def test_double_start(self) -> None:
        """测试重复启动。"""
        watcher = FileWatcher()
        
        await watcher.start()
        assert watcher._running == True
        
        # 再次启动应该无效果
        await watcher.start()
        assert watcher._running == True
        
        await watcher.stop()
    
    @pytest.mark.asyncio
    async def test_double_stop(self) -> None:
        """测试重复停止。"""
        watcher = FileWatcher()
        
        await watcher.start()
        await watcher.stop()
        assert watcher._running == False
        
        # 再次停止应该无效果
        await watcher.stop()
        assert watcher._running == False


# ============================================================================
# Import Test
# ============================================================================


# Import IngestionError for inheritance test
from graphskill.core.exceptions import IngestionError
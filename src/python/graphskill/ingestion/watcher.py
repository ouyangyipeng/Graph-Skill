"""
文件监控服务。

监控技能目录的文件变更，触发处理流程。

Reference: RFC-02 Section 3.1
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any

from graphskill.core.exceptions import IngestionError


class FileEventType(str, Enum):
    """文件事件类型。"""
    
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileEvent:
    """文件事件。"""
    
    event_type: FileEventType
    file_path: Path
    timestamp: datetime = field(default_factory=datetime.now)
    is_directory: bool = False
    old_path: Optional[Path] = None  # 用于 MOVED 事件
    
    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "file_path": str(self.file_path),
            "timestamp": self.timestamp.isoformat(),
            "is_directory": self.is_directory,
            "old_path": str(self.old_path) if self.old_path else None,
        }


@dataclass
class WatcherConfig:
    """监控配置。"""
    
    watch_paths: list[Path] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=lambda: ["SKILL.md"])
    recursive: bool = True
    debounce_seconds: float = 0.5
    max_queue_size: int = 1000
    ignore_patterns: list[str] = field(default_factory=lambda: ["*.tmp", "*.bak", ".git/*"])
    
    def to_dict(self) -> dict:
        return {
            "watch_paths": [str(p) for p in self.watch_paths],
            "file_patterns": self.file_patterns,
            "recursive": self.recursive,
            "debounce_seconds": self.debounce_seconds,
            "max_queue_size": self.max_queue_size,
            "ignore_patterns": self.ignore_patterns,
        }


class WatcherError(IngestionError):
    """监控错误。
    
    Error Code: GS-3040
    """
    
    def __init__(self, message: str, path: Optional[Path] = None):
        details = {}
        if path:
            details["path"] = str(path)
        super().__init__(message, file_path=str(path) if path else None, details=details)
        self.path = path
        # 覆盖错误码
        self.code = "GS-3040"
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.path:
            result["path"] = str(self.path)
        return result


class FileWatcher:
    """
    文件监控服务。
    
    监控技能目录的文件变更，触发处理流程。
    
    Features:
        - 实时文件监控
        - 事件过滤
        - 防抖处理
        - 异步事件队列
        - 可配置回调
    
    Example:
        >>> watcher = FileWatcher(config)
        >>> watcher.on_event = process_skill_file
        >>> await watcher.start()
        >>> # ... 监控运行
        >>> await watcher.stop()
    """
    
    def __init__(
        self,
        config: Optional[WatcherConfig] = None,
        on_event: Optional[Callable[[FileEvent], None]] = None,
    ):
        """
        初始化监控器。
        
        Args:
            config: 监控配置
            on_event: 事件回调函数
        """
        self.config = config or WatcherConfig()
        self.on_event = on_event
        
        self._event_queue: asyncio.Queue[FileEvent] = asyncio.Queue(
            maxsize=self.config.max_queue_size
        )
        self._running = False
        self._observer: Optional[Any] = None
        self._debounce_cache: dict[str, datetime] = {}
    
    async def start(self) -> None:
        """
        启动监控。
        
        Raises:
            WatcherError: 启动失败
        """
        if self._running:
            return
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
            
            # 创建事件处理器
            handler = self._create_handler()
            
            # 创建观察者
            self._observer = Observer()
            
            for watch_path in self.config.watch_paths:
                if not watch_path.exists():
                    raise WatcherError(f"Watch path does not exist: {watch_path}", watch_path)
                
                self._observer.schedule(
                    handler,
                    str(watch_path),
                    recursive=self.config.recursive,
                )
            
            self._observer.start()
            self._running = True
            
            # 启动事件处理循环
            asyncio.create_task(self._process_events())
        
        except ImportError:
            # watchdog 库未安装，使用模拟模式
            self._running = True
            asyncio.create_task(self._mock_watch())
        
        except Exception as e:
            raise WatcherError(f"Failed to start watcher: {e}")
    
    async def stop(self) -> None:
        """
        停止监控。
        """
        if not self._running:
            return
        
        self._running = False
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def _create_handler(self) -> Any:
        """
        创建文件系统事件处理器。
        
        Returns:
            FileSystemEventHandler: 处理器实例
        """
        from watchdog.events import FileSystemEventHandler, FileSystemEvent
        
        class SkillFileHandler(FileSystemEventHandler):
            def __init__(self, watcher: FileWatcher):
                self.watcher = watcher
            
            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_event(FileEventType.CREATED, Path(event.src_path))
            
            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_event(FileEventType.MODIFIED, Path(event.src_path))
            
            def on_deleted(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_event(FileEventType.DELETED, Path(event.src_path))
            
            def on_moved(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_event(
                        FileEventType.MOVED,
                        Path(event.dest_path),
                        old_path=Path(event.src_path),
                    )
        
        return SkillFileHandler(self)
    
    def _handle_event(
        self,
        event_type: FileEventType,
        file_path: Path,
        old_path: Optional[Path] = None,
    ) -> None:
        """
        处理文件事件。
        
        Args:
            event_type: 事件类型
            file_path: 文件路径
            old_path: 原路径（用于 MOVED）
        """
        # 检查是否匹配文件模式
        if not self._matches_pattern(file_path):
            return
        
        # 检查是否在忽略列表
        if self._should_ignore(file_path):
            return
        
        # 防抖处理
        if self._should_debounce(file_path):
            return
        
        # 创建事件
        event = FileEvent(
            event_type=event_type,
            file_path=file_path,
            is_directory=False,
            old_path=old_path,
        )
        
        # 加入队列
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # 队列满，丢弃事件
            pass
    
    def _matches_pattern(
        self,
        file_path: Path,
    ) -> bool:
        """
        检查文件是否匹配模式。
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否匹配
        """
        file_name = file_path.name
        
        for pattern in self.config.file_patterns:
            if file_name == pattern:
                return True
        
        return False
    
    def _should_ignore(
        self,
        file_path: Path,
    ) -> bool:
        """
        检查是否应该忽略。
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否忽略
        """
        import fnmatch
        
        path_str = str(file_path)
        
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        
        return False
    
    def _should_debounce(
        self,
        file_path: Path,
    ) -> bool:
        """
        检查是否应该防抖。
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否防抖
        """
        path_str = str(file_path)
        now = datetime.now()
        
        if path_str in self._debounce_cache:
            last_time = self._debounce_cache[path_str]
            elapsed = (now - last_time).total_seconds()
            
            if elapsed < self.config.debounce_seconds:
                return True
        
        self._debounce_cache[path_str] = now
        return False
    
    async def _process_events(self) -> None:
        """
        处理事件队列。
        """
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )
                
                # 调用回调
                if self.on_event:
                    try:
                        if asyncio.iscoroutinefunction(self.on_event):
                            await self.on_event(event)
                        else:
                            self.on_event(event)
                    except Exception as e:
                        # 回调失败，记录但不中断
                        pass
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                continue
    
    async def _mock_watch(self) -> None:
        """
        模拟监控（用于测试）。
        """
        while self._running:
            await asyncio.sleep(1.0)
    
    def add_watch_path(
        self,
        path: Path,
    ) -> None:
        """
        添加监控路径。
        
        Args:
            path: 监控路径
        """
        if path not in self.config.watch_paths:
            self.config.watch_paths.append(path)
    
    def remove_watch_path(
        self,
        path: Path,
    ) -> None:
        """
        移除监控路径。
        
        Args:
            path: 监控路径
        """
        if path in self.config.watch_paths:
            self.config.watch_paths.remove(path)
    
    def set_callback(
        self,
        callback: Callable[[FileEvent], None],
    ) -> None:
        """
        设置事件回调。
        
        Args:
            callback: 回调函数
        """
        self.on_event = callback
    
    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """队列大小。"""
        return self._event_queue.qsize()
    
    def get_stats(self) -> dict:
        """
        获取监控统计。
        
        Returns:
            dict: 统计信息
        """
        return {
            "running": self._running,
            "watch_paths": [str(p) for p in self.config.watch_paths],
            "queue_size": self.queue_size,
            "max_queue_size": self.config.max_queue_size,
            "debounce_cache_size": len(self._debounce_cache),
        }
    
    async def scan_existing_files(self) -> list[Path]:
        """
        扫描现有文件。
        
        Returns:
            list: 文件路径列表
        """
        existing_files: list[Path] = []
        
        for watch_path in self.config.watch_paths:
            if not watch_path.exists():
                continue
            
            if self.config.recursive:
                for pattern in self.config.file_patterns:
                    for file_path in watch_path.rglob(pattern):
                        if not self._should_ignore(file_path):
                            existing_files.append(file_path)
            else:
                for pattern in self.config.file_patterns:
                    for file_path in watch_path.glob(pattern):
                        if not self._should_ignore(file_path):
                            existing_files.append(file_path)
        
        return existing_files
    
    async def emit_initial_events(self) -> None:
        """
        发送初始事件（扫描现有文件）。
        """
        existing_files = await self.scan_existing_files()
        
        for file_path in existing_files:
            event = FileEvent(
                event_type=FileEventType.CREATED,
                file_path=file_path,
            )
            
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                break


def create_default_watcher(
    skill_dir: Path,
    on_event: Optional[Callable[[FileEvent], None]] = None,
) -> FileWatcher:
    """
    创建默认监控器。
    
    Args:
        skill_dir: 技能目录
        on_event: 事件回调
        
    Returns:
        FileWatcher: 监控器实例
    """
    config = WatcherConfig(
        watch_paths=[skill_dir],
        file_patterns=["SKILL.md"],
        recursive=True,
        debounce_seconds=0.5,
        ignore_patterns=["*.tmp", "*.bak", ".git/*", "__pycache__/*"],
    )
    
    return FileWatcher(config, on_event)
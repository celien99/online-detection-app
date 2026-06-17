"""Model hot-reload service polling deployed model directory."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional


class HotReloadService:
    """定时检查部署目录中的模型文件 mtime，变化时通知 InspectionService 重新加载。"""

    def __init__(self, poll_seconds: float = 30.0) -> None:
        self._poll_seconds = poll_seconds
        self._running = False
        self._watch_paths: dict[str, float] = {}
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[callable] = None

    def watch(self, path: str) -> None:
        p = Path(path)
        try:
            self._watch_paths[path] = p.stat().st_mtime if p.exists() else 0.0
        except OSError:
            self._watch_paths[path] = 0.0

    def clear(self) -> None:
        self._watch_paths.clear()

    def on_change(self, callback: callable) -> None:
        self._callback = callback

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="hot-reload")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            time.sleep(self._poll_seconds)
            changed = False
            for path, prev_mtime in list(self._watch_paths.items()):
                p = Path(path)
                try:
                    current = p.stat().st_mtime if p.exists() else prev_mtime
                except OSError:
                    continue
                if current > prev_mtime:
                    self._watch_paths[path] = current
                    changed = True
            if changed and self._callback is not None:
                self._callback()

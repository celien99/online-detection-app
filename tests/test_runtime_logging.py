"""Tests for packaged runtime logging."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from app.runtime_logging import LOGGER_NAME, get_runtime_logger, setup_runtime_logging


def test_setup_runtime_logging_creates_log_file(tmp_path: Path) -> None:
    log_path = setup_runtime_logging(tmp_path)
    logger = get_runtime_logger()

    logger.info("hello-runtime-log")
    for handler in logger.handlers:
        handler.flush()

    assert log_path == tmp_path / "runtime.log"
    assert "hello-runtime-log" in log_path.read_text(encoding="utf-8")


def test_setup_runtime_logging_installs_exception_hooks(tmp_path: Path) -> None:
    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    try:
        setup_runtime_logging(tmp_path)

        assert sys.excepthook is not original_sys_hook
        assert threading.excepthook is not original_thread_hook
    finally:
        sys.excepthook = original_sys_hook
        threading.excepthook = original_thread_hook
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

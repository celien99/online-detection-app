"""Runtime logging for packaged GUI deployments."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path


LOGGER_NAME = "online_detection_app"


def setup_runtime_logging(log_dir: str | Path = "./logs") -> Path:
    log_path = Path(log_dir) / "runtime.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
    logger.addHandler(handler)

    def excepthook(exc_type, exc_value, exc_traceback):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def threading_excepthook(args: threading.ExceptHookArgs):
        logger.critical(
            "Uncaught thread exception in %s",
            args.thread.name if args.thread else "<unknown>",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        if hasattr(threading, "__excepthook__"):
            threading.__excepthook__(args)

    sys.excepthook = excepthook
    threading.excepthook = threading_excepthook
    logger.info("Runtime logging initialized: %s", log_path.resolve())
    return log_path


def get_runtime_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)

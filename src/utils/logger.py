import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from rich.logging import RichHandler

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ROOT_SRC = os.path.join(ROOT, "src")
if ROOT_SRC not in sys.path:
    sys.path.insert(0, ROOT_SRC)

from config import LOG_DIR, settings


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for log records."""

    def format(self, record: logging.LogRecord) -> str:
        # Ensure message is rendered using the standard machinery first
        record.message = record.getMessage()
        # Emit ISO8601 time in UTC with milliseconds and 'Z' suffix
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        time_str = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

        payload: dict[str, Any] = {
            "time": time_str,
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "pathname": record.pathname,
            "filename": record.filename,
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }

        if record.exc_info:
            # Include exception info if present
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class ISOFormatter(logging.Formatter):
    """Formatter that renders asctime in ISO 8601 (UTC with 'Z')."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # Keep milliseconds for precision and use 'Z' suffix for UTC
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def setup_logging():
    # Console rich handler
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_level=True,
        show_path=True,
        log_time_format="%Y-%m-%d %H:%M:%S",
        omit_repeated_times=True,
    )
    root = logging.getLogger()
    level = getattr(logging, str(settings.log.level), None)
    if not isinstance(level, int):
        level = logging.INFO
    root.setLevel(level)

    # File handlers under log/<year>/<month>/<day>/
    os.makedirs(LOG_DIR, exist_ok=True)

    safe_name = settings.log.name.lower().replace(" ", "_")
    # JSON logs (preserve original filename for backward compatibility)
    log_file = os.path.join(LOG_DIR, f"{safe_name}.log")

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        ISOFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    # Apply a consistent level to console handler as well
    console_handler.setLevel(level)

    root.handlers = [console_handler, file_handler]


if __name__ == "__main__":
    setup_logging()

    log = logging.getLogger("test-logger")

    log.debug("Debug message")
    log.info("Info message")
    log.warning("Warning message")
    log.error("Error message")
    log.critical("Critical message")

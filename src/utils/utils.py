import json
import os
import sys
from typing import Any

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ROOT_SRC = os.path.join(ROOT, "src")
if ROOT_SRC not in sys.path:
    sys.path.insert(0, ROOT_SRC)

from config import LOG_DIR


def save_to_file(
    data: str,
    filename: str,
    *,
    dir: str | None = LOG_DIR,
    subdir: str | None = None,
    encoding: str = "utf-8",
) -> None:
    """Save a string to a file (text mode only).

    Args:
        data: String content to write.
        filename: Destination filename (relative to dir when provided).
        dir: Base directory. When None, treat filename as absolute/relative as-is.
        subdir: Subdirectory within the base directory (if any).
        encoding: Text encoding used for writing.
    """

    path = (
        os.path.abspath(os.path.join(dir, subdir, filename))
        if dir and subdir
        else (
            os.path.abspath(os.path.join(dir, filename))
            if dir
            else os.path.abspath(filename)
        )
    )
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding=encoding) as f:
        f.write(data)


if __name__ == "__main__":
    test_obj: dict[str, Any] = {
        "key": "value",
        "num": 42,
        "none": None,
    }
    save_to_file(json.dumps(test_obj), "test.json", subdir="test_subdir")

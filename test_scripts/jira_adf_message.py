import json
import os
import sys
from typing import Any

from jira import JIRA

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.config import settings

# Jira Cloud auth
jira = JIRA(
    settings.jira.server,
    basic_auth=(settings.jira.email, settings.jira.api_token),
)

# Manually prepare ADF
adf: dict[str, Any] = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "expand",
            "attrs": {"title": "References"},
            "content": [
                {
                    "type": "table",
                    "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
                    "content": [
                        {
                            "type": "tableRow",
                            "content": [
                                {
                                    "type": "tableHeader",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Name"}
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableHeader",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Value"}
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableHeader",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Notes"}
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "tableRow",
                            "content": [
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "API"}
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "v1.0"}
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Stable"}
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "tableRow",
                            "content": [
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [{"type": "text", "text": "DB"}],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Postgres"}
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "type": "tableCell",
                                    "attrs": {},
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {
                                                    "type": "text",
                                                    "text": "Replication on",
                                                }
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                }
            ],
        }
    ],
}

# Post the prepared ADF as a comment to an existing issue.
issue_key = "PLAYG-150"
resp = jira._session.post(  # type: ignore
    f"{jira._options['server']}/rest/api/3/issue/{issue_key}/comment",  # type: ignore
    headers={"Content-Type": "application/json"},
    data=json.dumps({"body": adf}),
)

print(f"HTTP {resp.status_code} when posting comment to {issue_key}")
try:
    resp.raise_for_status()
except Exception as exc:  # pragma: no cover - simple runtime error reporting
    print("Failed to post comment:", exc)

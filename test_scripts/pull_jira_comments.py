# pyright: reportUnknownMemberType=false
import logging
import os
import re
import sys
from typing import cast

from jira import JIRA, Comment, Issue

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from src.config import settings

log = logging.getLogger(settings.log.name)

# JQL: issues updated in the last 24 hours
JQL = 'updated >= -52w AND project in ("PLAYG", "CERM7", "LRN")'

jira = JIRA(
    server=settings.jira.server,
    basic_auth=(settings.jira.email, settings.jira.api_token),
)


def process_comments() -> dict[Issue, list[Comment]]:
    matching_comments: dict[Issue, list[Comment]] = {}
    issues: list[Issue] = cast(
        list[Issue],
        jira.enhanced_search_issues(
            JQL,
            fields=["comment"],
            maxResults=5000,  # API only returns max 100 issues at a time
        ),
    )
    log.info(f"Found {len(issues)} issues updated in the last 52 weeks.")
    for issue in issues:
        comments = issue.fields.comment.comments
        for comment in comments:
            body = str(comment.body).strip()
            lines = body.splitlines()
            first = " ".join(lines[:1]).lower()
            pattern = re.compile(
                r"^h[1-6]\.\s*(online help|doc & test)\b", re.IGNORECASE
            )
            if pattern.match(first):
                log.info(f"Match in {issue.key}")
                matching_comments.setdefault(issue, []).append(comment)
                run_custom_script(issue.key, body)

    return matching_comments


def run_custom_script(issue_key: str, comment: str):
    # Replace with your real logic
    log.info(f"Running script for {issue_key} with comment:\n{comment[:200]}...")


def main():
    matching_comments = process_comments()
    log.info(
        f"Found {sum(len(comments) for comments in matching_comments.values())} comments in {len(matching_comments.keys())} issues in the last 52 weeks."
    )


if __name__ == "__main__":
    main()

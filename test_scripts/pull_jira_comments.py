# pyright: reportUnknownMemberType=false
import logging
import os
import sys
from typing import cast

from jira import JIRA, Issue

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from src.config import settings

log = logging.getLogger(settings.log.name)

# Use the configured JQL directly for a simple connectivity test
JQL = settings.jql or "updated >= -1d ORDER BY updated DESC"
log.info("Using JQL: %s", JQL)

jira = JIRA(
    server=settings.jira.server,
    basic_auth=(settings.jira.email, settings.jira.api_token),
)


def search_all_issues(jql: str, *, fields: list[str] | None = None) -> list[Issue]:
    """Fetch all issues using Jira Cloud enhanced search with auto-pagination.

    Pass maxResults=0 to enhanced_search_issues to fetch all pages using nextPageToken.
    """
    issues = cast(
        list[Issue],
        jira.enhanced_search_issues(
            jql_str=jql,
            fields=fields,
            maxResults=0,  # 0 means fetch all pages (auto-paginate)
        ),
    )
    return issues


def fetch_issues() -> list[Issue]:
    issues: list[Issue] = search_all_issues(
        JQL, fields=["summary", "description", "created", "comment"]
    )
    return issues


def main():
    issues = fetch_issues()
    log.info("Fetched %d issues: %s", len(issues), ", ".join(i.key for i in issues))
    # Print a small summary with comment counts
    for issue in issues:
        comments = getattr(issue.fields, "comment", None)
        count = len(getattr(comments, "comments", []) or [])
        log.info("- %s: %d comments", issue.key, count)


if __name__ == "__main__":
    main()

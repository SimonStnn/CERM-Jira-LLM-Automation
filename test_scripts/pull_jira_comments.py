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
JQL_PROJECTS = '", "'.join(settings.projects)
JQL_KEYWORDS = " OR ".join(f'comment ~ "{keyword}"' for keyword in settings.keywords)
JQL = f'updated >= -12w AND project in ("{JQL_PROJECTS}") AND ({JQL_KEYWORDS})'

log.info(f"Using JQL: {JQL}")

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


def process_comments() -> dict[Issue, list[Comment]]:
    matching_comments: dict[Issue, list[Comment]] = {}
    issues: list[Issue] = search_all_issues(JQL, fields=["comment"])
    log.info(
        f"Fetched {len(issues)} issues updated in the last 52 weeks (auto-paginated)."
    )
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
                matching_comments.setdefault(issue, []).append(comment)

    return matching_comments


def main():
    matching_comments = process_comments()
    log.info(
        f"Found {sum(len(comments) for comments in matching_comments.values())} comments in {len(matching_comments.keys())} issues in the last 52 weeks.\n({', '.join(issue.key for issue in matching_comments.keys())})"
    )
    log.info("Issues with multiple matching comments:")
    for issue, comments in matching_comments.items():
        if len(comments) > 1:
            log.info(f" - {issue.key}: {len(comments)} comments")


if __name__ == "__main__":
    main()

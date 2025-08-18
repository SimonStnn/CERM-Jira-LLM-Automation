from __future__ import annotations

import re

from jira import JIRA
from requests_toolbelt import user_agent

from config import settings

__version__ = "0.0.0"

assert __version__ is not None, "Version must be set"


# By default, the client will connect to a Jira instance started from the Atlassian Plugin SDK
jira = JIRA(
    settings.jira.server,
    basic_auth=(settings.jira.email, settings.jira.api_token),
    options={
        "headers": {"User-Agent": user_agent(settings.jira.user_agent, __version__)}
    },
)

# Get all projects viewable by anonymous users.
projects = jira.projects()

# Sort available project keys, then return the second, third, and fourth keys.
keys = sorted(project.key for project in projects)[2:5]

print(projects)

# exit()

# Get an issue.
issue = jira.issue("JRA-1330")
# Find all comments made by Atlassians on this issue.
atl_comments = [
    comment
    for comment in issue.fields.comment.comments
    if re.search(r"@atlassian.com$", comment.author.key)
]

# Add a comment to the issue.
jira.add_comment(issue, "Comment text")

# Change the issue's summary and description.
issue.update(
    summary="I'm different!", description="Changed the summary to be different."
)

# Change the issue without sending updates
issue.update(notify=False, description="Quiet summary update.")

# You can update the entire labels field like this
issue.update(fields={"labels": ["AAA", "BBB"]})

# Or modify the List of existing labels. The new label is unicode with no
# spaces
issue.fields.labels.append("new_text")
issue.update(fields={"labels": issue.fields.labels})

# Send the issue away for good.
issue.delete()

# Linking a remote jira issue (needs applinks to be configured to work)
issue = jira.issue("JRA-1330")
issue2 = jira.issue("XX-23")  # could also be another instance
jira.add_remote_link(issue.id, issue2)

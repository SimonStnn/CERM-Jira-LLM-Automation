from __future__ import annotations

from jira import JIRA
from requests_toolbelt import user_agent

from config import log, settings

__version__ = "0.0.0"

assert __version__ is not None, "Version must be set"


def main():
    log.info("Application started.")

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

    log.info(f"Projects: {keys}")


if __name__ == "__main__":
    main()

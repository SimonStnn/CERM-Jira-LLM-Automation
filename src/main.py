from __future__ import annotations

from jira import JIRA
from openai import AzureOpenAI
from requests_toolbelt import user_agent  # type: ignore

from config import log, settings
from prompt import Prompt

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

    client = AzureOpenAI(
        azure_endpoint=settings.azure.endpoint,
        azure_deployment=settings.azure.deployment_name,
        api_key=settings.azure.api_key,
        api_version=settings.azure.api_version,
    )

    log.info("Azure OpenAI client created.")

    # Prepare the chat prompt using the markdown files
    prompt = Prompt.from_markdown_files()
    messages = prompt.to_chat_completion_messages()

    log.info("Sending chat completion request to Azure OpenAI.")

    # Generate the completion
    completion = client.chat.completions.create(
        model=settings.azure.deployment_name,
        messages=messages,
        max_completion_tokens=16384,
        stop=None,
        stream=False,
    )

    log.info(completion.choices[0].message.content)


if __name__ == "__main__":
    main()

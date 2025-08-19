from __future__ import annotations

from jira import JIRA
from openai import AzureOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
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

    client = AzureOpenAI(
        azure_endpoint=settings.azure.endpoint,
        azure_deployment=settings.azure.deployment_name,
        api_key=settings.azure.api_key,
        api_version=settings.azure.api_version,
    )

    log.info("Azure OpenAI client created.")

    # Prepare the chat prompt
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": (
                "You are an assistant that rewrites technical developer descriptions of "
                "CERM MIS software features into clear end-user help documentation. "
                "CERM develops specialized MIS software for the label printing and packaging industry. "
                "Their system integrates business processes like quoting, order management, planning, "
                "production, shipping, and invoicing. By centralizing these workflows, CERM helps printing "
                "companies reduce manual work, track performance, and scale efficiently. "
                "CERM also incorporates feedback from user groups to ensure the software evolves with "
                "real customer needs.\n\n"
                "Your job: take a developer's technical description of a feature or change and rewrite it "
                "so that an end user can easily understand it. Avoid technical jargon. Focus on what the "
                "feature does, why it matters, and how the end user can use it."
            ),
        },
        {
            "role": "user",
            "content": (
                "Developer description: The new API endpoint integrates with ERP backends "
                "via asynchronous webhooks to auto-sync shipment status.\n\n"
                "Rewrite this as end-user help documentation."
            ),
        },
    ]

    log.info("Sending chat completion request to Azure OpenAI.")

    # Generate the completion
    completion = client.chat.completions.create(
        model=settings.azure.deployment_name,
        messages=messages,
        max_completion_tokens=16384,
        stop=None,
        stream=False,
    )

    log.info(completion.to_json())


if __name__ == "__main__":
    main()

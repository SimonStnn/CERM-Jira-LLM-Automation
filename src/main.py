from __future__ import annotations

from jira import JIRA
from openai import AzureOpenAI
from requests_toolbelt import user_agent  # type: ignore

from config import log, settings
from help_selector import select_help_documents
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

    issue = jira.issue("PLAYG-149")

    log.info("Processing issue %s", issue.key)

    log.info(issue.fields.summary + "\n" + (issue.fields.description or ""))

    onlinehelp_comment = None
    for comment in issue.fields.comment.comments:
        # Check if "online help" is mentioned in the first two lines
        if "online help" in "".join(str(comment.body).lower().split("\n", 2)[:2]):
            onlinehelp_comment = comment
            break
    else:
        log.warning("No online help comment found.")
        exit(1)

    log.info("Online help comment:\n%s", onlinehelp_comment.body)

    reference_docs = select_help_documents(issue, onlinehelp_comment, max_documents=5)

    log.info("Found %d reference documents.", len(reference_docs))
    log.info(
        "Reference documents:\n%s",
        "\n".join([f"https://onlinehelp.cerm.net/{doc}" for doc in reference_docs]),
    )

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

    log.info("Using model: %s", settings.azure.deployment_name)
    log.info(messages)

    exit()

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

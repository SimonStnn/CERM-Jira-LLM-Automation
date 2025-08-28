import logging
from typing import Any, cast

from jira import JIRA, Comment, Issue
from openai import AzureOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pinecone import Pinecone
from requests_toolbelt import user_agent  # type: ignore

from config import Reference, Settings, __version__, settings

log = logging.getLogger(settings.log.name)


class Controller:
    settings: Settings
    jira: JIRA
    pinecone: Pinecone
    client: AzureOpenAI
    triage_client: AzureOpenAI
    embedding_client: AzureOpenAI

    def __init__(self) -> None:
        self.settings = settings

        # Initialize JIRA client
        self.jira = JIRA(
            server=self.settings.jira.server,
            basic_auth=(self.settings.jira.email, self.settings.jira.api_token),
            options={
                "headers": {
                    "User-Agent": user_agent(self.settings.jira.user_agent, __version__)
                },
            },
        )
        self.client = AzureOpenAI(
            api_key=self.settings.azure.api_key,
            api_version=self.settings.azure.api_version,
            azure_endpoint=self.settings.azure.endpoint,
        )
        self.triage_client = AzureOpenAI(
            api_key=self.settings.azure.api_key,
            api_version=self.settings.azure.api_version,
            azure_endpoint=self.settings.azure.triage.endpoint,
        )
        self.embedding_client = AzureOpenAI(
            api_key=self.settings.azure.api_key,
            api_version=self.settings.azure.api_version,
            azure_endpoint=self.settings.azure.embedding.endpoint,
        )
        self.pc = Pinecone(api_key=self.settings.pinecone.api_key)
        index_info = cast(
            Any, self.pc.describe_index(name=settings.pinecone.index_name)
        )
        self.idx = self.pc.Index(host=cast(str, index_info.host))

        log.debug("Controller initialized")

    def build_user_prompt(
        self, references: list[Reference], issue: Issue, onlinehelp_comment: Comment
    ) -> str:
        user_prompt = (
            "\n".join(
                [
                    f"# Reference {i+1}: {ref.title}\n\n{ref.text.replace('\n#', '\n##')}\n"
                    for i, ref in enumerate(references)
                ]
            )
            + f"\n# {issue.fields.summary}"
            + f"\n\n{issue.fields.description or ''}"
            + f"\n\n# {onlinehelp_comment.body}"
        ).replace("\r", "")

        return user_prompt

    def generate_completion(self, messages: list[ChatCompletionMessageParam]):
        completion = self.client.chat.completions.create(
            model=settings.azure.deployment_name,
            messages=messages,
            max_completion_tokens=16384,
            stop=None,
            stream=False,
        )
        completion_content = completion.choices[0].message.content or ""
        # For local testing we read a pre-generated result from disk. In production
        # you can re-enable the model call if needed.
        # with open(
        #     os.path.join(PROMPTS_DIR, "issues", issue.key, "result.md"),
        #     "r",
        #     encoding="utf-8",
        # ) as f:
        #     completion_content = f.read()

        return completion_content

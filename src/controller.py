import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, cast

from jira import JIRA, Comment, Issue
from openai import AzureOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pinecone import Pinecone
from requests_toolbelt import user_agent  # type: ignore

from config import Settings, settings
from const import SYSTEM_PROMPT_PATH, __version__
from utils import build_jira_comment

log = logging.getLogger(settings.log.name)


@dataclass
class Reference:
    title: str
    text: str
    source: str


class Controller:
    settings: Settings
    jira: JIRA
    pinecone: Pinecone
    client: AzureOpenAI
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

    def find_online_help_issues(self, jql: str) -> dict[Issue, list[Comment]]:
        # Fetch the issues from JIRA (last 52 weeks)

        matching_comments: dict[Issue, list[Comment]] = {}
        # Auto-paginate using Jira Cloud enhanced search (maxResults=0)
        issues: list[Issue] = cast(
            list[Issue],
            self.jira.enhanced_search_issues(jql, maxResults=0),
        )
        log.debug(
            "Fetched %d issues updated in the last 52 weeks (auto-paginated)",
            len(issues),
        )

        for issue in issues:
            comments = issue.fields.comment.comments
            for comment in comments:
                lines = str(comment.body).strip().splitlines()
                first = " ".join(lines[:1]).lower()
                pattern = re.compile(
                    r"^h[1-6]\.\s*(online help|doc & test|test & doc)\b",
                    re.IGNORECASE,
                )
                if pattern.match(first):
                    matching_comments.setdefault(issue, []).append(comment)

        return matching_comments

    def get_system_prompt(self, file_path: str = SYSTEM_PROMPT_PATH) -> str:
        log.info("Using system prompt: %s", file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        return system_prompt

    def query_pinecone(self, query: str, *, top_k: int = 10) -> list[Reference]:
        query_embedding = (
            self.embedding_client.embeddings.create(
                model=settings.azure.embedding.deployment_name,
                input=query,
            )
            .data[0]
            .embedding
        )

        results = cast(
            Any,
            self.idx.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=settings.pinecone.namespace,
                include_metadata=True,
                # filter={"metadata_key": { "$eq": "value1" }}
            ),
        )

        return [
            Reference(
                title=doc["metadata"]["title"],
                text=doc["metadata"]["text"],
                source=doc["metadata"]["source"],
            )
            for doc in results.matches
        ]

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
        start_time = time.time()
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
        elapsed_time = time.time() - start_time
        log.info("Obtained completion (took %.2f seconds)", elapsed_time)

        return completion_content

    def build_jira_comment(
        self, completion_content: str, references: list[Reference], issues_dir: str
    ) -> tuple[str, dict[str, Any]]:
        comment_text, adf = build_jira_comment(
            completion_content=completion_content,
            references=references,
            issues_dir=issues_dir,
        )
        return comment_text, adf

    def post_adf(self, issue: Issue, comment: Comment, adf: dict[str, Any]):
        try:
            url = f"{self.jira._options['server']}/rest/api/3/issue/{issue.key}/comment"  # type: ignore[attr-defined]
            resp = self.jira._session.post(  # type: ignore[attr-defined]
                url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                data=json.dumps({"body": adf, "parentId": str(comment.id)}),
            )
            log.info(
                "HTTP %s when posting ADF comment to issue %s (reply-to comment %s)",
                resp.status_code,
                issue.key,
                comment.id,
            )
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover - runtime posting may fail in CI
            log.exception("Failed to post ADF comment: %s", exc)

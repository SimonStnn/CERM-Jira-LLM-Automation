import json
import logging
import re
from typing import Annotated, Any, cast

from jira import JIRA, Comment, Issue
from openai import AzureOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pinecone import Pinecone
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from requests_toolbelt import user_agent  # type: ignore

from config import Reference, Settings, __version__, settings
from utils import build_jira_comment

log = logging.getLogger(settings.log.name)

# Shared types for scoring
Percent = Annotated[float, Field(ge=0, le=1)]
_Score = Annotated[float, Field(ge=0, le=1)]


class _RelevantSelectionModel(BaseModel):
    """Pydantic-validated structure for the AI response JSON."""

    model_config = ConfigDict(extra="forbid")

    scores: dict[str, _Score] = Field(default_factory=dict)

    @classmethod
    @field_validator("scores", mode="after")
    def _validate_scores(cls, v: dict[str, Any]) -> dict[str, float]:
        filtered: dict[str, float] = {}
        for k, val in v.items():
            try:
                f = float(val)
            except Exception:
                continue
            if 0.0 <= f <= 1.0:
                filtered[str(k)] = f
        return filtered


class Controller:
    settings: Settings
    jira: JIRA
    pc: Pinecone
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

    # ----- Helpers for AI comment filtering -----

    @classmethod
    def _compact(cls, text: str, limit: int = 1200) -> str:
        text = (text or "").replace("\r", "").strip()
        if len(text) <= limit:
            return text
        head = text[: limit - 200]
        tail = text[-180:]
        return f"{head}\n…\n{tail}"

    @classmethod
    def _build_messages(
        cls, issue: Issue, comments: list[Comment]
    ) -> list[dict[str, Any]]:
        summary = cast(str, getattr(issue.fields, "summary", ""))
        description = cast(str, getattr(issue.fields, "description", "") or "")
        created = cast(str, getattr(issue.fields, "created", ""))

        system = (
            "You are a senior triage engineer. The Jira issue has already been resolved. "
            "Identify which of the provided comments were relevant to diagnosing or fixing the issue."
            "\nGuidelines:"
            "\n- Relevant: technical findings, steps taken, logs, config, root-cause clues, links to authoritative docs, direct fix instructions, code changes."
            "\n- Not relevant: chit-chat, thanks, scheduling, duplicated text, off-topic, meta commentary."
            "\n- Prefer comments that contain concrete steps, error messages, or references that directly contributed to the resolution."
            "\nReturn a single JSON object only with keys: scores (object mapping id->0..1 (float))."
        )

        user_payload: dict[str, Any] = {
            "issue": {
                "key": issue.key,
                "summary": Controller._compact(summary, 500),
                "description": Controller._compact(description, 1500),
                "created": created,
            },
            "comments": [
                {
                    "id": str(c.id),
                    "author": cast(str, getattr(c.author, "displayName", "")),
                    "created": cast(str, getattr(c, "created", "")),
                    "body": Controller._compact(str(c.body), 1500),
                }
                for c in comments
            ],
            "output_schema": {
                "scores": {"<comment_id>": 0.1},
            },
        }

        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "You must answer with a single JSON object only, no extra text.\n"
                    + json.dumps(user_payload, ensure_ascii=False)
                ),
            },
        ]

    @classmethod
    def _extract_json(cls, s: str) -> dict[str, Any] | None:
        s = s.strip()
        try:
            return cast(dict[str, Any], json.loads(s))
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            try:
                return cast(dict[str, Any], json.loads(m.group(0)))
            except Exception:
                return None
        return None

    # ----- Public operations (merged from IssueGatherer) -----

    def query(self, jql: str) -> list[Issue]:
        issues: list[Issue] = cast(
            list[Issue],
            self.jira.enhanced_search_issues(jql, maxResults=0),
        )
        return issues

    def ai_filter_comments(
        self, issue: Issue, *, relevance_score: Percent = 0.5
    ) -> tuple[list[Comment], dict[str, float]]:
        messages = Controller._build_messages(issue, issue.fields.comment.comments)

        completion = self.triage_client.chat.completions.create(
            model=settings.azure.triage.deployment_name,
            messages=messages,  # type: ignore[arg-type]
            max_completion_tokens=500,
            temperature=0.1,
        )
        content = completion.choices[0].message.content or ""
        raw = Controller._extract_json(content) or {"scores": {}}
        try:
            parsed = _RelevantSelectionModel.model_validate(raw)
        except ValidationError as exc:
            log.warning("AI response validation failed: %s", exc)
            parsed = _RelevantSelectionModel()

        id_set = {
            str(i) for i in parsed.scores.keys() if parsed.scores[i] >= relevance_score
        }

        selected = [c for c in issue.fields.comment.comments if str(c.id) in id_set]
        return selected, parsed.scores

    @classmethod
    def get_target_comment(
        cls, comments: list[Comment], pattern: re.Pattern[str]
    ) -> Comment | None:
        for comment in comments:
            lines = str(comment.body).strip().splitlines()
            first = " ".join(lines[:1]).lower()
            if pattern.match(first):
                return comment
        return None

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

    def build_jira_comment(
        self, completion_content: str, references: list[Reference]
    ) -> tuple[str, dict[str, Any]]:
        comment_text, adf = build_jira_comment(
            completion_content=completion_content,
            references=references,
        )
        return comment_text, adf

    def post_adf(
        self,
        issue: Issue,
        adf: dict[str, Any],
        *,
        reply_comment: Comment | None = None,
    ):
        try:
            url = f"{self.jira._options['server']}/rest/api/3/issue/{issue.key}/comment"  # type: ignore[attr-defined]
            body: dict[str, Any] = {"body": adf}
            if reply_comment:
                body["parentId"] = str(reply_comment.id)
            resp = self.jira._session.post(  # type: ignore[attr-defined]
                url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                data=json.dumps(body),
            )
            log.info(
                "HTTP %s when posting ADF comment to issue %s (reply-to comment %s)",
                resp.status_code,
                issue.key,
                reply_comment.id if reply_comment else "N/A",
            )
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover
            log.exception("Failed to post ADF comment: %s", exc)

    def build_user_prompt(
        self, references: list[Reference], issue: Issue, onlinehelp_comment: Comment
    ) -> str:
        user_prompt = (
            "\n".join(
                [
                    f"# Reference {i+1}: {ref.title}\n\n{replaced_text}\n"
                    for i, ref in enumerate(references)
                    for replaced_text in [ref.text.replace("\n#", "\n##")]
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

import json
import logging
import os
from typing import TypedDict

from jira import Issue
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from config import PROMPTS_ISSUES_DIR, SYSTEM_PROMPT_PATH, Reference, settings

log = logging.getLogger(settings.log.name + "." + __name__)


class UserComment(TypedDict):
    author: str
    content: str


class PromptBuilder:
    _system_prompt: str | None
    _user_comments: list[UserComment]
    _docs_references: list[Reference]
    issue: Issue

    def __init__(
        self,
        *,
        system_prompt: str | None = None,
        issue: Issue,
        user_comments: list[UserComment] | None = None,
    ) -> None:
        self._system_prompt = system_prompt
        self.issue = issue
        self._user_comments = user_comments or []
        self._docs_references = []

    @property
    def system_prompt(self) -> str:
        return self._system_prompt or ""

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value.strip()

    @system_prompt.deleter
    def system_prompt(self) -> None:
        self._system_prompt = None

    @property
    def topic(self) -> str | None:
        return self.issue.fields.summary

    @property
    def user_comments(self) -> list[UserComment]:
        return self._user_comments

    @property
    def docs_references(self) -> list[Reference]:
        return self._docs_references

    @classmethod
    def get_system_prompt(cls, *, file_path: str = SYSTEM_PROMPT_PATH) -> str:
        log.debug("Using system prompt: %s", file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        return system_prompt

    def compile_messages(self) -> list[ChatCompletionMessageParam]:
        def _compact(text: str, limit: int = 1800) -> str:
            text = (text or "").replace("\r", "").strip()
            if len(text) <= limit:
                return text
            head = text[: limit - 220]
            tail = text[-200:]
            return f"{head}\n…\n{tail}"

        parts: list[str] = []

        # High-level instruction to align with the system prompt
        parts.append(
            (
                "Use only the material below to produce the deliverables described in the system prompt."
                "If information is missing, list clarifying questions."
            )
        )

        if self.topic:
            parts.append(f"# Topic\n{self.topic}")

        if self.user_comments:
            lines: list[str] = ["## Curated developer comments (from Jira)"]
            for i, uc in enumerate(self.user_comments, start=1):
                author = (uc.get("author") or "").strip()
                content = _compact(str(uc.get("content", "")), 1500)
                lines.append(f"### Comment {i} — {author}\n{content}")
            parts.append("\n\n".join(lines))

        if self.docs_references:
            lines = ["## Reference documents (retrieved)"]
            for i, ref in enumerate(self.docs_references, start=1):
                # Demote headings inside reference text to avoid overpowering the main structure
                text = _compact(ref.text.replace("\n#", "\n##"), 1800)
                lines.append(
                    f"### Reference {i}: {ref.title}\n{text}\n\nSource: {ref.source}"
                )
            parts.append("\n\n".join(lines))

        parts.append(
            "End of input. Follow the Output Structure from the system prompt. Do not invent details."
        )

        user_content = "\n\n".join(parts)

        prompt: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        SAVE_DIR = os.path.join(PROMPTS_ISSUES_DIR, self.issue.key)
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(
            os.path.join(SAVE_DIR, "prompt.json"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(prompt))

        return prompt

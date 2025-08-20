import logging
import os
from typing import Literal, cast

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from config import settings

log = logging.getLogger(settings.log.name)

PROMPT_DIR: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "prompt")
)

log.debug(f"Prompt directory: {PROMPT_DIR}")

Role = Literal["user", "assistant", "system"]


class Prompt:
    def __init__(self, messages: list[ChatCompletionMessageParam]):
        self.messages = messages

    def to_chat_completion_messages(self) -> list[ChatCompletionMessageParam]:
        return self.messages

    @classmethod
    def get_system_prompt(
        cls, directory: str = PROMPT_DIR, filename: str = "system.md"
    ) -> ChatCompletionMessageParam:
        with open(os.path.join(directory, filename), "r") as f:
            content = f.read()
            return {"role": "system", "content": content}

    @classmethod
    def from_markdown_files(cls, directory: str = PROMPT_DIR) -> "Prompt":
        messages: list[ChatCompletionMessageParam] = []
        for filename in os.listdir(directory):
            if filename.endswith(".md"):
                role = (
                    filename[:-3].lower()
                    if filename[:-3].lower() in ["system", "user", "assistant"]
                    else "user"
                )
                with open(os.path.join(directory, filename), "r") as f:
                    content = f.read()
                    message = {"role": role, "content": content}
                    messages.append(cast(ChatCompletionMessageParam, message))
        return cls(messages)


if __name__ == "__main__":
    prompt = Prompt.from_markdown_files()
    log.info(f"Loaded prompt with {len(prompt.messages)} messages.")
    for message in prompt.messages:
        content = message.get("content")
        if isinstance(content, str):
            preview = content[:30]
        else:
            preview = str(content)[:30] if content is not None else "<no content>"
        log.info(f" - {message.get('role', 'user')}: {preview}...")

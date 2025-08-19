import logging
import os
from typing import Literal, cast

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from ..config import settings

log = logging.getLogger(settings.log.name)

PROMPT_DIR: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "prompt")
)

log.debug(f"Prompt directory: {PROMPT_DIR}")

Role = Literal["user", "assistant", "system"]


class Prompt:

    class Message:
        references: list[str] = []

        def __init__(self, role: Role, content: str):
            self.role = role
            self.content = content

        def to_chat_completion_message(self) -> ChatCompletionMessageParam:
            # Assuming ChatCompletionMessageParam is a TypedDict or similar, cast the dict
            return cast(
                ChatCompletionMessageParam,
                {
                    "role": self.role,
                    "content": self.content,
                },
            )

    def __init__(self, messages: list[Message]):
        self.messages = messages

    def to_chat_completion_messages(self) -> list[ChatCompletionMessageParam]:
        return [message.to_chat_completion_message() for message in self.messages]

    @classmethod
    def get_system_prompt(
        cls, directory: str = PROMPT_DIR, filename: str = "system.md"
    ) -> Message:
        with open(os.path.join(directory, filename), "r") as f:
            content = f.read()
            return Prompt.Message(role="system", content=content)

    @classmethod
    def from_markdown_files(cls, directory: str = PROMPT_DIR) -> "Prompt":
        messages: list[Prompt.Message] = []
        for filename in os.listdir(directory):
            if filename.endswith(".md"):
                role = (
                    filename[:-3].lower()
                    if filename[:-3].lower() in ["system", "user", "assistant"]
                    else "user"
                )
                with open(os.path.join(directory, filename), "r") as f:
                    content = f.read()
                    messages.append(
                        Prompt.Message(role=cast(Role, role), content=content)
                    )
        return cls(messages)


if __name__ == "__main__":
    prompt = Prompt.from_markdown_files()
    log.info(f"Loaded prompt with {len(prompt.messages)} messages.")
    for message in prompt.messages:
        log.info(f" - {message.role}: {message.content[:30]}...")

import logging
import os
from typing import Literal

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from config import settings

log = logging.getLogger(settings.log.name)

PROMPT_DIR: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "prompt")
)

log.debug(f"Prompt directory: {PROMPT_DIR}")

Role = Literal["user", "assistant", "system"]


class Prompt:
    def __init__(self, system: str, user: str, assistant: str):
        self.system = system
        self.user = user
        self.assistant = assistant

    def to_chat_completion_messages(self) -> list[ChatCompletionMessageParam]:
        return [
            {"role": "user", "content": self.user},
            {"role": "assistant", "content": self.assistant},
        ]

    @classmethod
    def get_system_prompt(
        cls, directory: str = PROMPT_DIR, filename: str = "system.md"
    ) -> ChatCompletionMessageParam:
        with open(os.path.join(directory, filename), "r") as f:
            content = f.read()
            return {"role": "system", "content": content}


if __name__ == "__main__":
    pass

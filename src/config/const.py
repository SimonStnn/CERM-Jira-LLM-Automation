import os
from dataclasses import dataclass

__version__ = "0.0.0"

PROMPTS_DIR = os.path.abspath(os.path.join("prompt"))
PROMPTS_ISSUES_DIR = os.path.join(PROMPTS_DIR, "issues")
SYSTEM_PROMPT_PATH = os.path.join(PROMPTS_DIR, "system.md")


@dataclass
class Reference:
    title: str
    text: str
    source: str

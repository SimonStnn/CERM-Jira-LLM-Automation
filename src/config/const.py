import os
from dataclasses import dataclass
from datetime import datetime

__version__ = "0.0.0"

PROMPTS_DIR = os.path.abspath(os.path.join("prompt"))
PROMPTS_ISSUES_DIR = os.path.join(PROMPTS_DIR, "issues")
SYSTEM_PROMPT_PATH = os.path.join(PROMPTS_DIR, "system.md")

STARTUP = datetime.now()
LOG_DIR = os.path.abspath(
    os.path.join(
        "log", f"{STARTUP.year:04d}", f"{STARTUP.month:02d}", f"{STARTUP.day:02d}"
    )
)


@dataclass
class Reference:
    title: str
    text: str
    source: str

    def to_dict(self):
        return {"title": self.title, "text": self.text, "source": self.source}

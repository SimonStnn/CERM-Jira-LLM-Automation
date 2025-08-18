import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

ENV_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))

load_dotenv(ENV_PATH)
print("Loaded env from: ", ENV_PATH)


class JIRAConfig(BaseSettings):
    server: str = Field(frozen=True)
    email: str = Field(frozen=True, min_length=1)
    api_token: str = Field(frozen=True, min_length=1)
    user_agent: str = Field(default="Cerm7-AI-project", frozen=True)


class Settings(BaseSettings):
    jira: JIRAConfig = JIRAConfig(
        server=os.getenv("JIRA_SERVER"),  # type: ignore
        email=os.getenv("JIRA_EMAIL"),  # type: ignore
        api_token=os.getenv("JIRA_API_TOKEN"),  # type: ignore
        user_agent=os.getenv("JIRA_USER_AGENT"),  # type: ignore
    )

    class Config:
        env_file = ".env"


settings = Settings()

print(settings)

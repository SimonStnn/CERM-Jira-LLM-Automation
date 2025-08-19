import logging
import os
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from rich.logging import RichHandler

ENV_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH, verbose=True)


def setup_logging():
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_level=True,
        show_path=True,
        log_time_format=settings.log.datefmt,
        omit_repeated_times=True,
    )
    root = logging.getLogger()
    level = getattr(logging, str(settings.log.level), None)
    if not isinstance(level, int):
        level = logging.INFO
    root.setLevel(level)
    root.handlers = [handler]


class JIRAConfig(BaseSettings):
    server: str = Field(frozen=True)
    email: str = Field(frozen=True, min_length=1)
    api_token: str = Field(frozen=True, min_length=1, exclude=True)
    user_agent: str = Field(default="Cerm7-AI-project", frozen=True)


class AzureConfig(BaseSettings):
    endpoint: str = Field(frozen=True)
    api_key: str = Field(frozen=True, min_length=1, exclude=True)
    deployment_name: str = Field(frozen=True)
    api_version: str = Field(frozen=True, min_length=1)

    @model_validator(mode="before")
    def model_before_validator(cls, values: dict[str, str]) -> dict[str, str]:
        endpoint = values.get("endpoint")
        if endpoint:
            parsed = urlparse(endpoint)
            query = parse_qs(parsed.query)
            api_version = query.get("api-version") or query.get("api_version")
            if api_version and api_version[0]:
                values["api_version"] = api_version[0]
        return values


class LoggerConfig(BaseSettings):
    level: str = Field(default="INFO", frozen=True)
    datefmt: str = Field(default="%Y-%m-%d %H:%M:%S", frozen=True)
    name: str = Field(frozen=True)


class Settings(BaseSettings):
    jira: JIRAConfig = JIRAConfig(
        server=os.getenv("JIRA_SERVER"),  # type: ignore
        email=os.getenv("JIRA_EMAIL"),  # type: ignore
        api_token=os.getenv("JIRA_API_TOKEN"),  # type: ignore
        user_agent=os.getenv("JIRA_USER_AGENT"),  # type: ignore
    )

    azure: AzureConfig = AzureConfig(
        endpoint=os.getenv("AZURE_ENDPOINT"),  # type: ignore
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  # type: ignore
        deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME"),  # type: ignore
    )

    log: LoggerConfig = LoggerConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        datefmt=os.getenv("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S"),
        name=os.getenv("LOG_NAME", "Cerm7-AI-project"),
    )

    class Config:
        env_file = ENV_PATH


settings = Settings()

setup_logging()
log = logging.getLogger(settings.log.name)

log.info("Loaded env from: %s", ENV_PATH)


if __name__ == "__main__":
    from rich import print

    print(settings)

    log.setLevel("DEBUG")

    log.debug("Debug message")
    log.info("Info message")
    log.warning("Warning message")
    log.error("Error message")
    log.critical("Critical message")

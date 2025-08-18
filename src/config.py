import logging
import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings
from rich.logging import RichHandler

ENV_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH)


def setup_logging():
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_level=True,
        show_path=True,
        log_time_format=settings.log.datefmt,
        omit_repeated_times=False,
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


class LoggerConfig(BaseSettings):
    level: str = Field(default="INFO", frozen=True)
    format: str = Field(
        default="%(asctime)s [%(name)s] %(levelname)s %(message)s", frozen=True
    )
    datefmt: str = Field(default="%Y-%m-%d %H:%M:%S", frozen=True)
    name: str = Field(frozen=True)


class Settings(BaseSettings):
    jira: JIRAConfig = JIRAConfig(
        server=os.getenv("JIRA_SERVER"),  # type: ignore
        email=os.getenv("JIRA_EMAIL"),  # type: ignore
        api_token=os.getenv("JIRA_API_TOKEN"),  # type: ignore
        user_agent=os.getenv("JIRA_USER_AGENT"),  # type: ignore
    )

    log: LoggerConfig = LoggerConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=os.getenv(
            "LOG_FORMAT", "%(asctime)s [%(name)s] %(levelname)s %(message)s"
        ),
        datefmt=os.getenv("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S"),
        name=os.getenv("LOG_NAME", "Cerm7-AI-project"),
    )

    class Config:
        env_file = ".env"


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

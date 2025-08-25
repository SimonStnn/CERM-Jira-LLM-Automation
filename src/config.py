import logging
import os
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from rich.logging import RichHandler

ENV_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH, verbose=True)


class JIRAConfig(BaseSettings):
    server: str = Field(frozen=True)
    email: str = Field(frozen=True, min_length=1)
    api_token: str = Field(frozen=True, min_length=1, exclude=True)
    user_agent: str = Field(default="Cerm7-AI-project", frozen=True)
    post_adf: bool = Field(default=False, frozen=True)


class AzureEmbeddingsConfig(BaseSettings):
    endpoint: str = Field(frozen=True)
    deployment_name: str = Field(frozen=True)
    dimension: int = Field(default=1536, frozen=True)


class AzureConfig(BaseSettings):
    endpoint: str = Field(frozen=True)
    api_key: str = Field(frozen=True, min_length=1, exclude=True)
    deployment_name: str = Field(frozen=True)
    api_version: str = Field(frozen=True, min_length=1)
    embedding: AzureEmbeddingsConfig = Field(frozen=True)

    @model_validator(mode="before")
    def model_before_validator(
        cls, values: AzureEmbeddingsConfig | dict[str, str]
    ) -> Any:
        if not isinstance(values, dict):
            return values
        if endpoint := values.get("endpoint"):
            parsed = urlparse(endpoint)
            query = parse_qs(parsed.query)
            api_version = query.get("api-version") or query.get("api_version")
            if api_version and api_version[0]:
                values["api_version"] = api_version[0]
        return values


class PineconeConfig(BaseSettings):
    api_key: str = Field(frozen=True, min_length=1, exclude=True)
    # environment: str = Field(frozen=True)
    namespace: str = Field(frozen=True)
    index_name: str = Field(frozen=True)


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
        embedding=AzureEmbeddingsConfig(
            endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT"),  # type: ignore
            deployment_name=os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME"),  # type: ignore
            dimension=os.getenv("AZURE_EMBEDDING_DIMENSION"),  # type: ignore
        ),
    )

    pinecone: PineconeConfig = PineconeConfig(
        api_key=os.getenv("PINECONE_API_KEY"),  # type: ignore
        # environment=os.getenv("PINECONE_ENVIRONMENT"),  # type: ignore
        namespace=os.getenv("PINECONE_NAMESPACE"),  # type: ignore
        index_name=os.getenv("PINECONE_INDEX_NAME"),  # type: ignore
    )

    log: LoggerConfig = LoggerConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        datefmt=os.getenv("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S"),
        name=os.getenv("LOG_NAME", "Cerm7-AI-project"),
    )

    class Config:
        env_file = ENV_PATH


settings = Settings()


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

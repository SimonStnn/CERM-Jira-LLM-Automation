import logging
import os
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH, verbose=True)


class JIRAConfig(BaseSettings):
    server: str = Field(frozen=True, min_length=1)
    email: str = Field(frozen=True, min_length=1)
    api_token: str = Field(frozen=True, min_length=1, exclude=True, repr=False)
    user_agent: str = Field(default="AI-project", frozen=True)


class AzureBaseConfig(BaseSettings):
    endpoint: str = Field(frozen=True, min_length=1)
    deployment_name: str = Field(frozen=True, min_length=1)
    api_version: str | None = Field(default=None, frozen=True)

    @model_validator(mode="before")
    def model_before_validator(cls, values: Any | dict[str, str]) -> Any:
        if not isinstance(values, dict):
            return values
        if endpoint := cast(str | None, values.get("endpoint")):
            parsed = urlparse(endpoint)
            query = parse_qs(parsed.query)
            api_version = query.get("api-version") or query.get("api_version")
            if api_version and api_version[0]:
                values["api_version"] = api_version[0]
        return cast(str, values)


class AzureEmbeddingConfig(AzureBaseConfig):
    dimension: int = Field(default=1536, frozen=True)


class AzureConfig(AzureBaseConfig):
    api_key: str = Field(frozen=True, min_length=1, exclude=True, repr=False)
    triage: AzureBaseConfig = Field(frozen=True)
    embedding: AzureEmbeddingConfig = Field(frozen=True)


class PineconeConfig(BaseSettings):
    api_key: str = Field(frozen=True, min_length=1, exclude=True, repr=False)
    # environment: str = Field(frozen=True)
    namespace: str = Field(frozen=True, min_length=1)
    index_name: str = Field(frozen=True, min_length=1)


class LoggerConfig(BaseSettings):
    level: str = Field(default="INFO", frozen=True, min_length=1)
    datefmt: str = Field(default="%Y-%m-%d %H:%M:%S", frozen=True, min_length=1)
    name: str = Field(frozen=True, min_length=1)


class Settings(BaseSettings):
    #! Required for list parsing
    model_config = SettingsConfigDict(populate_by_name=True)

    # Only use explicitly provided init values; ignore environment/dotenv/file secrets for this model.
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (init_settings,)

    projects: list[str] = Field(default_factory=list, frozen=True)
    keywords: list[str] = Field(default_factory=list, frozen=True)

    jira: JIRAConfig = JIRAConfig(
        server=os.getenv("JIRA_SERVER", ""),
        email=os.getenv("JIRA_EMAIL", ""),
        api_token=os.getenv("JIRA_API_TOKEN", ""),
        user_agent=os.getenv("JIRA_USER_AGENT", ""),
    )

    azure: AzureConfig = AzureConfig(
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        endpoint=os.getenv("AZURE_ENDPOINT", ""),
        deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME", ""),
        triage=AzureBaseConfig(
            endpoint=os.getenv("AZURE_TRIAGE_ENDPOINT", ""),
            deployment_name=os.getenv("AZURE_TRIAGE_DEPLOYMENT_NAME", ""),
        ),
        embedding=AzureEmbeddingConfig(
            endpoint=os.getenv("AZURE_EMBEDDING_ENDPOINT", ""),
            deployment_name=os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", ""),
            dimension=int(os.getenv("AZURE_EMBEDDING_DIMENSION", "1536")),
        ),
    )

    pinecone: PineconeConfig = PineconeConfig(
        api_key=os.getenv("PINECONE_API_KEY", ""),
        # environment=os.getenv("PINECONE_ENVIRONMENT", ""),
        namespace=os.getenv("PINECONE_NAMESPACE", ""),
        index_name=os.getenv("PINECONE_INDEX", ""),
    )

    log: LoggerConfig = LoggerConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        datefmt=os.getenv("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S"),
        name=os.getenv("LOG_NAME", "AI-project"),
    )


settings = Settings(
    projects=[
        p.strip() for p in os.getenv("AIR_SEARCH_PROJECTS", "").split(",") if p.strip()
    ],
    keywords=[
        k.strip() for k in os.getenv("AIR_SEARCH_KEYWORDS", "").split(",") if k.strip()
    ],
)


log = logging.getLogger(settings.log.name)

log.info("Loaded env from: %s", ENV_PATH)


if __name__ == "__main__":
    from rich import print

    print(settings)

    log.warning("API keys are not printed. Double check if they are present")

    log.setLevel("DEBUG")

    log.debug("Debug message")
    log.info("Info message")
    log.warning("Warning message")
    log.error("Error message")
    log.critical("Critical message")

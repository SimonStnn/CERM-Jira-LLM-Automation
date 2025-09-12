import logging
import os
from datetime import datetime
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")
)
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

    jql: str = Field(frozen=True, min_length=1)
    project: str = Field(default="CERM7", frozen=True, min_length=1)
    pipeline_last_run_utc: str | None = Field(
        default=None,
        frozen=True,
        description="UTC timestamp of previous pipeline run normalized to 'YYYY-MM-DD HH:MM'",
    )

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
        name=os.getenv("LOG_NAME", "AI-project"),
    )

    @computed_field
    @property
    def jira_query(self) -> str:
        """Build the JQL by replacing the {period} placeholder.

        Priority for last-run timestamp environment variables:
        1. AIR_PIPELINE_LAST_RUN_UTC (set by pipeline when available)
        2. PREVIOUS_LAST_RUN_UTC (legacy / alternate variable name)
        If neither is set, fall back to a default relative period (last 14 days).

        Expected timestamp format (UTC): YYYY-MM-DD HH:MM (strict)
        Injected into a JQL clause like:
            updated >= "YYYY-MM-DD HH:MM"
        """
        last_run = self.pipeline_last_run_utc
        if last_run:
            period = f'updated >= "{last_run}"'
        else:
            log.warning(
                "No last run timestamp set. Falling back to default 14-day period in JQL (AIR_PIPELINE_LAST_RUN_UTC=%s).",
                self.pipeline_last_run_utc,
            )
            period = "updated >= -14d"
        if "{period}" in self.jql:
            return self.jql.replace("{period}", period)

        log.warning("No period placeholder found in JQL. Returning original JQL.")
        return self.jql

    @field_validator("pipeline_last_run_utc")
    @classmethod
    def _validate_last_run(cls, v: str | None) -> str | None:
        if v is None:
            return None
        raw = str(v).strip()
        if not raw:
            return None
        # Accept either:
        # 1. Strict format 'YYYY-MM-DD HH:MM'
        # 2. ISO 8601 UTC like '2025-09-12T08:42:04.1391901Z' (with optional seconds & fractional seconds, optional trailing 'Z')
        #    We normalize all accepted inputs to 'YYYY-MM-DD HH:MM'.
        # Fast path for existing strict format
        fmt = "%Y-%m-%d %H:%M"
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime(fmt)
        except ValueError:
            pass

        # Attempt ISO 8601 parse variants
        iso_candidate = raw
        if iso_candidate.endswith("Z"):
            iso_candidate = iso_candidate[:-1]
        # Replace 'T' with space to leverage strptime patterns
        iso_candidate = iso_candidate.replace("T", " ")

        # Try patterns with decreasing precision
        iso_patterns = [
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        # If fractional seconds have more than 6 digits, truncate to 6 (Python supports microseconds only)
        if "." in iso_candidate:
            head, tail = iso_candidate.split(".", 1)
            # tail may include other separators; isolate digits first
            frac = ""
            rest = ""
            for ch in tail:
                if ch.isdigit():
                    frac += ch
                else:
                    rest += ch
            if len(frac) > 6:
                frac = frac[:6]
            iso_candidate = head + "." + frac + rest if frac else head + rest
        for pattern in iso_patterns:
            try:
                dt = datetime.strptime(iso_candidate, pattern)
                return dt.strftime(fmt)
            except ValueError:
                continue

        return None


print("Loading env from: %s" % ENV_PATH)
settings = Settings(
    jql=os.getenv("AIR_SEARCH_JQL") or "",
    project=os.getenv("AIR_SEARCH_PROJECT", "CERM7"),
    pipeline_last_run_utc=os.getenv("AIR_PIPELINE_LAST_RUN_UTC")
    or os.getenv("PREVIOUS_LAST_RUN_UTC"),
)


log = logging.getLogger(settings.log.name)

log.info("Loaded env from: %s", ENV_PATH)


if __name__ == "__main__":
    from rich import print

    print(settings)

    log.warning("API keys are not printed. Double check if they are present")

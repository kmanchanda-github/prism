from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM — provider + model both configurable; only the matching API key is required
    llm_provider: str = "anthropic"           # anthropic | openai | google | bedrock
    llm_model: str = "claude-sonnet-4-6"

    anthropic_api_key: str | None = None      # required when llm_provider=anthropic
    openai_api_key: str | None = None         # required when llm_provider=openai
    google_api_key: str | None = None         # required when llm_provider=google
    aws_access_key_id: str | None = None      # required when llm_provider=bedrock
    aws_secret_access_key: str | None = None  # required when llm_provider=bedrock
    aws_region: str | None = None             # required when llm_provider=bedrock

    # Database
    database_url: str

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # App
    base_url: str = "http://localhost:8000"
    secret_key: str

    # Optional integrations — read from env, not config.yaml
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_webhook_secret: str | None = None

    salesforce_instance_url: str | None = None
    salesforce_client_id: str | None = None
    salesforce_client_secret: str | None = None

    splunk_base_url: str | None = None
    splunk_token: str | None = None

    datadog_api_key: str | None = None
    datadog_app_key: str | None = None

    slack_bot_token: str | None = None
    sendgrid_api_key: str | None = None
    webex_bot_token: str | None = None

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"anthropic", "openai", "google", "bedrock"}
        if v not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of {allowed}, got '{v}'")
        return v

    @field_validator("database_url")
    @classmethod
    def fix_async_driver(cls, v: str) -> str:
        # Alembic needs sync driver; async code needs asyncpg
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


def load_yaml_config(path: Path = Path("config.yaml")) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_yaml_config() -> dict:
    return load_yaml_config()

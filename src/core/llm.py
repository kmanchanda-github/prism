"""
LLM factory — provider and model are fully controlled by env vars:

  LLM_PROVIDER=anthropic   (or openai, google, bedrock)
  LLM_MODEL=claude-sonnet-4-6

Install only the packages for the provider you use:
  uv pip install -e ".[anthropic]"   # default
  uv pip install -e ".[openai]"
  uv pip install -e ".[google]"
  uv pip install -e ".[bedrock]"
"""
from functools import lru_cache
from typing import Any

from src.core.config import get_settings, get_yaml_config


def get_llm(*, max_tokens: int | None = None, temperature: float | None = None) -> Any:
    settings = get_settings()
    cfg = get_yaml_config().get("llm", {})

    provider = settings.llm_provider
    model = settings.llm_model
    max_tok = max_tokens or cfg.get("max_tokens", 8192)
    temp = temperature if temperature is not None else cfg.get("temperature", 0.2)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            max_tokens=max_tok,
            temperature=temp,
            api_key=settings.anthropic_api_key,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            max_tokens=max_tok,
            temperature=temp,
            api_key=settings.openai_api_key,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            max_output_tokens=max_tok,
            temperature=temp,
            google_api_key=settings.google_api_key,
        )

    if provider == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id=model,
            region_name=settings.aws_region or "us-east-1",
            model_kwargs={"temperature": temp, "max_tokens": max_tok},
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER='{provider}'. Supported: anthropic, openai, google, bedrock"
    )

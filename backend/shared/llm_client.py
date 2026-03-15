from __future__ import annotations

import os
from pathlib import Path

import railtracks as rt
from dotenv import load_dotenv
from openai import OpenAI


GPT_OSS_ENDPOINTS = (
    "https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
    "https://qyt7893blb71b5d3.us-east-2.aws.endpoints.huggingface.cloud/v1",
)
GPT_OSS_MODEL = "openai/gpt-oss-120b"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ENV_PATH, override=False)


class LLMUnavailableError(RuntimeError):
    pass


def llm_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _get_base_urls() -> list[str]:
    configured = os.getenv("OPENAI_BASE_URL", "").strip()
    urls: list[str] = []
    if configured:
        urls.append(configured)
    for endpoint in GPT_OSS_ENDPOINTS:
        if endpoint not in urls:
            urls.append(endpoint)
    return urls


def get_client(base_url: str | None = None) -> OpenAI:
    """GPT-OSS via hackathon HuggingFace endpoint (OpenAI-compatible)."""
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", "test"), base_url=base_url or _get_base_urls()[0])


def call_gpt(messages: list[dict], max_tokens: int = 1500, json_mode: bool = False) -> str:
    """Synchronous GPT-OSS call that returns response text."""
    if not llm_is_configured():
        raise LLMUnavailableError("OPENAI_API_KEY is not configured.")

    kwargs: dict = {
        "model": GPT_OSS_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error: Exception | None = None
    for base_url in _get_base_urls():
        try:
            client = get_client(base_url)
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc

    raise LLMUnavailableError("LLM request failed.") from last_error


def get_railtracks_llm():
    """Railtracks LLM pointing at GPT-OSS endpoint."""
    primary_base_url = _get_base_urls()[0]
    os.environ.setdefault("OPENAI_BASE_URL", primary_base_url)
    try:
        return rt.llm.OpenAILLM(
            GPT_OSS_MODEL,
            api_key=os.getenv("OPENAI_API_KEY", "test"),
            base_url=primary_base_url,
        )
    except TypeError:
        return rt.llm.OpenAILLM(
            GPT_OSS_MODEL,
            api_key=os.getenv("OPENAI_API_KEY", "test"),
        )

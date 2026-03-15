from __future__ import annotations

import os
from pathlib import Path

import railtracks as rt
from dotenv import load_dotenv
from openai import OpenAI


GPT_OSS_ENDPOINT = "https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1"
GPT_OSS_MODEL = "openai/gpt-oss-120b"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ENV_PATH, override=False)


class LLMUnavailableError(RuntimeError):
    pass


def llm_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_client() -> OpenAI:
    """GPT-OSS via hackathon HuggingFace endpoint (OpenAI-compatible)."""
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", "test"), base_url=GPT_OSS_ENDPOINT)


def call_gpt(messages: list[dict], max_tokens: int = 1500, json_mode: bool = False) -> str:
    """Synchronous GPT-OSS call that returns response text."""
    if not llm_is_configured():
        raise LLMUnavailableError("OPENAI_API_KEY is not configured.")

    client = get_client()
    kwargs: dict = {
        "model": GPT_OSS_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMUnavailableError("LLM request failed.") from exc
    return resp.choices[0].message.content or ""


def get_railtracks_llm():
    """Railtracks LLM pointing at GPT-OSS endpoint."""
    os.environ.setdefault("OPENAI_BASE_URL", GPT_OSS_ENDPOINT)
    try:
        return rt.llm.OpenAILLM(
            GPT_OSS_MODEL,
            api_key=os.getenv("OPENAI_API_KEY", "test"),
            base_url=GPT_OSS_ENDPOINT,
        )
    except TypeError:
        return rt.llm.OpenAILLM(
            GPT_OSS_MODEL,
            api_key=os.getenv("OPENAI_API_KEY", "test"),
        )
